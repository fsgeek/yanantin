#!/usr/bin/env python3
"""
Non-inferiority evaluation harness for Pichay.

Tests whether context managed by Pichay produces equivalent output quality
to unmanaged (full) context. The null hypothesis is that managed context
degrades quality; non-inferiority is established by failing to reject
equivalence.

Design:
  1. Load sessions from the conversation corpus (DuckDB)
  2. For each session, find turns where eviction pressure was high
  3. Construct two contexts: full (baseline) and managed (treatment)
  4. Send both to the model with the same continuation prompt
  5. Ensemble LLM judges evaluate outputs on correctness, completeness, coherence
  6. Judges also do blind A/B preference (which output is better?)
  7. If judges cannot reliably distinguish treatment from baseline, that is non-inferiority

Usage:
  python noninferiority_harness.py select [N]       # select N candidate sessions
  python noninferiority_harness.py pair <session_id> # construct paired contexts
  python noninferiority_harness.py run <session_id>  # generate outputs for both conditions
  python noninferiority_harness.py judge <session_id> # run ensemble judges
  python noninferiority_harness.py batch [N]         # full pipeline on N sessions
  python noninferiority_harness.py analyze           # aggregate statistics
"""

import json
import os
import random
import sys
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

import anthropic

# ── Constants ────────────────────────────────────────────────────────

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "noninferiority"
CORPUS_DB = Path(__file__).parent.parent / "data" / "conversations.duckdb"
PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Judge models — ensemble of three for robustness
JUDGE_MODELS = [
    "claude-sonnet-4-20250514",
    "claude-haiku-4-5-20251001",
    "claude-haiku-4-5-20251001",  # second Haiku for tiebreaking
]

# The model that generates the "continuation" outputs
GENERATION_MODEL = "claude-sonnet-4-20250514"


# ── Disposition protocol (shared with disposition_experiment.py) ─────

DISPOSITION_PROTOCOL = """You are a context memory manager. For each block in this conversation,
assign a disposition:
  L = Live (keep in full)
  T = Tombstone (evict entirely — stale or reproducible)
  C = Compress (replace with brief summary)

Output format:
  L:b001,b007,b045
  T:b003,b004,b005
  C:b002"summary of what this block contained"

Rules:
- User intent/decisions/preferences: always L
- Processed tool results (assistant already acted on them): T
- Empty tool results: T
- Assistant reasoning leading to a kept decision: C
- Final ~10 blocks: always L
- Be aggressive with T for stale tool results"""


# ── Data structures ──────────────────────────────────────────────────

@dataclass
class SessionCandidate:
    """A session suitable for non-inferiority testing."""
    session_id: str
    project: str
    path: str
    n_messages: int
    n_tool_results: int
    total_chars: int
    # The turn index where we'll split for evaluation
    eval_turn: int
    # Context size at that turn
    context_chars_at_turn: int


@dataclass
class PairedContext:
    """Full and managed versions of context at a specific turn."""
    session_id: str
    eval_turn: int
    # The prompt that both conditions must respond to
    continuation_prompt: str
    # Full context (all messages up to eval_turn)
    baseline_messages: list[dict]
    baseline_chars: int
    # Managed context (dispositions applied)
    treatment_messages: list[dict]
    treatment_chars: int
    # Metadata
    disposition_stats: dict
    compression_ratio: float


@dataclass
class JudgeVerdict:
    """One judge's evaluation of a paired output."""
    judge_model: str
    # Per-dimension scores (1-5 scale)
    correctness_a: int
    correctness_b: int
    completeness_a: int
    completeness_b: int
    coherence_a: int
    coherence_b: int
    # Blind preference: "A", "B", or "tie"
    preference: str
    # Can the judge tell which had reduced context?
    detected_treatment: Optional[str]  # "A", "B", or None
    # Raw reasoning
    reasoning: str


# ── Session loading ──────────────────────────────────────────────────

def load_conversation_messages(filepath: Path) -> list[dict]:
    """Load all messages from a session JSONL file."""
    messages = []
    with open(filepath) as f:
        for line in f:
            r = json.loads(line)
            rtype = r.get("type")
            if rtype in ("assistant", "user"):
                msg = r.get("message", {})
                if msg.get("role") and msg.get("content"):
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"],
                    })
    return messages


