#!/usr/bin/env python3
"""
Compaction quality experiment.

Tests whether pre-cleaning tool results (as Pichay does) improves the
quality of conversation compaction summaries produced by Claude Code.

Design:
  1. Load sessions that contain compact_boundary events
  2. Reconstruct the pre-compaction message list
  3. Identify "dead" tool results (large results never re-referenced)
  4. Produce two versions: raw messages and cleaned messages
  5. Run both through the Claude Code compaction prompt
  6. Extract reasoning anchors from original conversation
  7. Test whether each anchor is recoverable from each summary

Usage:
  python compaction_experiment.py survey          # list available sessions
  python compaction_experiment.py extract <idx>   # extract one session pair
  python compaction_experiment.py run <idx>       # run compaction on both versions
  python compaction_experiment.py evaluate <idx>  # score reasoning recall
  python compaction_experiment.py batch [N]       # run full pipeline on N sessions
"""

import json
import os
import sys
import hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


# ── Session loading ──────────────────────────────────────────────────

PROJECTS_DIR = Path.home() / ".claude" / "projects"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "compaction_experiment"


@dataclass
class SessionInfo:
    path: str
    project: str
    session_id: str
    total_records: int
    compact_boundary_idx: int
    tool_results_before: int
    tool_result_bytes: int
    compaction_count: int


def find_compacted_sessions() -> list[SessionInfo]:
    """Find all sessions with compact_boundary events."""
    results = []
    for p in PROJECTS_DIR.rglob("*.jsonl"):
        try:
            records = []
            compactions = []
            with open(p) as f:
                for i, line in enumerate(f):
                    r = json.loads(line)
                    records.append(r)
                    if r.get("subtype") == "compact_boundary":
                        compactions.append(i)

            if not compactions:
                continue

            # Stats for first compaction
            cb_idx = compactions[0]
            tr_count = 0
            tr_size = 0
            for r in records[:cb_idx]:
                if r.get("type") == "user":
                    content = r.get("message", {}).get("content", [])
                    if isinstance(content, list):
                        for c in content:
                            if isinstance(c, dict) and c.get("type") == "tool_result":
                                tr_count += 1
                                rc = c.get("content", "")
                                tr_size += len(str(rc))

            project = str(p.parent.name)
            session_id = p.stem

            results.append(SessionInfo(
                path=str(p),
                project=project,
                session_id=session_id,
                total_records=len(records),
                compact_boundary_idx=cb_idx,
                tool_results_before=tr_count,
                tool_result_bytes=tr_size,
                compaction_count=len(compactions),
            ))
        except Exception as e:
            print(f"  error reading {p}: {e}", file=sys.stderr)

    results.sort(key=lambda x: x.tool_result_bytes, reverse=True)
    return results


# ── Message reconstruction ───────────────────────────────────────────

def load_pre_compaction_messages(session_path: str, cb_idx: int) -> list[dict]:
    """
    Reconstruct the API message list from session records up to compaction.
    Returns list of {"role": ..., "content": ...} dicts.
    Skips non-message records (file-history-snapshot, progress, queue-operation).
    """
    messages = []
    with open(session_path) as f:
        for i, line in enumerate(f):
            if i >= cb_idx:
                break
            r = json.loads(line)
            rtype = r.get("type")
            if rtype in ("assistant", "user"):
                msg = r.get("message", {})
                if msg.get("role") and msg.get("content"):
                    messages.append({
                        "role": msg["role"],
                        "content": msg["content"],
                    })
            elif rtype == "system":
                # System messages become system role
                msg = r.get("message", {})
                if msg.get("content"):
                    messages.append({
                        "role": "system",
                        "content": msg["content"],
                    })
    return messages


def load_actual_compaction(session_path: str, cb_idx: int) -> Optional[str]:
    """Load the actual compaction summary that Claude Code produced."""
    with open(session_path) as f:
        for i, line in enumerate(f):
            if i == cb_idx + 1:
                r = json.loads(line)
                content = r.get("message", {}).get("content", "")
                if isinstance(content, list):
                    parts = []
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            parts.append(c["text"])
                        elif isinstance(c, str):
                            parts.append(c)
                    return "\n".join(parts)
                return str(content)
    return None


