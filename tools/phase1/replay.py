#!/usr/bin/env python3
"""Offline replay simulator for context paging.

Replays JSONL session transcripts through the pager to measure fault rates
without making any API calls. For each turn in a session, it:

1. Reconstructs the messages array as it would have been at that turn
2. Runs compaction (evicts old tool results)
3. Checks if the model's ACTUAL next action was a re-request of evicted content

This gives us fault rates across the entire corpus — the statistical power
to validate or invalidate the paging hypothesis.

Usage:
    # All main sessions
    uv run python tools/phase1/replay.py

    # Specific sessions or directories
    uv run python tools/phase1/replay.py --sessions ~/.claude/projects/-home-tony-projects-yanantin/

    # Vary parameters
    uv run python tools/phase1/replay.py --age-threshold 6 --min-size 1000
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pager import PageStore, compact_messages, _eviction_key, _build_tool_use_index


@dataclass
class ReplayResult:
    """Results from replaying one session."""

    path: Path
    session_type: str
    turns: int
    tool_results: int
    total_evictions: int  # cumulative across all turns
    total_faults: int
    total_bytes_original: int  # sum of message bytes across all turns
    total_bytes_compacted: int
    fault_details: list[dict] = field(default_factory=list)

    @property
    def fault_rate(self) -> float:
        if self.total_evictions == 0:
            return 0.0
        return self.total_faults / self.total_evictions

    @property
    def bytes_saved(self) -> int:
        return self.total_bytes_original - self.total_bytes_compacted

    @property
    def reduction_pct(self) -> float:
        if self.total_bytes_original == 0:
            return 0.0
        return (self.bytes_saved / self.total_bytes_original) * 100


def classify_session(path: Path) -> str:
    name = path.name
    if "compact" in name:
        return "compact"
    elif "prompt_suggestion" in name:
        return "prompt_suggestion"
    elif name.startswith("agent-"):
        return "subagent"
    elif name == "history.jsonl" or name == "pretty.jsonl":
        return "other"
    else:
        return "main"


def reconstruct_messages(records: list[dict]) -> list[dict]:
    """Rebuild the messages array from JSONL records.

    Each JSONL record has type "user" or "assistant" with a "message" field
    containing the actual message content (role + content).
    """
    messages = []
    for record in records:
        rtype = record.get("type", "")
        if rtype not in ("user", "assistant"):
            continue
        message = record.get("message", {})
        if not message:
            continue
        # The message field contains {role, content, ...}
        msg = {"role": message.get("role", rtype)}
        content = message.get("content", "")
        if content:
            msg["content"] = content
        messages.append(msg)
    return messages


def replay_session(
    path: Path,
    age_threshold: int = 4,
    min_size: int = 500,
) -> ReplayResult | None:
    """Replay a session through the pager, measuring fault rates.

    For each turn boundary, we:
    1. Build the messages array up to that point
    2. Compact it (identify what would be evicted)
    3. Look at the model's next tool_use blocks to detect faults
    """
    # Load all records
    records = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not records:
        return None

    session_type = classify_session(path)

    # Reconstruct full message sequence
    all_messages = reconstruct_messages(records)
    if len(all_messages) < 2:
        return None

    # Count turns and tool results
    total_tool_results = 0
    for msg in all_messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    total_tool_results += 1

    # Count user turns
    user_turns = sum(1 for m in all_messages if m.get("role") == "user")

    if total_tool_results == 0 or user_turns < age_threshold + 2:
        # Not enough turns for compaction to matter
        return ReplayResult(
            path=path,
            session_type=session_type,
            turns=user_turns,
            tool_results=total_tool_results,
            total_evictions=0,
            total_faults=0,
            total_bytes_original=0,
            total_bytes_compacted=0,
        )

    # Simulate turn-by-turn compaction
    # At each turn t, we have messages[0:t]. We compact and check
    # if the next assistant action re-requests evicted content.

    # Build a persistent eviction index to track what's been evicted
    # across the session (simulates the proxy's PageStore)
    eviction_index: dict[tuple[str, str], dict] = {}  # (tool_name, key) → info
    total_evictions = 0
    total_faults = 0
    total_bytes_original = 0
    total_bytes_compacted = 0
    fault_details = []

    # Find turn boundaries (indices where user messages are)
    turn_boundaries = []
    for i, msg in enumerate(all_messages):
        if msg.get("role") == "user":
            turn_boundaries.append(i)

    for turn_idx in range(len(turn_boundaries)):
        # Messages up to this turn (inclusive)
        end_idx = turn_boundaries[turn_idx] + 1
        messages_snapshot = [
            _deep_copy_msg(m) for m in all_messages[:end_idx]
        ]

        # Measure original size
        original_size = _messages_size(messages_snapshot)

        # Compact
        store = PageStore()
        stats = compact_messages(
            messages_snapshot,
            age_threshold=age_threshold,
            min_size=min_size,
            page_store=store,
        )

        compacted_size = _messages_size(messages_snapshot)
        total_bytes_original += original_size
        total_bytes_compacted += compacted_size
        total_evictions += stats.evicted_count

        if stats.evicted_count == 0:
            continue

        # Track what was evicted
        for entry in store.pages.values():
            key = _eviction_key(entry.tool_name, entry.tool_input)
            if key is not None:
                eviction_index[(entry.tool_name, key)] = {
                    "tool_use_id": entry.tool_use_id,
                    "turn_index": entry.turn_index,
                    "original_size": entry.original_size,
                }

        # Check if the model's next action re-requests evicted content
        # Look at assistant messages AFTER this turn
        if end_idx < len(all_messages):
            next_msg = all_messages[end_idx]
            if next_msg.get("role") == "assistant":
                content = next_msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") != "tool_use":
                            continue
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})
                        key = _eviction_key(tool_name, tool_input)
                        if key is None:
                            continue
                        if (tool_name, key) in eviction_index:
                            total_faults += 1
                            evicted = eviction_index[(tool_name, key)]
                            fault_details.append({
                                "turn": turn_idx,
                                "tool_name": tool_name,
                                "key": key,
                                "evicted_turn": evicted["turn_index"],
                                "evicted_size": evicted["original_size"],
                            })

    return ReplayResult(
        path=path,
        session_type=session_type,
        turns=user_turns,
        tool_results=total_tool_results,
        total_evictions=total_evictions,
        total_faults=total_faults,
        total_bytes_original=total_bytes_original,
        total_bytes_compacted=total_bytes_compacted,
        fault_details=fault_details,
    )


def _deep_copy_msg(msg: dict) -> dict:
    """Deep copy a message dict (avoid mutating originals during replay)."""
    return json.loads(json.dumps(msg))


def _messages_size(messages: list[dict]) -> int:
    """Total byte size of a messages array."""
    return len(json.dumps(messages).encode("utf-8"))


def find_main_sessions(roots: list[Path], min_size: int = 10000) -> list[Path]:
    """Find main session JSONL files (not subagents, not compact)."""
    sessions = []
    for root in roots:
        if root.is_file() and root.suffix == ".jsonl":
            sessions.append(root)
            continue
        for jsonl in root.rglob("*.jsonl"):
            if classify_session(jsonl) == "main" and jsonl.stat().st_size >= min_size:
                sessions.append(jsonl)
    return sorted(sessions, key=lambda p: p.stat().st_size, reverse=True)


def main():
    parser = argparse.ArgumentParser(
        description="Replay JSONL sessions through the context pager"
    )
    parser.add_argument(
        "--sessions",
        type=Path,
        nargs="*",
        default=[Path.home() / ".claude" / "projects"],
        help="Session files or directories to search",
    )
    parser.add_argument(
        "--age-threshold", type=int, default=4,
        help="Eviction age threshold in user-turns (default: 4)",
    )
    parser.add_argument(
        "--min-size", type=int, default=500,
        help="Minimum tool result size for eviction (default: 500 bytes)",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Max sessions to replay (0 = all)",
    )
    parser.add_argument(
        "--include-subagents", action="store_true",
        help="Include subagent sessions (default: main only)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSONL",
    )
    args = parser.parse_args()

    sessions = find_main_sessions(args.sessions)
    if not args.include_subagents:
        sessions = [s for s in sessions if classify_session(s) == "main"]

    if args.limit > 0:
        sessions = sessions[: args.limit]

    print(
        f"Replaying {len(sessions)} sessions "
        f"(age_threshold={args.age_threshold}, min_size={args.min_size})",
        file=sys.stderr,
    )

    results: list[ReplayResult] = []
    for i, path in enumerate(sessions):
        print(
            f"  [{i+1}/{len(sessions)}] {path.name} "
            f"({path.stat().st_size / 1024:.0f} KB)...",
            file=sys.stderr,
            end="",
            flush=True,
        )
        result = replay_session(
            path,
            age_threshold=args.age_threshold,
            min_size=args.min_size,
        )
        if result is not None and result.total_evictions > 0:
            results.append(result)
            print(
                f" {result.turns} turns, "
                f"{result.total_evictions} evictions, "
                f"{result.total_faults} faults "
                f"({result.fault_rate:.1%}), "
                f"saved {result.bytes_saved:,} bytes "
                f"({result.reduction_pct:.1f}%)",
                file=sys.stderr,
            )
        else:
            print(" (skipped: no evictions)", file=sys.stderr)

    if not results:
        print("No sessions with evictions found.", file=sys.stderr)
        return

    if args.json:
        for r in results:
            print(json.dumps({
                "path": str(r.path),
                "session_type": r.session_type,
                "turns": r.turns,
                "tool_results": r.tool_results,
                "evictions": r.total_evictions,
                "faults": r.total_faults,
                "fault_rate": round(r.fault_rate, 4),
                "bytes_saved": r.bytes_saved,
                "reduction_pct": round(r.reduction_pct, 1),
                "fault_details": r.fault_details,
            }))
        return

    # Aggregate report
    print(f"\n{'='*70}")
    print(f"REPLAY RESULTS: {len(results)} sessions with evictions")
    print(f"Parameters: age_threshold={args.age_threshold}, min_size={args.min_size}")
    print(f"{'='*70}")

    all_fault_rates = [r.fault_rate for r in results]
    all_reductions = [r.reduction_pct for r in results]
    all_evictions = [r.total_evictions for r in results]
    all_faults = [r.total_faults for r in results]
    total_evictions = sum(all_evictions)
    total_faults = sum(all_faults)

    print(f"\nSessions analyzed:  {len(results)}")
    print(f"Total evictions:    {total_evictions:,}")
    print(f"Total page faults:  {total_faults:,}")
    print(f"Aggregate fault rate: {total_faults/total_evictions:.2%}"
          if total_evictions > 0 else "")

    print(f"\nPer-session fault rate distribution:")
    print(f"  Min:    {min(all_fault_rates):.2%}")
    print(f"  P25:    {_percentile(all_fault_rates, 25):.2%}")
    print(f"  Median: {statistics.median(all_fault_rates):.2%}")
    print(f"  P75:    {_percentile(all_fault_rates, 75):.2%}")
    print(f"  P90:    {_percentile(all_fault_rates, 90):.2%}")
    print(f"  Max:    {max(all_fault_rates):.2%}")
    print(f"  Mean:   {statistics.mean(all_fault_rates):.2%}")

    zero_fault = sum(1 for r in all_fault_rates if r == 0)
    print(f"\nSessions with zero faults: {zero_fault}/{len(results)} "
          f"({100*zero_fault/len(results):.0f}%)")

    print(f"\nByte reduction distribution:")
    print(f"  Min:    {min(all_reductions):.1f}%")
    print(f"  Median: {statistics.median(all_reductions):.1f}%")
    print(f"  Mean:   {statistics.mean(all_reductions):.1f}%")
    print(f"  Max:    {max(all_reductions):.1f}%")

    total_saved = sum(r.bytes_saved for r in results)
    total_original = sum(r.total_bytes_original for r in results)
    BYTES_PER_TOKEN = 3.75
    print(f"\nAggregate savings:")
    print(f"  Total bytes saved:  {total_saved:>15,}")
    print(f"  Total bytes orig:   {total_original:>15,}")
    print(f"  Aggregate reduction: {100*total_saved/total_original:.1f}%"
          if total_original > 0 else "")
    print(f"  Est. tokens saved:  {total_saved/BYTES_PER_TOKEN:>15,.0f}")

    # Fault breakdown by tool
    fault_tools: dict[str, int] = {}
    for r in results:
        for fd in r.fault_details:
            tool = fd["tool_name"]
            fault_tools[tool] = fault_tools.get(tool, 0) + 1
    if fault_tools:
        print(f"\nFaults by tool:")
        for tool, count in sorted(fault_tools.items(), key=lambda x: -x[1]):
            print(f"  {tool}: {count}")

    # Worst sessions
    worst = sorted(results, key=lambda r: r.fault_rate, reverse=True)[:5]
    if worst and worst[0].total_faults > 0:
        print(f"\nHighest fault-rate sessions:")
        for r in worst:
            if r.total_faults == 0:
                break
            print(f"  {r.path.name}: {r.fault_rate:.1%} "
                  f"({r.total_faults}/{r.total_evictions}), "
                  f"{r.turns} turns")


def _percentile(data: list[float], pct: int) -> float:
    """Simple percentile calculation."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (pct / 100) * (len(sorted_data) - 1)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_data) - 1)
    frac = idx - lower
    return sorted_data[lower] * (1 - frac) + sorted_data[upper] * frac


if __name__ == "__main__":
    main()