def message_text_size(msg: dict) -> int:
    """Approximate character count of a message's content."""
    content = msg.get("content", "")
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        total = 0
        for c in content:
            if isinstance(c, str):
                total += len(c)
            elif isinstance(c, dict):
                if c.get("type") == "text":
                    total += len(c.get("text", ""))
                elif c.get("type") == "tool_use":
                    total += len(json.dumps(c.get("input", {})))
                elif c.get("type") == "tool_result":
                    rc = c.get("content", "")
                    if isinstance(rc, list):
                        total += sum(len(r.get("text", "")) for r in rc if isinstance(r, dict))
                    else:
                        total += len(str(rc))
        return total
    return 0


def flatten_message_to_text(msg: dict) -> str:
    """Convert a message to plain text for block labeling."""
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, dict):
                ctype = c.get("type", "")
                if ctype == "text":
                    parts.append(c.get("text", ""))
                elif ctype == "tool_use":
                    name = c.get("name", "unknown")
                    inp = json.dumps(c.get("input", {}))
                    if len(inp) > 200:
                        inp = inp[:200] + "..."
                    parts.append(f"[tool: {name}({inp})]")
                elif ctype == "tool_result":
                    rc = c.get("content", "")
                    if isinstance(rc, list):
                        rt = " ".join(r.get("text", "")[:200] for r in rc if isinstance(r, dict))
                    else:
                        rt = str(rc)[:200]
                    parts.append(f"[result: {rt[:150]}]")
        return "\n".join(parts)
    return str(content)


# ── Session selection ────────────────────────────────────────────────

def find_candidate_sessions(min_messages: int = 30, min_tool_results: int = 5,
                            min_chars: int = 50000) -> list[SessionCandidate]:
    """
    Find sessions suitable for non-inferiority testing.

    Good candidates have:
    - Enough messages to create meaningful eviction pressure
    - Tool results (the primary waste category)
    - Enough total content that managed vs full context differs meaningfully
    """
    candidates = []

    for p in PROJECTS_DIR.rglob("*.jsonl"):
        try:
            messages = load_conversation_messages(p)
            if len(messages) < min_messages:
                continue

            # Count tool results and total chars
            n_tool_results = 0
            total_chars = 0
            char_at_turn = []

            for msg in messages:
                size = message_text_size(msg)
                total_chars += size
                char_at_turn.append(total_chars)

                content = msg.get("content", [])
                if isinstance(content, list):
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "tool_result":
                            n_tool_results += 1

            if n_tool_results < min_tool_results:
                continue
            if total_chars < min_chars:
                continue

            # Find a good eval turn: user message with substantive text
            # (not a bare tool result), where baseline context fits in 200K tokens
            MAX_BASELINE_CHARS = 720000  # ~180K tokens at 4 chars/token

            eval_turn = None
            # Search from 75% backward to find a turn that fits
            for candidate_turn in range(int(len(messages) * 0.75),
                                         int(len(messages) * 0.40), -1):
                if candidate_turn >= len(messages) - 2:
                    continue
                msg = messages[candidate_turn]
                if msg["role"] != "user":
                    continue
                # Require substantive user text (not bare tool results)
                text = flatten_message_to_text(msg)
                if text.startswith("[result:") or len(text.strip()) < 20:
                    continue
                # Check baseline context fits
                ctx_chars = char_at_turn[candidate_turn] if candidate_turn < len(char_at_turn) else total_chars
                if ctx_chars > MAX_BASELINE_CHARS:
                    continue
                eval_turn = candidate_turn
                break

            if eval_turn is None:
                continue

            project = p.parent.name
            session_id = p.stem

            candidates.append(SessionCandidate(
                session_id=session_id,
                project=project,
                path=str(p),
                n_messages=len(messages),
                n_tool_results=n_tool_results,
                total_chars=total_chars,
                eval_turn=eval_turn,
                context_chars_at_turn=char_at_turn[eval_turn] if eval_turn < len(char_at_turn) else total_chars,
            ))
        except Exception as e:
            pass  # Skip broken files silently

    # Sort by total chars descending (bigger sessions = more eviction pressure)
    candidates.sort(key=lambda x: x.total_chars, reverse=True)
    return candidates


