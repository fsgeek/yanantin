#!/usr/bin/env python3
"""Measure the reference string for tool results across sessions.

For each tool result in a session, scans forward through all remaining
turns to find re-references (tool_use blocks that match the same
eviction key). Records the distance in turns.

This gives us:
- The re-reference distance distribution (shape of demand paging)
- Which tool results are truly dead vs which have future references
- The working set size at each point in the session
- How far wrong FIFO eviction can be (Belady's MIN comparison)

Usage:
    uv run python tools/phase1/reference_string.py
    uv run python tools/phase1/reference_string.py --limit 10 --json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pager import _eviction_key


@dataclass
class Reference:
    """A single re-reference of a tool result."""

    source_turn: int  # turn where the original tool result appeared
    ref_turn: int  # turn where it was re-referenced
    distance: int  # ref_turn - source_turn
    tool_name: str
    eviction_key: str


@dataclass
class ToolResultRecord:
    """A tool result with its forward reference data."""

    turn: int
    tool_name: str
    eviction_key: str
    content_bytes: int
    forward_refs: list[int] = field(default_factory=list)  # distances
    # Derived
    is_dead: bool = True  # never re-referenced
    nearest_ref: int = 0  # closest re-reference distance
    farthest_ref: int = 0  # farthest re-reference distance


@dataclass
class SessionRefString:
    """Reference string analysis for one session."""

    path: Path
    turns: int
    tool_results: int
    dead_results: int  # never re-referenced
    live_results: int  # re-referenced at least once
    total_refs: int  # total re-reference events
    distances: list[int] = field(default_factory=list)
    records: list[ToolResultRecord] = field(default_factory=list)
    refs_by_tool: dict[str, int] = field(default_factory=dict)
    dead_by_tool: dict[str, int] = field(default_factory=dict)

    @property
    def dead_pct(self) -> float:
        if self.tool_results == 0:
            return 0.0
        return 100 * self.dead_results / self.tool_results


def classify_session(path: Path) -> str:
    name = path.name
    if "compact" in name:
        return "compact"
    elif name.startswith("agent-"):
        return "subagent"
    elif name in ("history.jsonl", "pretty.jsonl"):
        return "other"
    return "main"


def analyze_reference_string(path: Path) -> SessionRefString | None:
    """Build the full reference string for a session.

    For each tool result, scan all subsequent assistant messages
    for tool_use blocks that match the same eviction key.
    """
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

    # Reconstruct messages
    messages = []
    for record in records:
        rtype = record.get("type", "")
        if rtype not in ("user", "assistant"):
            continue
        message = record.get("message", {})
        if not message:
            continue
        msg = {
            "role": message.get("role", rtype),
            "content": message.get("content", ""),
        }
        messages.append(msg)

    if len(messages) < 4:
        return None

    # Build two indices:
    # 1. For each user turn: what tool_results are delivered (with eviction keys)
    # 2. For each assistant turn: what tool_use blocks are issued (with eviction keys)

    # Track turn number (user messages = turns)
    user_turn = 0
    tool_use_index: dict[str, dict] = {}  # tool_use_id → {name, input}

    # Phase 1: Build tool_use_id → name mapping from all assistant messages
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_use_index[block["id"]] = {
                    "name": block.get("name", "unknown"),
                    "input": block.get("input", {}),
                }

    # Phase 2: Collect all tool results with their turn index and eviction key
    tool_results: list[ToolResultRecord] = []
    user_turn = 0

    for msg in messages:
        if msg.get("role") != "user":
            continue
        user_turn += 1
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_result":
                continue

            tool_use_id = block.get("tool_use_id", "")
            tool_info = tool_use_index.get(tool_use_id, {})
            tool_name = tool_info.get("name", "unknown")
            tool_input = tool_info.get("input", {})
            ekey = _eviction_key(tool_name, tool_input)

            if ekey is None:
                continue  # Can't track re-references for this tool type

            result_content = block.get("content", "")
            if isinstance(result_content, str):
                content_bytes = len(result_content.encode("utf-8"))
            else:
                content_bytes = len(json.dumps(result_content).encode("utf-8"))

            tool_results.append(ToolResultRecord(
                turn=user_turn,
                tool_name=tool_name,
                eviction_key=ekey,
                content_bytes=content_bytes,
            ))

    if not tool_results:
        return None

    total_user_turns = user_turn

    # Phase 3: Collect all tool_use actions with their turn index and eviction key
    # (We use assistant turn index aligned with the NEXT user turn)
    tool_actions: list[tuple[int, str, str]] = []  # (turn, tool_name, eviction_key)
    user_turn = 0

    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            user_turn += 1
        elif msg.get("role") == "assistant":
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use":
                    continue
                tool_name = block.get("name", "unknown")
                tool_input = block.get("input", {})
                ekey = _eviction_key(tool_name, tool_input)
                if ekey is not None:
                    # Action happens at the current user_turn
                    # (after the most recent user message)
                    tool_actions.append((user_turn, tool_name, ekey))

    # Phase 4: For each tool result, find all forward references
    # Build an index: eviction_key → list of action turns
    action_index: dict[str, list[int]] = defaultdict(list)
    for turn, tool_name, ekey in tool_actions:
        action_index[ekey].append(turn)

    # Sort action turns for binary search
    for ekey in action_index:
        action_index[ekey].sort()

    all_distances = []
    refs_by_tool: Counter = Counter()
    dead_by_tool: Counter = Counter()

    for tr in tool_results:
        # Find all actions with the same eviction key AFTER this turn
        future_actions = [
            t for t in action_index.get(tr.eviction_key, [])
            if t > tr.turn
        ]

        if future_actions:
            tr.is_dead = False
            tr.forward_refs = [t - tr.turn for t in future_actions]
            tr.nearest_ref = min(tr.forward_refs)
            tr.farthest_ref = max(tr.forward_refs)
            all_distances.extend(tr.forward_refs)
            refs_by_tool[tr.tool_name] += len(future_actions)
        else:
            tr.is_dead = True
            dead_by_tool[tr.tool_name] += 1

    dead_count = sum(1 for tr in tool_results if tr.is_dead)
    live_count = len(tool_results) - dead_count

    return SessionRefString(
        path=path,
        turns=total_user_turns,
        tool_results=len(tool_results),
        dead_results=dead_count,
        live_results=live_count,
        total_refs=len(all_distances),
        distances=all_distances,
        records=tool_results,
        refs_by_tool=dict(refs_by_tool),
        dead_by_tool=dict(dead_by_tool),
    )


def find_main_sessions(roots: list[Path], min_size: int = 10000) -> list[Path]:
    sessions = []
    for root in roots:
        if root.is_file() and root.suffix == ".jsonl":
            sessions.append(root)
            continue
        for jsonl in root.rglob("*.jsonl"):
            if classify_session(jsonl) == "main" and jsonl.stat().st_size >= min_size:
                sessions.append(jsonl)
    return sorted(sessions, key=lambda p: p.stat().st_size, reverse=True)


def _percentile(data: list[float | int], pct: int) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    idx = (pct / 100) * (len(s) - 1)
    lower = int(idx)
    upper = min(lower + 1, len(s) - 1)
    frac = idx - lower
    return s[lower] * (1 - frac) + s[upper] * frac


def print_distance_histogram(distances: list[int], bin_size: int = 5) -> None:
    """Print a text histogram of re-reference distances."""
    if not distances:
        print("  (no re-references)")
        return

    max_dist = max(distances)
    bins: dict[str, int] = {}

    for d in distances:
        if d <= 1:
            label = "1"
        elif d <= 2:
            label = "2"
        elif d <= 3:
            label = "3"
        elif d <= 5:
            label = "4-5"
        elif d <= 10:
            label = "6-10"
        elif d <= 20:
            label = "11-20"
        elif d <= 50:
            label = "21-50"
        elif d <= 100:
            label = "51-100"
        else:
            label = "101+"
        bins[label] = bins.get(label, 0) + 1

    total = len(distances)
    cumulative = 0
    order = ["1", "2", "3", "4-5", "6-10", "11-20", "21-50", "51-100", "101+"]

    print(f"  {'Dist':>7s}  {'Count':>6s}  {'Pct':>5s}  {'Cum':>5s}  Bar")
    for label in order:
        count = bins.get(label, 0)
        if count == 0:
            continue
        cumulative += count
        pct = 100 * count / total
        cum_pct = 100 * cumulative / total
        bar = "#" * int(pct)
        print(f"  {label:>7s}  {count:>6,}  {pct:>4.1f}%  {cum_pct:>4.0f}%  {bar}")


def main():
    parser = argparse.ArgumentParser(
        description="Measure tool result reference strings"
    )
    parser.add_argument(
        "--sessions", type=Path, nargs="*",
        default=[Path.home() / ".claude" / "projects"],
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    sessions = find_main_sessions(args.sessions)
    if args.limit > 0:
        sessions = sessions[:args.limit]

    print(f"Analyzing {len(sessions)} sessions...", file=sys.stderr)

    results: list[SessionRefString] = []
    all_distances: list[int] = []

    for i, path in enumerate(sessions):
        print(
            f"  [{i+1}/{len(sessions)}] {path.name} "
            f"({path.stat().st_size / 1024:.0f} KB)...",
            file=sys.stderr, end="", flush=True,
        )
        result = analyze_reference_string(path)
        if result is not None and result.tool_results > 0:
            results.append(result)
            all_distances.extend(result.distances)
            print(
                f" {result.turns} turns, "
                f"{result.tool_results} results, "
                f"{result.dead_results} dead ({result.dead_pct:.0f}%), "
                f"{result.total_refs} re-refs",
                file=sys.stderr,
            )
        else:
            print(" (skipped)", file=sys.stderr)

    if not results:
        print("No results.", file=sys.stderr)
        return

    if args.json:
        for r in results:
            print(json.dumps({
                "path": str(r.path),
                "turns": r.turns,
                "tool_results": r.tool_results,
                "dead": r.dead_results,
                "live": r.live_results,
                "dead_pct": round(r.dead_pct, 1),
                "total_refs": r.total_refs,
                "distances": r.distances,
                "refs_by_tool": r.refs_by_tool,
                "dead_by_tool": r.dead_by_tool,
            }))
        return

    # Aggregate report
    total_results = sum(r.tool_results for r in results)
    total_dead = sum(r.dead_results for r in results)
    total_live = sum(r.live_results for r in results)
    total_refs = sum(r.total_refs for r in results)

    print(f"\n{'='*70}")
    print(f"REFERENCE STRING ANALYSIS: {len(results)} sessions")
    print(f"{'='*70}")

    print(f"\nTool results analyzed: {total_results:,}")
    print(f"  Dead (never re-referenced):  {total_dead:,} ({100*total_dead/total_results:.1f}%)")
    print(f"  Live (re-referenced):        {total_live:,} ({100*total_live/total_results:.1f}%)")
    print(f"  Total re-reference events:   {total_refs:,}")

    if all_distances:
        print(f"\nRe-reference distance distribution (turns):")
        print(f"  Min:    {min(all_distances)}")
        print(f"  P10:    {_percentile(all_distances, 10):.0f}")
        print(f"  P25:    {_percentile(all_distances, 25):.0f}")
        print(f"  Median: {statistics.median(all_distances):.0f}")
        print(f"  P75:    {_percentile(all_distances, 75):.0f}")
        print(f"  P90:    {_percentile(all_distances, 90):.0f}")
        print(f"  P95:    {_percentile(all_distances, 95):.0f}")
        print(f"  Max:    {max(all_distances)}")
        print(f"  Mean:   {statistics.mean(all_distances):.1f}")

        print(f"\nHistogram:")
        print_distance_histogram(all_distances)

        # What fraction of re-refs would be caught by various thresholds?
        print(f"\n  Threshold analysis (fraction of re-refs within N turns):")
        for threshold in [1, 2, 3, 4, 5, 10, 20, 50]:
            within = sum(1 for d in all_distances if d <= threshold)
            print(f"    <= {threshold:>3d} turns: {within:>6,}/{total_refs:,} "
                  f"({100*within/total_refs:.1f}%)")

    # Dead/live breakdown by tool
    all_refs_by_tool: Counter = Counter()
    all_dead_by_tool: Counter = Counter()
    for r in results:
        for tool, count in r.refs_by_tool.items():
            all_refs_by_tool[tool] += count
        for tool, count in r.dead_by_tool.items():
            all_dead_by_tool[tool] += count

    print(f"\nBy tool type:")
    all_tools = set(all_refs_by_tool.keys()) | set(all_dead_by_tool.keys())
    for tool in sorted(all_tools):
        refs = all_refs_by_tool.get(tool, 0)
        dead = all_dead_by_tool.get(tool, 0)
        total = refs + dead  # rough (refs counts events, dead counts results)
        print(f"  {tool:>10s}: {dead:>5,} dead, {refs:>5,} re-refs")

    # Per-session dead percentage distribution
    dead_pcts = [r.dead_pct for r in results]
    print(f"\nPer-session dead percentage:")
    print(f"  Min:    {min(dead_pcts):.0f}%")
    print(f"  Median: {statistics.median(dead_pcts):.0f}%")
    print(f"  Mean:   {statistics.mean(dead_pcts):.0f}%")
    print(f"  Max:    {max(dead_pcts):.0f}%")

    # Working set analysis: for live results, what's the
    # nearest re-reference distance?
    nearest_refs = []
    for r in results:
        for tr in r.records:
            if not tr.is_dead and tr.nearest_ref > 0:
                nearest_refs.append(tr.nearest_ref)

    if nearest_refs:
        print(f"\nNearest re-reference distance (live results only):")
        print(f"  Min:    {min(nearest_refs)}")
        print(f"  Median: {statistics.median(nearest_refs):.0f}")
        print(f"  P75:    {_percentile(nearest_refs, 75):.0f}")
        print(f"  P90:    {_percentile(nearest_refs, 90):.0f}")
        print(f"  Mean:   {statistics.mean(nearest_refs):.1f}")


if __name__ == "__main__":
    main()