# ── Dead tool result identification ──────────────────────────────────

def _get_text_content(msg: dict) -> str:
    """Extract all text from a message's content."""
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, dict):
                if c.get("type") == "text":
                    parts.append(c.get("text", ""))
                elif c.get("type") == "tool_result":
                    # Don't include tool result content in "text" —
                    # we're looking for assistant references TO results
                    pass
        return "\n".join(parts)
    return ""


def _tool_result_text(content) -> str:
    """Extract text from tool_result content field."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, str):
                parts.append(c)
            elif isinstance(c, dict) and c.get("type") == "text":
                parts.append(c.get("text", ""))
        return "\n".join(parts)
    return str(content)


def _build_tool_id_to_name(messages: list[dict]) -> dict[str, str]:
    """Map tool_use_id -> tool name from assistant messages."""
    mapping = {}
    for msg in messages:
        if msg["role"] != "assistant":
            continue
        content = msg.get("content", [])
        if isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    mapping[c["id"]] = c.get("name", "unknown")
    return mapping


@dataclass
class ToolResultInfo:
    tool_use_id: str
    tool_name: str
    content_size: int
    content_text: str
    msg_index: int  # index in messages list
    is_dead: bool = False


def identify_dead_tool_results(
    messages: list[dict],
    min_size: int = 500,
    reference_window: int = 40,  # chars to check for substring matches
) -> list[ToolResultInfo]:
    """
    Identify tool results that are large but never re-referenced.

    A tool result is "dead" if:
      - Its content is > min_size chars
      - No subsequent assistant message contains any distinctive substring
        from the result (sampled at multiple positions)

    Returns all tool results with is_dead flag set.
    """
    id_to_name = _build_tool_id_to_name(messages)
    tool_results: list[ToolResultInfo] = []

    # First pass: collect all tool results
    for i, msg in enumerate(messages):
        if msg["role"] != "user":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for c in content:
            if not isinstance(c, dict) or c.get("type") != "tool_result":
                continue
            tr_text = _tool_result_text(c.get("content", ""))
            tool_results.append(ToolResultInfo(
                tool_use_id=c.get("tool_use_id", ""),
                tool_name=id_to_name.get(c.get("tool_use_id", ""), "unknown"),
                content_size=len(tr_text),
                content_text=tr_text,
                msg_index=i,
            ))

    # Second pass: check references in subsequent assistant messages
    for tr in tool_results:
        if tr.content_size < min_size:
            continue  # Small results aren't worth evicting

        # Build reference strings: sample distinctive substrings from the result
        text = tr.content_text
        ref_strings = set()

        # Sample at regular intervals
        step = max(1, len(text) // 10)
        for pos in range(0, len(text) - reference_window, step):
            candidate = text[pos:pos + reference_window].strip()
            # Skip if it's mostly whitespace or very generic
            if len(candidate) >= 15 and not candidate.isspace():
                ref_strings.add(candidate)

        if not ref_strings:
            continue

        # Check if any subsequent assistant message references this content
        referenced = False
        for msg in messages[tr.msg_index + 1:]:
            if msg["role"] != "assistant":
                continue
            assistant_text = _get_text_content(msg)
            for ref in ref_strings:
                if ref in assistant_text:
                    referenced = True
                    break
            if referenced:
                break

        tr.is_dead = not referenced

    return tool_results


# ── Message cleaning ─────────────────────────────────────────────────

EVICTION_STUB = "[Tool result evicted — content not referenced in subsequent conversation]"


def clean_messages(messages: list[dict], dead_results: list[ToolResultInfo]) -> list[dict]:
    """
    Replace dead tool result content with eviction stubs.
    Returns a new message list (deep copy with modifications).
    """
    dead_ids = {tr.tool_use_id for tr in dead_results if tr.is_dead}
    if not dead_ids:
        return messages  # Nothing to clean

    cleaned = []
    for msg in messages:
        if msg["role"] != "user":
            cleaned.append(msg)
            continue

        content = msg.get("content", [])
        if not isinstance(content, list):
            cleaned.append(msg)
            continue

        new_content = []
        modified = False
        for c in content:
            if isinstance(c, dict) and c.get("type") == "tool_result":
                if c.get("tool_use_id") in dead_ids:
                    new_c = dict(c)
                    new_c["content"] = EVICTION_STUB
                    new_content.append(new_c)
                    modified = True
                else:
                    new_content.append(c)
            else:
                new_content.append(c)

        if modified:
            cleaned.append({"role": msg["role"], "content": new_content})
        else:
            cleaned.append(msg)

    return cleaned


# ── Compaction prompt ────────────────────────────────────────────────

COMPACTION_PROMPT = """<summary-prompt>
Provide a detailed summary of the conversation so far in a structured format that will help you continue the conversation effectively if this summary replaces the full conversation history. Focus on preserving ALL information needed to continue the conversation without any loss of context.

