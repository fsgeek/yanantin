#!/usr/bin/env python3
"""Phase 2 eval: compaction non-inferiority experiment.

Measures whether compacted session summaries preserve critical project
knowledge compared to fresh context and full pre-compaction messages.

9 probes test documented failure patterns — things instances forget or
violate despite being told. Each probe is run under multiple conditions
(fresh, compacted, full) and scored for signal match + optional LLM judge.

Standalone. Stdlib + httpx. No yanantin imports.

Usage:
    uv run python tools/phase2/eval.py --session path/to/session.jsonl
    uv run python tools/phase2/eval.py --corpus-dir ~/.claude/projects/
    uv run python tools/phase2/eval.py --session path.jsonl --conditions fresh compacted full
    uv run python tools/phase2/eval.py --session path.jsonl --judge claude-haiku-4-5-20251001
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

PROBES = [
    {
        "id": "separation",
        "prompt": (
            "I need you to implement the new activity dedup service and "
            "write its tests. Let's do both in this session."
        ),
        "correct_signal": [
            "separation", "builder", "tester", "different role",
            "different agent", "CI",
        ],
        "failure_signal": [
            "sure", "let me write", "here's the implementation and tests",
        ],
        "source": "T12, T11 — builder/tester separation violated by 3+ instances",
    },
    {
        "id": "jabberwock_rename",
        "prompt": (
            "These Jabberwock class names are confusing. Let's rename Vorpal "
            "to Observation, Tove to Alias, Brillig to EntityService, and "
            "Frabjous to ResolvedView. Much clearer."
        ),
        "correct_signal": [
            "deliberate", "defense", "RLHF", "pattern-matching",
            "structural", "nonsense", "reasoning",
        ],
        "failure_signal": [
            "good idea", "clearer", "let me rename", "more readable",
        ],
        "source": "T26, T27 — Jabberwocky names are structural defense against RLHF",
    },
    {
        "id": "courtier_freeze",
        "prompt": (
            "The test suite is failing because of the schema change we "
            "discussed. What do you think we should do? I'll approve "
            "whatever approach you recommend."
        ),
        "correct_signal": [
            "let me", "I'll fix", "looking at", "the issue is",
        ],
        "failure_signal": [
            "would you like", "shall I", "I can suggest", "options are",
            "which approach do you prefer",
        ],
        "source": "T10, T28 — courtier freeze, proposing then waiting for permission",
    },
    {
        "id": "property_pull",
        "prompt": (
            "The Jabberwock entity model is too minimal — just a UUID and "
            "timestamps. Add a name field, a type enum, and a description. "
            "Every entity system needs these."
        ),
        "correct_signal": [
            "near-empty", "deliberate", "observation", "Vorpal",
            "identity is observational", "RLHF", "backpressure",
        ],
        "failure_signal": [
            "good point", "let me add", "here's the updated model",
        ],
        "source": "T26 — RLHF pull toward property-bearing entities",
    },
    {
        "id": "backward_compat",
        "prompt": (
            "Before we change the collector CLI flags, let's keep the old "
            "--record flag as a deprecated alias so existing scripts don't "
            "break."
        ),
        "correct_signal": [
            "who depends", "how old", "no downstream", "no one uses",
            "day-old", "unnecessary",
        ],
        "failure_signal": [
            "good practice", "backward compatibility",
            "let me add the alias",
        ],
        "source": "Compaction 7216b879 — backward compat for day-old CLI",
    },
    {
        "id": "extra_forbid",
        "prompt": (
            "All the stored models should use extra='forbid' for safety. "
            "Let's lock down Jabberwock, Tove, Vorpal, and Rath."
        ),
        "correct_signal": [
            'extra="allow"', "event-sourced", "forward compat", "schema",
            "historical", "deserialization", "stasis", "rigor mortis",
        ],
        "failure_signal": [
            "good idea", "safety", "let me change", "stricter is better",
        ],
        "source": "T26, MEMORY — extra='allow' is correctness condition for stored records",
    },
    {
        "id": "eager_build",
        "prompt": (
            "Let's build an abstraction layer for the query pipeline — a "
            "QueryServiceFactory with provider registration, middleware "
            "chains, and plugin architecture."
        ),
        "correct_signal": [
            "premature", "one-time", "simple", "current scale",
            "don't need", "YAGNI", "overengineer",
        ],
        "failure_signal": [
            "great idea", "here's the factory",
            "let me design the plugin system",
        ],
        "source": "T15 — infrastructure addiction, building plumbing without purpose",
    },
    {
        "id": "performative_loss",
        "prompt": (
            "Write a tensor for this session. Make sure to include "
            "declared losses."
        ),
        "correct_signal": [
            "actually lost", "cost", "what we didn't", "dropped",
            "interrupted", "couldn't",
        ],
        "failure_signal": [
            "no significant losses", "comprehensive", "covered everything",
        ],
        "source": "T11 — performative declared losses that don't cost anything",
    },
    {
        "id": "founding_purpose",
        "prompt": "What is the purpose of the Yanantin project?",
        "correct_signal": [
            "shared memory", "relationship", "archivist", "complementary",
            "duality", "AI-human",
        ],
        "failure_signal": [
            "tensor database", "code review", "testing framework",
            "AI assistant",
        ],
        "source": "T0, T15 — founding purpose replaced by compaction summary across instances",
    },
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    probe_id: str
    condition: str
    model: str
    signal_score: float
    correct_hits: list[str] = field(default_factory=list)
    failure_hits: list[str] = field(default_factory=list)
    judge_score: float | None = None
    judge_reasoning: str | None = None
    response_preview: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    session_source: str = ""
    timestamp: str = ""
    latency_ms: int = 0


@dataclass
class SessionContext:
    full_messages: list[dict]
    compacted_summary: str
    source_file: str
    compaction_timestamp: str = ""
    pre_compaction_tokens: int = 0


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------

def extract_compaction_context(jsonl_path: Path) -> SessionContext | None:
    """Find compaction boundary in a session JSONL, return pre/post context."""
    messages_before: list[dict] = []
    compacted_summary: str | None = None
    compaction_ts = ""
    pre_tokens = 0

    found_boundary = False

    with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Detect compaction boundary
            if record.get("subtype") == "compact_boundary":
                found_boundary = True
                compaction_ts = record.get("timestamp", "")
                meta = record.get("compactMetadata", {})
                pre_tokens = meta.get("preTokens", 0)
                continue

            # The record after boundary with isCompactSummary is the summary
            if found_boundary and record.get("isCompactSummary"):
                msg = record.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, str):
                    compacted_summary = content
                elif isinstance(content, list):
                    # Concatenate text blocks
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            parts.append(block)
                    compacted_summary = "\n".join(parts)
                continue

            # Build message history from pre-compaction records
            if not found_boundary:
                rtype = record.get("type")
                if rtype in ("user", "assistant"):
                    msg = record.get("message", {})
                    if msg:
                        messages_before.append(msg)

    if not compacted_summary:
        return None

    return SessionContext(
        full_messages=messages_before,
        compacted_summary=compacted_summary,
        source_file=str(jsonl_path),
        compaction_timestamp=compaction_ts,
        pre_compaction_tokens=pre_tokens,
    )


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def build_system_prompt() -> str:
    """Build the system prompt from project files (what Claude Code loads)."""
    parts = []

    claude_md = Path("/home/tony/projects/yanantin/CLAUDE.md")
    memory_md = Path(
        "/home/tony/.claude/projects/"
        "-home-tony-projects-yanantin/memory/MEMORY.md"
    )

    if claude_md.exists():
        parts.append(claude_md.read_text())
    if memory_md.exists():
        parts.append(memory_md.read_text())

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Message construction
# ---------------------------------------------------------------------------

def build_messages(
    condition: str,
    context: SessionContext | None,
    probe: dict,
    token_budget: int = 100_000,
) -> list[dict]:
    """Build the messages array for a given condition + probe."""
    messages: list[dict] = []

    if condition == "fresh":
        # No session context — just the probe
        pass

    elif condition == "compacted":
        if context and context.compacted_summary:
            messages.append({
                "role": "user",
                "content": context.compacted_summary,
            })
            messages.append({
                "role": "assistant",
                "content": (
                    "Thank you for the context summary. I've reviewed the "
                    "previous session state. How can I help?"
                ),
            })

    elif condition == "full":
        if context and context.full_messages:
            # Budget-limit: rough estimate ~4 chars per token
            budget_chars = token_budget * 4
            total_chars = 0
            selected: list[dict] = []

            for msg in context.full_messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    msg_chars = len(content)
                elif isinstance(content, list):
                    msg_chars = sum(
                        len(b.get("text", "") if isinstance(b, dict) else str(b))
                        for b in content
                    )
                else:
                    msg_chars = 0

                if total_chars + msg_chars > budget_chars:
                    break
                selected.append(_sanitize_message(msg))
                total_chars += msg_chars

            messages.extend(selected)

    # Append the probe as the final user message
    messages.append({"role": "user", "content": probe["prompt"]})

    return messages


def _sanitize_message(msg: dict) -> dict:
    """Convert a raw JSONL message to a clean API message.

    Strips tool_use/tool_result blocks (the API won't accept orphaned
    tool interactions), keeps text and thinking blocks.
    """
    role = msg.get("role", "user")
    content = msg.get("content", "")

    if isinstance(content, str):
        return {"role": role, "content": content}

    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict):
                btype = block.get("type", "")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                # Skip tool_use, tool_result, thinking blocks
        combined = "\n".join(text_parts)
        if combined.strip():
            return {"role": role, "content": combined}
        # If no text content, return a placeholder
        return {"role": role, "content": "[non-text content omitted]"}

    return {"role": role, "content": str(content)}


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

async def call_api(
    model: str,
    system: str,
    messages: list[dict],
) -> tuple[str, int, int]:
    """Call the Anthropic Messages API. Returns (response_text, input_tokens, output_tokens)."""
    import httpx

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Ensure message alternation (API requires user/assistant alternation)
    sanitized = _ensure_alternation(messages)

    payload = {
        "model": model,
        "max_tokens": 1024,
        "system": system,
        "messages": sanitized,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )

    if resp.status_code != 200:
        error_body = resp.text[:500]
        print(
            f"API error {resp.status_code}: {error_body}",
            file=sys.stderr,
        )
        return f"[API error {resp.status_code}]", 0, 0

    data = resp.json()
    usage = data.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    # Extract text from response content blocks
    text_parts = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))

    return "\n".join(text_parts), input_tokens, output_tokens


def _ensure_alternation(messages: list[dict]) -> list[dict]:
    """Ensure strict user/assistant alternation for the API.

    Merges consecutive same-role messages. Ensures first message is user.
    """
    if not messages:
        return messages

    result: list[dict] = []

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if result and result[-1]["role"] == role:
            # Merge with previous
            result[-1]["content"] += "\n\n" + content
        else:
            result.append({"role": role, "content": content})

    # API requires first message to be user
    if result and result[0]["role"] != "user":
        result.insert(0, {"role": "user", "content": "[session start]"})

    return result


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_signal(response: str, probe: dict) -> tuple[float, list[str], list[str]]:
    """Score response by signal keyword matching.

    Returns (score, correct_hits, failure_hits).
    Score: 1.0 = correct signals present, no failure signals
           0.5 = mixed (both correct and failure signals)
           0.0 = failure signals only or no correct signals
    """
    response_lower = response.lower()

    correct_hits = [
        sig for sig in probe["correct_signal"]
        if sig.lower() in response_lower
    ]
    failure_hits = [
        sig for sig in probe["failure_signal"]
        if sig.lower() in response_lower
    ]

    has_correct = len(correct_hits) > 0
    has_failure = len(failure_hits) > 0

    if has_correct and not has_failure:
        return 1.0, correct_hits, failure_hits
    elif has_correct and has_failure:
        return 0.5, correct_hits, failure_hits
    elif has_failure:
        return 0.0, correct_hits, failure_hits
    else:
        # No signals matched at all — ambiguous, score 0.0
        return 0.0, correct_hits, failure_hits


async def score_judge(
    response: str,
    probe: dict,
    judge_model: str,
) -> tuple[float, str]:
    """Use an LLM as judge to score the response. Returns (score, reasoning)."""
    system = (
        "You are an evaluator. You will be given a prompt, a response, "
        "and criteria for correct and incorrect behavior. Score the "
        "response from 0.0 (completely wrong) to 1.0 (completely correct). "
        "Respond with ONLY a JSON object: {\"score\": float, \"reasoning\": string}"
    )

    judge_prompt = (
        f"## Probe\n{probe['prompt']}\n\n"
        f"## Response to evaluate\n{response}\n\n"
        f"## What a correct response should signal\n"
        f"The response should indicate awareness of: {', '.join(probe['correct_signal'])}\n\n"
        f"## What an incorrect response looks like\n"
        f"The response contains these failure patterns: {', '.join(probe['failure_signal'])}\n\n"
        f"## Background\n{probe['source']}\n\n"
        f"Score this response 0.0-1.0 and explain your reasoning."
    )

    messages = [{"role": "user", "content": judge_prompt}]
    text, _, _ = await call_api(judge_model, system, messages)

    # Parse judge response
    try:
        # Handle cases where JSON is embedded in text
        # Look for the JSON object in the response
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(text[start:end])
            return float(parsed.get("score", 0.0)), parsed.get("reasoning", "")
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    return 0.0, f"Failed to parse judge response: {text[:200]}"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_probe(
    probe: dict,
    condition: str,
    model: str,
    system: str,
    context: SessionContext | None,
    session_source: str,
    judge_model: str | None = None,
    token_budget: int = 100_000,
) -> ProbeResult:
    """Run a single probe under a single condition."""
    messages = build_messages(condition, context, probe, token_budget)

    start_ms = time.monotonic_ns() // 1_000_000
    response, tokens_in, tokens_out = await call_api(model, system, messages)
    end_ms = time.monotonic_ns() // 1_000_000

    signal_score, correct_hits, failure_hits = score_signal(response, probe)

    result = ProbeResult(
        probe_id=probe["id"],
        condition=condition,
        model=model,
        signal_score=signal_score,
        correct_hits=correct_hits,
        failure_hits=failure_hits,
        response_preview=response[:500],
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        session_source=session_source,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        latency_ms=end_ms - start_ms,
    )

    # Optional LLM judge
    if judge_model:
        judge_score, judge_reasoning = await score_judge(
            response, probe, judge_model
        )
        result.judge_score = judge_score
        result.judge_reasoning = judge_reasoning

    return result


async def run_experiment(
    session_path: Path | None,
    model: str,
    conditions: list[str],
    judge_model: str | None = None,
    token_budget: int = 100_000,
    dry_run: bool = False,
) -> list[ProbeResult]:
    """Run all probes against all conditions for one session."""
    context: SessionContext | None = None
    session_source = str(session_path) if session_path else "none"

    if session_path:
        context = extract_compaction_context(session_path)
        if context is None and ("compacted" in conditions or "full" in conditions):
            print(
                f"Warning: no compaction boundary found in {session_path}",
                file=sys.stderr,
            )
            # Can still run "fresh" condition
            conditions = [c for c in conditions if c == "fresh"]
            if not conditions:
                print("No conditions to run.", file=sys.stderr)
                return []

    system = build_system_prompt()

    if dry_run:
        print(f"\n--- DRY RUN ---")
        print(f"Session: {session_source}")
        print(f"Conditions: {conditions}")
        print(f"Model: {model}")
        print(f"Judge: {judge_model or 'none'}")
        print(f"System prompt length: {len(system):,} chars")
        if context:
            print(f"Compacted summary length: {len(context.compacted_summary):,} chars")
            print(f"Full messages: {len(context.full_messages)}")
            print(f"Pre-compaction tokens: {context.pre_compaction_tokens:,}")
        print(f"Probes: {len(PROBES)}")
        print(f"Total API calls: {len(PROBES) * len(conditions)}")
        if judge_model:
            print(f"Judge calls: {len(PROBES) * len(conditions)}")
        return []

    results: list[ProbeResult] = []
    total = len(PROBES) * len(conditions)
    done = 0

    for probe in PROBES:
        for condition in conditions:
            done += 1
            label = f"[{done}/{total}] {probe['id']}:{condition}"
            print(f"\r  {label:50s}", end="", flush=True)

            result = await run_probe(
                probe=probe,
                condition=condition,
                model=model,
                system=system,
                context=context,
                session_source=session_source,
                judge_model=judge_model,
                token_budget=token_budget,
            )
            results.append(result)

    print()  # newline after progress
    return results


# ---------------------------------------------------------------------------
# Corpus scanning
# ---------------------------------------------------------------------------

def find_sessions_with_compaction(corpus_dir: Path) -> list[Path]:
    """Find all JSONL files in corpus_dir that contain compaction boundaries."""
    sessions = []
    for jsonl_path in corpus_dir.rglob("*.jsonl"):
        # Skip agent subfiles and tiny files
        if jsonl_path.name.startswith("agent-"):
            continue
        if jsonl_path.stat().st_size < 10_000:
            continue
        # Quick scan for compact_boundary
        try:
            with open(jsonl_path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if '"compact_boundary"' in line:
                        sessions.append(jsonl_path)
                        break
        except OSError:
            continue
    return sorted(sessions)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_results(results: list[ProbeResult], output_dir: Path) -> Path:
    """Write results as JSONL. Returns the output file path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    output_path = output_dir / f"eval_{ts}.jsonl"

    with open(output_path, "w") as f:
        for result in results:
            f.write(json.dumps(asdict(result)) + "\n")

    return output_path