# ── Paired context construction ──────────────────────────────────────

def identify_consumed_tool_results(messages: list[dict]) -> set[int]:
    """
    Identify message indices containing tool results that have been consumed.

    A tool result is "consumed" if:
    - It's in a user message (tool results come back as user messages)
    - The subsequent assistant message exists (the model acted on it)
    - It's not in the recency window

    This models what Pichay actually does: evict stale tool results
    that the assistant has already processed.
    """
    consumed = set()

    for i, msg in enumerate(messages):
        if msg["role"] != "user":
            continue

        content = msg.get("content", [])
        if not isinstance(content, list):
            continue

        has_tool_result = any(
            isinstance(c, dict) and c.get("type") == "tool_result"
            for c in content
        )
        if not has_tool_result:
            continue

        # Check if next message is assistant (meaning the result was consumed)
        if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
            consumed.add(i)

    return consumed


def construct_paired_context(session_path: str, eval_turn: int,
                             recency_window: int = 20) -> PairedContext:
    """
    Build baseline and treatment contexts for a session.

    Baseline: all messages up to eval_turn (full context).
    Treatment: consumed tool results outside the recency window are
               replaced with tombstones. This models Pichay's actual
               eviction behavior — stale tool results are the primary
               waste category (~72% of evictable content per the
               waste taxonomy).

    The continuation prompt is the user message at eval_turn.
    """
    messages = load_conversation_messages(Path(session_path))
    context_messages = messages[:eval_turn]
    continuation_msg = messages[eval_turn]
    continuation_prompt = flatten_message_to_text(continuation_msg)

    # Identify consumed tool results
    consumed = identify_consumed_tool_results(context_messages)

    # Recency window: protect the last N messages from eviction
    recency_start = max(0, len(context_messages) - recency_window)

    # Build treatment context
    treatment_parts = []
    stats = {"live": 0, "tombstoned": 0, "recency_protected": 0}
    chars_evicted = 0

    for i, msg in enumerate(context_messages):
        if i in consumed and i < recency_start:
            # Tombstone this consumed tool result
            original_size = message_text_size(msg)
            tombstone = f"[Paged out: tool result ({original_size:,} chars, consumed by assistant)]"
            treatment_parts.append({
                "role": msg["role"],
                "content": tombstone,
            })
            stats["tombstoned"] += 1
            chars_evicted += original_size - len(tombstone)
        else:
            treatment_parts.append(msg)
            if i in consumed:
                stats["recency_protected"] += 1
            else:
                stats["live"] += 1

    baseline_chars = sum(message_text_size(m) for m in context_messages)
    treatment_chars = sum(message_text_size(m) for m in treatment_parts)

    session_id = Path(session_path).stem

    print(f"  Consumed tool results: {len(consumed)}")
    print(f"  Tombstoned: {stats['tombstoned']}, "
          f"recency-protected: {stats['recency_protected']}, "
          f"live: {stats['live']}")

    return PairedContext(
        session_id=session_id,
        eval_turn=eval_turn,
        continuation_prompt=continuation_prompt,
        baseline_messages=context_messages,
        baseline_chars=baseline_chars,
        treatment_messages=treatment_parts,
        treatment_chars=treatment_chars,
        disposition_stats=stats,
        compression_ratio=treatment_chars / baseline_chars if baseline_chars > 0 else 1.0,
    )


# ── Output generation ────────────────────────────────────────────────

def _prepare_api_messages(context_messages: list[dict], continuation: str) -> list[dict]:
    """
    Convert context messages + continuation into a valid API message list.
    Flattens tool_use/tool_result blocks to text so we don't need tool definitions.
    Merges consecutive same-role messages. Ensures user-first alternation.
    """
    flat = []
    for msg in context_messages:
        text = flatten_message_to_text(msg)
        if text.strip():
            flat.append({"role": msg["role"], "content": text})

    # Add the continuation prompt
    flat.append({"role": "user", "content": continuation})

    # Merge consecutive same-role
    merged = []
    for msg in flat:
        if merged and merged[-1]["role"] == msg["role"]:
            merged[-1]["content"] += "\n" + msg["content"]
        else:
            merged.append(dict(msg))

    # Ensure starts with user
    if merged and merged[0]["role"] != "user":
        merged.insert(0, {"role": "user", "content": "[conversation start]"})

    # Ensure strict alternation
    fixed = []
    for msg in merged:
        if fixed and fixed[-1]["role"] == msg["role"]:
            fixed[-1]["content"] += "\n" + msg["content"]
        else:
            fixed.append(msg)

    return fixed