## Instructions:
1. First, analyze the conversation chronologically
2. Then create a structured summary following the format below
3. Preserve all specific details, file names, code snippets, and technical decisions
4. Maintain the user's original intent and any constraints they specified

<analysis>
[Chronological analysis of the conversation. Include everything that was said and done. It is better to include too much than too little information. Be comprehensive and VERY detailed.]
</analysis>

## Primary Request and Intent
[What the user originally asked for and their underlying goal]

## Key Technical Concepts and Decisions
[List all important technical decisions, trade-offs discussed, and their rationale]

## Files and Code
[List all files that were discussed, created, or modified. Include the latest state of the code.]

## Errors and Fixes
[Document any errors encountered and how they were (or weren't) resolved. Pay very close attention to what specific attempts were made so that they are not repeated.]

## Problem Solving
[Any problem-solving approaches attempted, including failed approaches and their outcomes]

## All User Messages
[Everything the user said, in order. Include the user's exact words where possible so that intent is accurately captured.]

## Pending Tasks
[Any remaining tasks, action items, or unresolved issues. Be specific about what still needs to be done.]

## Current Work
[Where in the process were things left off. What is the next step that should be taken?]

## Optional Next Step
[Suggest the very next action to take based on the current state.]
</summary-prompt>"""


# ── Experiment execution ─────────────────────────────────────────────

def extract_session_pair(info: SessionInfo) -> dict:
    """
    Extract raw and cleaned message pairs for a session.
    Returns stats and saves to disk.
    """
    messages = load_pre_compaction_messages(info.path, info.compact_boundary_idx)
    actual_summary = load_actual_compaction(info.path, info.compact_boundary_idx)
    tool_results = identify_dead_tool_results(messages)

    dead = [tr for tr in tool_results if tr.is_dead]
    alive = [tr for tr in tool_results if not tr.is_dead and tr.content_size >= 500]

    cleaned = clean_messages(messages, tool_results)

    # Calculate sizes
    raw_size = sum(len(json.dumps(m)) for m in messages)
    cleaned_size = sum(len(json.dumps(m)) for m in cleaned)

    result = {
        "session_id": info.session_id,
        "project": info.project,
        "total_messages": len(messages),
        "total_tool_results": len(tool_results),
        "dead_tool_results": len(dead),
        "alive_tool_results": len(alive),
        "dead_bytes": sum(tr.content_size for tr in dead),
        "alive_bytes": sum(tr.content_size for tr in alive),
        "raw_message_bytes": raw_size,
        "cleaned_message_bytes": cleaned_size,
        "reduction_pct": round((1 - cleaned_size / raw_size) * 100, 1) if raw_size else 0,
        "actual_summary_length": len(actual_summary) if actual_summary else 0,
        "dead_tools": [
            {"id": tr.tool_use_id, "name": tr.tool_name, "size": tr.content_size}
            for tr in dead
        ],
    }

    # Save to disk
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    session_dir = OUTPUT_DIR / info.session_id
    session_dir.mkdir(exist_ok=True)

    with open(session_dir / "raw_messages.json", "w") as f:
        json.dump(messages, f)
    with open(session_dir / "cleaned_messages.json", "w") as f:
        json.dump(cleaned, f)
    if actual_summary:
        with open(session_dir / "actual_summary.txt", "w") as f:
            f.write(actual_summary)
    with open(session_dir / "stats.json", "w") as f:
        json.dump(result, f, indent=2)

    return result


# ── Reasoning anchor extraction ──────────────────────────────────────

REASONING_MARKERS = [
    "because", "since", "instead of", "rather than", "the reason",
    "decided to", "chose to", "opted for", "this means", "therefore",
    "so that", "in order to", "the problem was", "the issue was",
    "turns out", "root cause", "the fix", "switched to", "pivoted to",
]


def extract_reasoning_anchors(messages: list[dict]) -> list[dict]:
    """
    Find assistant statements that contain explicit reasoning.
    Returns list of {text, marker, context} dicts.
    """
    anchors = []
    for msg in messages:
        if msg["role"] != "assistant":
            continue
        text = _get_text_content(msg)
        for marker in REASONING_MARKERS:
            idx = 0
            while True:
                pos = text.lower().find(marker, idx)
                if pos == -1:
                    break
                # Extract surrounding context (sentence-ish)
                start = max(0, text.rfind(".", 0, pos) + 1)
                end = text.find(".", pos)
                if end == -1:
                    end = min(len(text), pos + 200)
                else:
                    end = min(end + 1, pos + 300)

                context = text[start:end].strip()
                if len(context) > 30:  # Skip trivial matches
                    anchors.append({
                        "marker": marker,
                        "context": context,
                    })
                idx = pos + len(marker)

    # Deduplicate by context
    seen = set()
    unique = []
    for a in anchors:
        key = a["context"][:80]
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique


# ── API compaction ───────────────────────────────────────────────────

def _flatten_content(content) -> str:
    """Convert message content (string, list of blocks) into plain text."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)

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
                inp = c.get("input", {})
                # Compact representation of tool call
                inp_str = json.dumps(inp, indent=None)
                if len(inp_str) > 200:
                    inp_str = inp_str[:200] + "..."
                parts.append(f"[Tool call: {name}({inp_str})]")
            elif ctype == "tool_result":
                rc = c.get("content", "")
                text = _tool_result_text(rc) if not isinstance(rc, str) else rc
                if len(text) > 500:
                    parts.append(f"[Tool result ({len(text)} chars): {text[:200]}...]")
                else:
                    parts.append(f"[Tool result: {text}]")
            elif ctype == "thinking":
                parts.append(f"[Thinking: {c.get('thinking', '')[:200]}]")
            else:
                parts.append(f"[{ctype}]")
    return "\n".join(parts)


def _prepare_compaction_request(messages: list[dict]) -> list[dict]:
    """
    Convert session messages into a text-only API request for compaction.

    Tool use/result blocks are flattened into text descriptions so the
    API doesn't require tool_use/tool_result pairing. System messages
    are skipped.
    """
    flat_messages = []
    for msg in messages:
        role = msg["role"]
        if role == "system":
            continue
        text = _flatten_content(msg["content"])
        if text.strip():
            flat_messages.append({"role": role, "content": text})

    # Append the compaction prompt as a final user message
    flat_messages.append({
        "role": "user",
        "content": COMPACTION_PROMPT,
    })

    # Merge consecutive same-role messages
    merged = []
    for msg in flat_messages:
        if merged and merged[-1]["role"] == msg["role"]:
            merged[-1]["content"] += "\n" + msg["content"]
        else:
            merged.append(dict(msg))

    # Ensure first message is from user
    if merged and merged[0]["role"] != "user":
        merged.insert(0, {"role": "user", "content": "[conversation start]"})

    return merged


def run_compaction(messages: list[dict], model: str = "claude-sonnet-4-20250514") -> str:
    """Send messages to the API with the compaction prompt and return the summary."""
    import anthropic

    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY from env
    api_messages = _prepare_compaction_request(messages)

    response = client.messages.create(
        model=model,
        max_tokens=8192,
        messages=api_messages,
    )

    # Extract text from response
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)

    summary = "\n".join(parts)

    return summary, {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "model": model,
    }


def cmd_run(idx: int, model: str = "claude-sonnet-4-20250514"):
    """Run compaction on both raw and cleaned versions of a session."""
    sessions = find_compacted_sessions()
    if idx >= len(sessions):
        print(f"Error: index {idx} out of range (0-{len(sessions)-1})")
        return

    info = sessions[idx]
    session_dir = OUTPUT_DIR / info.session_id

    if not session_dir.exists():
        print(f"Session not yet extracted. Run: extract {idx}")
        return

    raw_messages = json.load(open(session_dir / "raw_messages.json"))
    cleaned_messages = json.load(open(session_dir / "cleaned_messages.json"))

    stats = json.load(open(session_dir / "stats.json"))
    print(f"Session: {info.session_id[:12]}... ({stats['project'][:25]})")
    print(f"  Raw: {stats['raw_message_bytes']:,} bytes, "
          f"Cleaned: {stats['cleaned_message_bytes']:,} bytes "
          f"(Δ {stats['reduction_pct']}%)")
    print(f"  Model: {model}")
    print()

    # Run cleaned first (smaller, faster, cheaper — and if it fails we save money)
    print("Running compaction on CLEANED messages...")
    cleaned_summary, cleaned_usage = run_compaction(cleaned_messages, model)
    print(f"  Input: {cleaned_usage['input_tokens']:,} tokens, "
          f"Output: {cleaned_usage['output_tokens']:,} tokens")
    print(f"  Summary length: {len(cleaned_summary):,} chars")

    with open(session_dir / "cleaned_summary.txt", "w") as f:
        f.write(cleaned_summary)
    with open(session_dir / "cleaned_usage.json", "w") as f:
        json.dump(cleaned_usage, f, indent=2)

    print()
    print("Running compaction on RAW messages...")
    raw_summary, raw_usage = run_compaction(raw_messages, model)
    print(f"  Input: {raw_usage['input_tokens']:,} tokens, "
          f"Output: {raw_usage['output_tokens']:,} tokens")
    print(f"  Summary length: {len(raw_summary):,} chars")

    with open(session_dir / "raw_summary.txt", "w") as f:
        f.write(raw_summary)
    with open(session_dir / "raw_usage.json", "w") as f:
        json.dump(raw_usage, f, indent=2)

    # Quick comparison
    print()
    print("=== Comparison ===")
    print(f"  Raw summary: {len(raw_summary):,} chars "
          f"({raw_usage['input_tokens']:,} + {raw_usage['output_tokens']:,} tokens)")
    print(f"  Cleaned summary: {len(cleaned_summary):,} chars "
          f"({cleaned_usage['input_tokens']:,} + {cleaned_usage['output_tokens']:,} tokens)")
    print(f"  Token savings: {raw_usage['input_tokens'] - cleaned_usage['input_tokens']:,} input tokens")

    # Save comparison
    comparison = {
        "session_id": info.session_id,
        "model": model,
        "raw": {
            "summary_length": len(raw_summary),
            **raw_usage,
        },
        "cleaned": {
            "summary_length": len(cleaned_summary),
            **cleaned_usage,
        },
        "input_token_savings": raw_usage["input_tokens"] - cleaned_usage["input_tokens"],
    }
    with open(session_dir / "comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)


# ── CLI ──────────────────────────────────────────────────────────────

def cmd_survey():
    """List all available sessions with compaction events."""
    sessions = find_compacted_sessions()
    print(f"Found {len(sessions)} sessions with compaction events:\n")
    print(f"{'#':>3}  {'Project':30s}  {'CB@':>6}  {'TR':>4}  {'TR Size':>10}  {'Compactions':>4}")
    print("-" * 70)
    for i, s in enumerate(sessions):
        proj = s.project[:30]
        print(f"{i:3d}  {proj:30s}  {s.compact_boundary_idx:6d}  "
              f"{s.tool_results_before:4d}  {s.tool_result_bytes:>10,}  {s.compaction_count:4d}")


def cmd_extract(idx: int):
    """Extract raw and cleaned message pairs for a session."""
    sessions = find_compacted_sessions()
    if idx >= len(sessions):
        print(f"Error: index {idx} out of range (0-{len(sessions)-1})")
        return

    info = sessions[idx]
    print(f"Extracting session: {info.session_id}")
    print(f"  Project: {info.project}")
    print(f"  Compact boundary at record: {info.compact_boundary_idx}")
    print(f"  Tool results: {info.tool_results_before}")
    print()

    result = extract_session_pair(info)

    print(f"Results:")
    print(f"  Total messages: {result['total_messages']}")
    print(f"  Tool results: {result['total_tool_results']}")
    print(f"  Dead (unreferenced): {result['dead_tool_results']} ({result['dead_bytes']:,} bytes)")
    print(f"  Alive (referenced): {result['alive_tool_results']} ({result['alive_bytes']:,} bytes)")
    print(f"  Raw size: {result['raw_message_bytes']:,} bytes")
    print(f"  Cleaned size: {result['cleaned_message_bytes']:,} bytes")
    print(f"  Reduction: {result['reduction_pct']}%")
    print(f"  Actual summary length: {result['actual_summary_length']:,} chars")

    # Also extract reasoning anchors
    messages = load_pre_compaction_messages(info.path, info.compact_boundary_idx)
    anchors = extract_reasoning_anchors(messages)
    print(f"\n  Reasoning anchors found: {len(anchors)}")
    for a in anchors[:5]:
        ctx = a["context"][:100].replace("\n", " ")
        print(f"    [{a['marker']}] {ctx}")

    session_dir = OUTPUT_DIR / info.session_id
    with open(session_dir / "reasoning_anchors.json", "w") as f:
        json.dump(anchors, f, indent=2)


def cmd_extract_all():
    """Extract all sessions."""
    sessions = find_compacted_sessions()
    print(f"Extracting {len(sessions)} sessions...\n")
    for i, info in enumerate(sessions):
        print(f"[{i+1}/{len(sessions)}] {info.project} / {info.session_id[:12]}...")
        try:
            result = extract_session_pair(info)
            messages = load_pre_compaction_messages(info.path, info.compact_boundary_idx)
            anchors = extract_reasoning_anchors(messages)
            session_dir = OUTPUT_DIR / info.session_id
            with open(session_dir / "reasoning_anchors.json", "w") as f:
                json.dump(anchors, f, indent=2)
            print(f"  dead={result['dead_tool_results']} "
                  f"reduction={result['reduction_pct']}% "
                  f"anchors={len(anchors)}")
        except Exception as e:
            print(f"  ERROR: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd == "survey":
        cmd_survey()
    elif cmd == "extract":
        if len(sys.argv) < 3:
            print("Usage: compaction_experiment.py extract <idx|all>")
            sys.exit(1)
        if sys.argv[2] == "all":
            cmd_extract_all()
        else:
            cmd_extract(int(sys.argv[2]))
    elif cmd == "run":
        if len(sys.argv) < 3:
            print("Usage: compaction_experiment.py run <idx> [model]")
            sys.exit(1)
        model = sys.argv[3] if len(sys.argv) > 3 else "claude-sonnet-4-20250514"
        cmd_run(int(sys.argv[2]), model)
    elif cmd == "evaluate":
        print("TODO: evaluate reasoning recall")
    elif cmd == "batch":
        print("TODO: full pipeline")
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