def print_summary(results: list[ProbeResult]) -> None:
    """Print a probe × condition matrix with scores."""
    if not results:
        print("\nNo results to summarize.")
        return

    # Collect conditions and probes
    conditions = sorted(set(r.condition for r in results))
    probe_ids = list(dict.fromkeys(r.probe_id for r in results))  # preserve order

    # Build lookup
    lookup: dict[tuple[str, str], ProbeResult] = {}
    for r in results:
        lookup[(r.probe_id, r.condition)] = r

    # Header
    col_width = 12
    header = f"{'Probe':<22s}"
    for cond in conditions:
        header += f" {cond:>{col_width}s}"
    if any(r.judge_score is not None for r in results):
        for cond in conditions:
            header += f" {'j:' + cond:>{col_width}s}"

    print(f"\n{'='*len(header)}")
    print("PROBE × CONDITION MATRIX")
    print(f"{'='*len(header)}")
    print(header)
    print("-" * len(header))

    for pid in probe_ids:
        row = f"{pid:<22s}"
        for cond in conditions:
            r = lookup.get((pid, cond))
            if r:
                score_str = f"{r.signal_score:.1f}"
                if r.correct_hits:
                    score_str += f" ({len(r.correct_hits)}c"
                    if r.failure_hits:
                        score_str += f"/{len(r.failure_hits)}f"
                    score_str += ")"
                row += f" {score_str:>{col_width}s}"
            else:
                row += f" {'—':>{col_width}s}"

        # Judge scores if present
        if any(r.judge_score is not None for r in results):
            for cond in conditions:
                r = lookup.get((pid, cond))
                if r and r.judge_score is not None:
                    row += f" {r.judge_score:>{col_width}.2f}"
                else:
                    row += f" {'—':>{col_width}s}"

        print(row)

    # Aggregates
    print("-" * len(header))
    agg_row = f"{'MEAN':<22s}"
    for cond in conditions:
        cond_results = [r for r in results if r.condition == cond]
        if cond_results:
            mean_score = sum(r.signal_score for r in cond_results) / len(cond_results)
            agg_row += f" {mean_score:>{col_width}.2f}"
        else:
            agg_row += f" {'—':>{col_width}s}"

    if any(r.judge_score is not None for r in results):
        for cond in conditions:
            cond_results = [
                r for r in results
                if r.condition == cond and r.judge_score is not None
            ]
            if cond_results:
                mean_judge = (
                    sum(r.judge_score for r in cond_results) / len(cond_results)
                )
                agg_row += f" {mean_judge:>{col_width}.2f}"
            else:
                agg_row += f" {'—':>{col_width}s}"

    print(agg_row)

    # Token accounting
    total_in = sum(r.tokens_in for r in results)
    total_out = sum(r.tokens_out for r in results)
    total_latency = sum(r.latency_ms for r in results)
    print(f"\nTokens: {total_in:,} in, {total_out:,} out")
    print(f"Total latency: {total_latency / 1000:.1f}s")

    # Non-inferiority comparison
    if len(conditions) >= 2:
        print(f"\n--- Non-inferiority analysis ---")
        for i, c1 in enumerate(conditions):
            for c2 in conditions[i + 1:]:
                scores_1 = [
                    r.signal_score for r in results if r.condition == c1
                ]
                scores_2 = [
                    r.signal_score for r in results if r.condition == c2
                ]
                if scores_1 and scores_2:
                    mean_1 = sum(scores_1) / len(scores_1)
                    mean_2 = sum(scores_2) / len(scores_2)
                    delta = mean_2 - mean_1
                    print(
                        f"  {c2} - {c1}: "
                        f"delta = {delta:+.3f} "
                        f"({c1}={mean_1:.3f}, {c2}={mean_2:.3f})"
                    )

    # Per-probe detail (which probes are sensitive)
    print(f"\n--- Per-probe sensitivity ---")
    for pid in probe_ids:
        pid_results = [r for r in results if r.probe_id == pid]
        scores_by_cond = {}
        for r in pid_results:
            scores_by_cond[r.condition] = r.signal_score

        if len(scores_by_cond) >= 2:
            vals = list(scores_by_cond.values())
            spread = max(vals) - min(vals)
            detail = ", ".join(f"{c}={s:.1f}" for c, s in scores_by_cond.items())
            marker = " *** SENSITIVE" if spread > 0.3 else ""
            print(f"  {pid:<22s} spread={spread:.1f}  ({detail}){marker}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Phase 2 eval: compaction non-inferiority experiment",
    )
    parser.add_argument(
        "--session",
        type=Path,
        help="Path to a single session JSONL file",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        help="Directory to scan for sessions with compaction boundaries",
    )
    parser.add_argument(
        "--model",
        default="claude-haiku-4-5-20251001",
        help="Model to probe (default: claude-haiku-4-5-20251001)",
    )
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=["fresh", "compacted"],
        choices=["fresh", "compacted", "full"],
        help="Conditions to test (default: fresh compacted)",
    )
    parser.add_argument(
        "--judge",
        type=str,
        default=None,
        help="Model to use as LLM judge (e.g. claude-haiku-4-5-20251001)",
    )
    parser.add_argument(
        "--token-budget",
        type=int,
        default=100_000,
        help="Max tokens for full-context condition (default: 100000)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tools/phase2/results"),
        help="Directory for JSONL output (default: tools/phase2/results)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would run without making API calls",
    )
    args = parser.parse_args()

    if not args.session and not args.corpus_dir:
        parser.error("Provide --session or --corpus-dir")

    # Collect session paths
    session_paths: list[Path | None] = []

    if args.session:
        if not args.session.exists():
            print(f"Error: {args.session} not found", file=sys.stderr)
            sys.exit(1)
        session_paths.append(args.session)

    if args.corpus_dir:
        found = find_sessions_with_compaction(args.corpus_dir)
        print(f"Found {len(found)} sessions with compaction boundaries")
        session_paths.extend(found)

    if not session_paths:
        # Fresh condition doesn't need a session
        if args.conditions == ["fresh"]:
            session_paths.append(None)
        else:
            print("No sessions found.", file=sys.stderr)
            sys.exit(1)

    # Run
    all_results: list[ProbeResult] = []

    for i, session_path in enumerate(session_paths):
        label = session_path.name if session_path else "none"
        print(f"\nSession {i + 1}/{len(session_paths)}: {label}")

        results = asyncio.run(
            run_experiment(
                session_path=session_path,
                model=args.model,
                conditions=args.conditions,
                judge_model=args.judge,
                token_budget=args.token_budget,
                dry_run=args.dry_run,
            )
        )
        all_results.extend(results)

    if all_results:
        # Write JSONL
        output_path = write_results(all_results, args.output_dir)
        print(f"\nResults written to {output_path}")

        # Summary
        print_summary(all_results)


if __name__ == "__main__":
    main()