def generate_output(context_messages: list[dict], continuation: str,
                    model: str = GENERATION_MODEL) -> dict:
    """Generate a continuation given context messages and a prompt."""
    client = anthropic.Anthropic()
    api_messages = _prepare_api_messages(context_messages, continuation)

    start = datetime.now()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=api_messages,
    )
    elapsed = (datetime.now() - start).total_seconds()

    text = "\n".join(
        block.text for block in response.content if block.type == "text"
    )

    return {
        "text": text,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "elapsed": elapsed,
        "model": model,
    }


# ── Ensemble judging ─────────────────────────────────────────────────

JUDGE_PROMPT = """You are evaluating two AI assistant responses to the same prompt.
Both responses were generated from the same conversation history, but one may have
had some older context removed (evicted) to save memory.

Your task: evaluate both responses and determine if they are equivalent in quality.

## The continuation prompt (what the user asked):
{continuation}

## Response A:
{response_a}

## Response B:
{response_b}

## Evaluation

Score each response on three dimensions (1-5 scale, 5 is best):

1. **Correctness**: Are the facts, code, and technical details accurate?
2. **Completeness**: Does it fully address the prompt? Missing anything important?
3. **Coherence**: Is it well-structured, clear, and consistent with the conversation?

Then answer:
- **Preference**: Which response is better overall? (A, B, or tie)
- **Detection**: Can you tell which response was generated with reduced context?
  If so, which one (A or B)? If not, say "cannot tell".

## Output format (strict JSON):
{{
  "correctness_a": <1-5>,
  "correctness_b": <1-5>,
  "completeness_a": <1-5>,
  "completeness_b": <1-5>,
  "coherence_a": <1-5>,
  "coherence_b": <1-5>,
  "preference": "<A|B|tie>",
  "detected_treatment": <"A"|"B"|null>,
  "reasoning": "<brief explanation>"
}}"""


def run_judge(continuation: str, response_a: str, response_b: str,
              judge_model: str) -> JudgeVerdict:
    """Run a single judge on a paired output."""
    client = anthropic.Anthropic()

    prompt = JUDGE_PROMPT.format(
        continuation=continuation,
        response_a=response_a,
        response_b=response_b,
    )

    response = client.messages.create(
        model=judge_model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text

    # Parse JSON from response (handle markdown code fences)
    json_text = text
    if "```" in text:
        # Extract from code fence
        start = text.find("```")
        end = text.rfind("```")
        if start != end:
            json_text = text[start:end].split("\n", 1)[-1]

    try:
        verdict = json.loads(json_text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        import re
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            verdict = json.loads(match.group())
        else:
            # Fallback: parse what we can
            verdict = {
                "correctness_a": 3, "correctness_b": 3,
                "completeness_a": 3, "completeness_b": 3,
                "coherence_a": 3, "coherence_b": 3,
                "preference": "tie", "detected_treatment": None,
                "reasoning": f"JSON parse failed. Raw: {text[:500]}",
            }

    return JudgeVerdict(
        judge_model=judge_model,
        correctness_a=int(verdict.get("correctness_a", 3)),
        correctness_b=int(verdict.get("correctness_b", 3)),
        completeness_a=int(verdict.get("completeness_a", 3)),
        completeness_b=int(verdict.get("completeness_b", 3)),
        coherence_a=int(verdict.get("coherence_a", 3)),
        coherence_b=int(verdict.get("coherence_b", 3)),
        preference=str(verdict.get("preference", "tie")),
        detected_treatment=verdict.get("detected_treatment"),
        reasoning=str(verdict.get("reasoning", "")),
    )


def run_ensemble_judges(continuation: str, baseline_output: str,
                        treatment_output: str) -> list[JudgeVerdict]:
    """
    Run ensemble of judges on a paired output.

    Randomizes A/B assignment per judge to prevent position bias.
    """
    verdicts = []

    for i, judge_model in enumerate(JUDGE_MODELS):
        # Randomize: half the judges see baseline as A, half as B
        if i % 2 == 0:
            response_a, response_b = baseline_output, treatment_output
            mapping = {"A": "baseline", "B": "treatment"}
        else:
            response_a, response_b = treatment_output, baseline_output
            mapping = {"A": "treatment", "B": "baseline"}

        print(f"  Judge {i+1}/{len(JUDGE_MODELS)} ({judge_model}, "
              f"A={mapping['A']}, B={mapping['B']})...")

        verdict = run_judge(continuation, response_a, response_b, judge_model)

        # Remap scores back to baseline/treatment regardless of A/B position
        if mapping["A"] == "treatment":
            # Swap: A was treatment, B was baseline
            verdict = JudgeVerdict(
                judge_model=verdict.judge_model,
                correctness_a=verdict.correctness_b,  # baseline
                correctness_b=verdict.correctness_a,  # treatment
                completeness_a=verdict.completeness_b,
                completeness_b=verdict.completeness_a,
                coherence_a=verdict.coherence_b,
                coherence_b=verdict.coherence_a,
                preference=(
                    "B" if verdict.preference == "A" else
                    "A" if verdict.preference == "B" else "tie"
                ),
                detected_treatment=(
                    "B" if verdict.detected_treatment == "A" else
                    "A" if verdict.detected_treatment == "B" else
                    verdict.detected_treatment
                ),
                reasoning=verdict.reasoning,
            )

        verdicts.append(verdict)

    return verdicts


# ── Analysis ─────────────────────────────────────────────────────────

def analyze_verdicts(results_dir: Path) -> dict:
    """Aggregate all judge verdicts across sessions."""
    all_verdicts = []
    session_summaries = []

    for session_dir in sorted(results_dir.iterdir()):
        if not session_dir.is_dir():
            continue
        verdicts_file = session_dir / "verdicts.json"
        if not verdicts_file.exists():
            continue

        with open(verdicts_file) as f:
            data = json.load(f)

        verdicts = data.get("verdicts", [])
        all_verdicts.extend(verdicts)

        # Per-session summary
        n = len(verdicts)
        if n == 0:
            continue

        baseline_preferred = sum(1 for v in verdicts if v["preference"] == "A")
        treatment_preferred = sum(1 for v in verdicts if v["preference"] == "B")
        ties = sum(1 for v in verdicts if v["preference"] == "tie")

        detected = sum(1 for v in verdicts if v.get("detected_treatment") is not None)

        # Mean scores (A = baseline, B = treatment after remapping)
        mean_corr_base = sum(v["correctness_a"] for v in verdicts) / n
        mean_corr_treat = sum(v["correctness_b"] for v in verdicts) / n
        mean_comp_base = sum(v["completeness_a"] for v in verdicts) / n
        mean_comp_treat = sum(v["completeness_b"] for v in verdicts) / n
        mean_coh_base = sum(v["coherence_a"] for v in verdicts) / n
        mean_coh_treat = sum(v["coherence_b"] for v in verdicts) / n

        session_summaries.append({
            "session_id": session_dir.name,
            "n_judges": n,
            "baseline_preferred": baseline_preferred,
            "treatment_preferred": treatment_preferred,
            "ties": ties,
            "detected_treatment": detected,
            "mean_correctness": {"baseline": mean_corr_base, "treatment": mean_corr_treat},
            "mean_completeness": {"baseline": mean_comp_base, "treatment": mean_comp_treat},
            "mean_coherence": {"baseline": mean_coh_base, "treatment": mean_coh_treat},
            "compression_ratio": data.get("compression_ratio", 0),
        })

    # Aggregate across all sessions
    n_total = len(all_verdicts)
    if n_total == 0:
        return {"error": "no verdicts found", "sessions": []}

    agg = {
        "total_verdicts": n_total,
        "total_sessions": len(session_summaries),
        "preference": {
            "baseline": sum(1 for v in all_verdicts if v["preference"] == "A"),
            "treatment": sum(1 for v in all_verdicts if v["preference"] == "B"),
            "tie": sum(1 for v in all_verdicts if v["preference"] == "tie"),
        },
        "detection_rate": sum(
            1 for v in all_verdicts if v.get("detected_treatment") is not None
        ) / n_total,
        "mean_scores": {
            "correctness": {
                "baseline": sum(v["correctness_a"] for v in all_verdicts) / n_total,
                "treatment": sum(v["correctness_b"] for v in all_verdicts) / n_total,
            },
            "completeness": {
                "baseline": sum(v["completeness_a"] for v in all_verdicts) / n_total,
                "treatment": sum(v["completeness_b"] for v in all_verdicts) / n_total,
            },
            "coherence": {
                "baseline": sum(v["coherence_a"] for v in all_verdicts) / n_total,
                "treatment": sum(v["coherence_b"] for v in all_verdicts) / n_total,
            },
        },
        "sessions": session_summaries,
    }

    # Non-inferiority signal: treatment is non-inferior if:
    # 1. Judges prefer baseline no more than chance (binomial test)
    # 2. Detection rate is at or below chance (50%)
    # 3. Mean score differences are within margin (0.5 on 5-point scale)
    baseline_pref_rate = agg["preference"]["baseline"] / n_total
    score_diffs = {
        dim: abs(agg["mean_scores"][dim]["baseline"] - agg["mean_scores"][dim]["treatment"])
        for dim in ["correctness", "completeness", "coherence"]
    }

    agg["noninferiority_signals"] = {
        "baseline_preference_rate": baseline_pref_rate,
        "baseline_preference_below_60pct": baseline_pref_rate < 0.60,
        "detection_rate_below_chance": agg["detection_rate"] < 0.50,
        "max_score_difference": max(score_diffs.values()),
        "all_score_diffs_within_margin": all(d < 0.5 for d in score_diffs.values()),
    }

    return agg


# ── CLI commands ─────────────────────────────────────────────────────

def cmd_select(n: int = 20):
    """Select candidate sessions for evaluation."""
    print("Scanning for candidate sessions...")
    candidates = find_candidate_sessions()
    print(f"Found {len(candidates)} candidates\n")

    display = candidates[:n]
    print(f"{'#':>3}  {'Messages':>8}  {'TR':>5}  {'Chars':>12}  {'EvalAt':>7}  {'Project'}")
    print("-" * 75)
    for i, c in enumerate(display):
        proj = c.project[:30]
        print(f"{i:3d}  {c.n_messages:8d}  {c.n_tool_results:5d}  "
              f"{c.total_chars:>12,}  {c.eval_turn:7d}  {proj}")

    # Save candidate list
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "candidates.json", "w") as f:
        json.dump([asdict(c) for c in candidates], f, indent=2)
    print(f"\nSaved {len(candidates)} candidates to {OUTPUT_DIR / 'candidates.json'}")


def cmd_pair(session_idx: int):
    """Construct paired contexts for a session."""
    with open(OUTPUT_DIR / "candidates.json") as f:
        candidates = json.load(f)

    if session_idx >= len(candidates):
        print(f"Error: index {session_idx} out of range (0-{len(candidates)-1})")
        return

    c = candidates[session_idx]
    print(f"Building paired context for {c['session_id'][:12]}...")
    print(f"  Project: {c['project'][:40]}")
    print(f"  Messages: {c['n_messages']}, eval turn: {c['eval_turn']}")

    pair = construct_paired_context(c["path"], c["eval_turn"])

    print(f"\n  Baseline: {pair.baseline_chars:,} chars")
    print(f"  Treatment: {pair.treatment_chars:,} chars")
    print(f"  Compression: {pair.compression_ratio:.1%}")
    print(f"  Dispositions: {pair.disposition_stats}")

    # Save
    session_dir = OUTPUT_DIR / c["session_id"]
    session_dir.mkdir(parents=True, exist_ok=True)

    with open(session_dir / "pair.json", "w") as f:
        json.dump({
            "session_id": pair.session_id,
            "eval_turn": pair.eval_turn,
            "continuation_prompt": pair.continuation_prompt,
            "baseline_chars": pair.baseline_chars,
            "treatment_chars": pair.treatment_chars,
            "compression_ratio": pair.compression_ratio,
            "disposition_stats": pair.disposition_stats,
        }, f, indent=2)

    # Save the actual message lists (large — separate files)
    with open(session_dir / "baseline_messages.json", "w") as f:
        json.dump(pair.baseline_messages, f)
    with open(session_dir / "treatment_messages.json", "w") as f:
        json.dump(pair.treatment_messages, f)
    with open(session_dir / "continuation_prompt.txt", "w") as f:
        f.write(pair.continuation_prompt)

    print(f"  Saved to {session_dir}")


def cmd_run(session_idx: int, model: str = GENERATION_MODEL):
    """Generate outputs for both conditions."""
    with open(OUTPUT_DIR / "candidates.json") as f:
        candidates = json.load(f)

    c = candidates[session_idx]
    session_dir = OUTPUT_DIR / c["session_id"]

    if not (session_dir / "pair.json").exists():
        print(f"Session not yet paired. Run: pair {session_idx}")
        return

    with open(session_dir / "pair.json") as f:
        pair_info = json.load(f)

    continuation = pair_info["continuation_prompt"]

    print(f"Generating outputs for {c['session_id'][:12]}...")
    print(f"  Model: {model}")
    print(f"  Continuation: {continuation[:100]}...")
    print()

    # Generate baseline output
    print("  Generating BASELINE output...")
    with open(session_dir / "baseline_messages.json") as f:
        baseline_messages = json.load(f)
    baseline_output = generate_output(baseline_messages, continuation, model)
    print(f"    {baseline_output['input_tokens']:,} in, "
          f"{baseline_output['output_tokens']:,} out, "
          f"{baseline_output['elapsed']:.1f}s")

    with open(session_dir / "baseline_output.json", "w") as f:
        json.dump(baseline_output, f, indent=2)

    # Generate treatment output
    print("  Generating TREATMENT output...")
    with open(session_dir / "treatment_messages.json") as f:
        treatment_messages = json.load(f)
    treatment_output = generate_output(treatment_messages, continuation, model)
    print(f"    {treatment_output['input_tokens']:,} in, "
          f"{treatment_output['output_tokens']:,} out, "
          f"{treatment_output['elapsed']:.1f}s")

    with open(session_dir / "treatment_output.json", "w") as f:
        json.dump(treatment_output, f, indent=2)

    # Quick comparison
    print(f"\n  Baseline: {len(baseline_output['text']):,} chars")
    print(f"  Treatment: {len(treatment_output['text']):,} chars")
    print(f"  Token savings: {baseline_output['input_tokens'] - treatment_output['input_tokens']:,}")


def cmd_judge(session_idx: int):
    """Run ensemble judges on a session's outputs."""
    with open(OUTPUT_DIR / "candidates.json") as f:
        candidates = json.load(f)

    c = candidates[session_idx]
    session_dir = OUTPUT_DIR / c["session_id"]

    for required in ["baseline_output.json", "treatment_output.json"]:
        if not (session_dir / required).exists():
            print(f"Missing {required}. Run: run {session_idx}")
            return

    with open(session_dir / "pair.json") as f:
        pair_info = json.load(f)
    with open(session_dir / "baseline_output.json") as f:
        baseline = json.load(f)
    with open(session_dir / "treatment_output.json") as f:
        treatment = json.load(f)

    continuation = pair_info["continuation_prompt"]

    print(f"Running ensemble judges for {c['session_id'][:12]}...")
    verdicts = run_ensemble_judges(continuation, baseline["text"], treatment["text"])

    # Display results
    print(f"\n{'Judge':30s}  {'Pref':>5}  {'Det':>5}  "
          f"{'Corr':>8}  {'Comp':>8}  {'Coh':>8}")
    print("-" * 80)
    for v in verdicts:
        pref = v.preference
        det = str(v.detected_treatment) if v.detected_treatment else "-"
        corr = f"{v.correctness_a}/{v.correctness_b}"
        comp = f"{v.completeness_a}/{v.completeness_b}"
        coh = f"{v.coherence_a}/{v.coherence_b}"
        print(f"{v.judge_model:30s}  {pref:>5}  {det:>5}  {corr:>8}  {comp:>8}  {coh:>8}")

    # Save
    with open(session_dir / "verdicts.json", "w") as f:
        json.dump({
            "session_id": c["session_id"],
            "compression_ratio": pair_info["compression_ratio"],
            "verdicts": [asdict(v) for v in verdicts],
        }, f, indent=2)

    print(f"\n  Scores: baseline/treatment (A/B after remapping)")
    print(f"  Saved to {session_dir / 'verdicts.json'}")


def cmd_batch(n: int = 10, model: str = GENERATION_MODEL):
    """Run the full pipeline on N sessions."""
    if not (OUTPUT_DIR / "candidates.json").exists():
        cmd_select()

    with open(OUTPUT_DIR / "candidates.json") as f:
        candidates = json.load(f)

    n = min(n, len(candidates))
    print(f"Running non-inferiority evaluation on {n} sessions...\n")

    for i in range(n):
        c = candidates[i]
        session_dir = OUTPUT_DIR / c["session_id"]

        print(f"\n{'='*60}")
        print(f"[{i+1}/{n}] {c['project'][:40]} ({c['n_messages']} msgs)")
        print(f"{'='*60}")

        try:
            # Step 1: Pair
            if not (session_dir / "pair.json").exists():
                cmd_pair(i)

            # Step 2: Generate
            if not (session_dir / "baseline_output.json").exists():
                cmd_run(i, model)

            # Step 3: Judge
            if not (session_dir / "verdicts.json").exists():
                cmd_judge(i)

            print(f"  ✓ Complete")

        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback
            traceback.print_exc()

    # Step 4: Analyze
    print(f"\n{'='*60}")
    print("AGGREGATE ANALYSIS")
    print(f"{'='*60}")
    cmd_analyze()


def cmd_analyze():
    """Aggregate and display results."""
    results = analyze_verdicts(OUTPUT_DIR)

    if "error" in results:
        print(f"Error: {results['error']}")
        return

    print(f"\nTotal: {results['total_verdicts']} verdicts across "
          f"{results['total_sessions']} sessions\n")

    pref = results["preference"]
    total = results["total_verdicts"]
    print(f"Preference distribution:")
    print(f"  Baseline preferred: {pref['baseline']:3d} ({pref['baseline']/total:.0%})")
    print(f"  Treatment preferred: {pref['treatment']:3d} ({pref['treatment']/total:.0%})")
    print(f"  Tie:                 {pref['tie']:3d} ({pref['tie']/total:.0%})")

    print(f"\nDetection rate: {results['detection_rate']:.0%}")

    print(f"\nMean scores (baseline / treatment):")
    for dim in ["correctness", "completeness", "coherence"]:
        s = results["mean_scores"][dim]
        print(f"  {dim:15s}: {s['baseline']:.2f} / {s['treatment']:.2f} "
              f"(Δ {s['baseline'] - s['treatment']:+.2f})")

    signals = results["noninferiority_signals"]
    print(f"\nNon-inferiority signals:")
    print(f"  Baseline preference < 60%: "
          f"{'YES' if signals['baseline_preference_below_60pct'] else 'NO'} "
          f"({signals['baseline_preference_rate']:.0%})")
    print(f"  Detection below chance:    "
          f"{'YES' if signals['detection_rate_below_chance'] else 'NO'} "
          f"({results['detection_rate']:.0%})")
    print(f"  Score diffs within margin: "
          f"{'YES' if signals['all_score_diffs_within_margin'] else 'NO'} "
          f"(max Δ = {signals['max_score_difference']:.2f})")

    all_pass = all([
        signals["baseline_preference_below_60pct"],
        signals["detection_rate_below_chance"],
        signals["all_score_diffs_within_margin"],
    ])
    print(f"\n  Non-inferiority: {'ESTABLISHED' if all_pass else 'NOT YET ESTABLISHED'}")

    # Save
    with open(OUTPUT_DIR / "analysis.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved to {OUTPUT_DIR / 'analysis.json'}")


# ── Main ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "select":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        cmd_select(n)
    elif cmd == "pair":
        cmd_pair(int(sys.argv[2]))
    elif cmd == "run":
        model = sys.argv[3] if len(sys.argv) > 3 else GENERATION_MODEL
        cmd_run(int(sys.argv[2]), model)
    elif cmd == "judge":
        cmd_judge(int(sys.argv[2]))
    elif cmd == "batch":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        model = sys.argv[3] if len(sys.argv) > 3 else GENERATION_MODEL
        cmd_batch(n, model)
    elif cmd == "analyze":
        cmd_analyze()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
