#!/usr/bin/env python3
"""Corpus-scale trimmer analysis: project tool stub savings across 813 sessions.

The trimmer (pichay) works on proxy JSONL logs. The 813-session corpus is raw
Claude Code session JSONL — different format. This script bridges the gap:

1. Reads raw session JSONL, extracts tool usage per session
2. Uses per-tool byte costs measured from 14 proxy-captured sessions
3. Projects tool stub savings at corpus scale
4. Adds constant skill dedup and static re-send savings

The tool stub savings are the only metric that varies per session —
skill dedup and static re-send are constants determined by the system prompt.

Usage:
    python tools/phase1/corpus_trimmer_analysis.py [--corpus-dir DIR] [--json]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants from 14 proxy-captured sessions (measured, not estimated)
# ---------------------------------------------------------------------------

# Tool definitions in the API request (bytes, median across 14 sessions)
TOTAL_TOOL_DEF_BYTES = 63_088

# Known tools sent by Claude Code
KNOWN_TOOLS = [
    "Agent", "Bash", "Edit", "Glob", "Grep", "Read", "Write",
    "WebFetch", "WebSearch", "NotebookEdit", "TodoWrite", "Skill",
    "AskUserQuestion", "EnterPlanMode", "ExitPlanMode", "TaskOutput",
    "TaskStop", "EnterWorktree",
]
NUM_KNOWN_TOOLS = len(KNOWN_TOOLS)

# Per-tool byte costs
PER_TOOL_DEF_BYTES = TOTAL_TOOL_DEF_BYTES / NUM_KNOWN_TOOLS  # ~3505
STUB_BYTES = 80  # minimal stub schema
NET_SAVINGS_PER_STUB = PER_TOOL_DEF_BYTES - STUB_BYTES  # ~3425

# Skill dedup: constant per request (skills list is always tripled)
SKILL_DEDUP_PER_REQUEST = 7_453  # bytes, measured from proxy logs

# Static re-send: system prompt bytes that don't change between turns
# Only applies to turns after the first (can't detect static on turn 1)
STATIC_BYTES_PER_REQUEST = 30_100  # bytes, median from proxy logs

# Additional tools seen in session logs that aren't in KNOWN_TOOLS
# (MCP tools, team tools, etc.) — these don't have stubs in the proxy
EXTRA_TOOL_PREFIXES = ("mcp__", "SendMessage", "TeamCreate", "TeamDelete")


# ---------------------------------------------------------------------------
# Session analysis
# ---------------------------------------------------------------------------

@dataclass
class SessionToolProfile:
    """Tool usage profile for a single session."""

    path: str
    session_type: str
    file_bytes: int
    assistant_turns: int = 0  # proxy for API call count
    unique_tools: set[str] = field(default_factory=set)

    # Computed
    @property
    def known_tools_used(self) -> int:
        return len(self.unique_tools & set(KNOWN_TOOLS))

    @property
    def stubbable_tools(self) -> int:
        return max(0, NUM_KNOWN_TOOLS - self.known_tools_used)

    @property
    def stub_bytes_per_request(self) -> int:
        return int(self.stubbable_tools * NET_SAVINGS_PER_STUB)

    @property
    def total_stub_bytes(self) -> int:
        return self.stub_bytes_per_request * self.assistant_turns

    @property
    def total_skill_dedup_bytes(self) -> int:
        # Skill list present after first turn (system-reminder injection)
        return SKILL_DEDUP_PER_REQUEST * max(0, self.assistant_turns - 1)

    @property
    def total_static_bytes(self) -> int:
        # Static savings after first turn
        return STATIC_BYTES_PER_REQUEST * max(0, self.assistant_turns - 1)

    @property
    def total_savings(self) -> int:
        return self.total_stub_bytes + self.total_skill_dedup_bytes + self.total_static_bytes


def classify_session(path: Path) -> str:
    name = path.name
    if name.startswith("agent-acompact"):
        return "compact"
    elif name.startswith("agent-aprompt_suggestion"):
        return "prompt_suggestion"
    elif name.startswith("agent-"):
        return "subagent"
    elif name in ("history.jsonl", "pretty.jsonl"):
        return "other"
    return "main"


def analyze_session(path: Path) -> SessionToolProfile:
    """Extract tool usage from a raw Claude Code session JSONL."""
    profile = SessionToolProfile(
        path=str(path),
        session_type=classify_session(path),
        file_bytes=path.stat().st_size,
    )

    tool_use_to_name: dict[str, str] = {}

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            rtype = record.get("type", "")

            if rtype == "assistant":
                profile.assistant_turns += 1
                content = record.get("message", {}).get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            name = block.get("name", "")
                            if name:
                                profile.unique_tools.add(name)
                                tool_use_to_name[block.get("id", "")] = name

    return profile


def find_sessions(corpus_dirs: list[Path], min_size: int = 10000) -> list[Path]:
    sessions = []
    for d in corpus_dirs:
        if not d.exists():
            print(f"Warning: {d} not found", file=sys.stderr)
            continue
        for f in d.rglob("*.jsonl"):
            if f.stat().st_size >= min_size:
                sessions.append(f)
    return sorted(sessions, key=lambda p: p.stat().st_size, reverse=True)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_report(profiles: list[SessionToolProfile]) -> None:
    print(f"\n{'='*72}")
    print("CORPUS-SCALE TRIMMER PROJECTION")
    print(f"{'='*72}")
    print(f"Sessions analyzed: {len(profiles)}")
    print(f"Constants from 14 proxy-captured sessions:")
    print(f"  Tool definitions:     {TOTAL_TOOL_DEF_BYTES:>10,} bytes/request ({NUM_KNOWN_TOOLS} tools)")
    print(f"  Per-tool definition:  {PER_TOOL_DEF_BYTES:>10,.0f} bytes")
    print(f"  Stub overhead:        {STUB_BYTES:>10,} bytes")
    print(f"  Net savings/stub:     {NET_SAVINGS_PER_STUB:>10,.0f} bytes")
    print(f"  Skill dedup/request:  {SKILL_DEDUP_PER_REQUEST:>10,} bytes")
    print(f"  Static re-send/req:   {STATIC_BYTES_PER_REQUEST:>10,} bytes")

    # Filter to sessions with actual work
    active = [p for p in profiles if p.assistant_turns > 0]
    substantial = [p for p in profiles if p.assistant_turns > 5]

    print(f"\nActive sessions (>0 turns): {len(active)}")
    print(f"Substantial sessions (>5 turns): {len(substantial)}")

    # Tool usage distribution
    tools_used = [p.known_tools_used for p in active]
    stubbable = [p.stubbable_tools for p in active]

    print(f"\n--- Tool Usage Distribution (active sessions) ---")
    print(f"  Known tools used per session:")
    print(f"    Min:    {min(tools_used):>3d}")
    print(f"    P25:    {statistics.quantiles(tools_used, n=4)[0]:>5.1f}")
    print(f"    Median: {statistics.median(tools_used):>5.1f}")
    print(f"    P75:    {statistics.quantiles(tools_used, n=4)[2]:>5.1f}")
    print(f"    Max:    {max(tools_used):>3d}")

    print(f"\n  Stubbable tools per session:")
    print(f"    Min:    {min(stubbable):>3d}")
    print(f"    Median: {statistics.median(stubbable):>5.1f}")
    print(f"    Max:    {max(stubbable):>3d}")

    # Tool frequency across corpus
    tool_freq: Counter[str] = Counter()
    for p in active:
        for t in p.unique_tools:
            tool_freq[t] += 1
    n_active = len(active)

    print(f"\n--- Tool Adoption Rate (% of sessions using each tool) ---")
    for tool in KNOWN_TOOLS:
        count = tool_freq.get(tool, 0)
        pct = count / n_active * 100 if n_active else 0
        bar = "#" * int(pct / 2)
        print(f"  {tool:20s}: {count:4d} ({pct:5.1f}%) {bar}")

    # Extra tools (MCP, team, etc.)
    extra = {t: c for t, c in tool_freq.items() if t not in KNOWN_TOOLS}
    if extra:
        print(f"\n  Non-standard tools:")
        for name, count in sorted(extra.items(), key=lambda x: -x[1])[:10]:
            print(f"    {name:30s}: {count:4d} sessions")

    # Savings projection
    total_turns = sum(p.assistant_turns for p in active)
    total_stub = sum(p.total_stub_bytes for p in active)
    total_skill = sum(p.total_skill_dedup_bytes for p in active)
    total_static = sum(p.total_static_bytes for p in active)
    total_all = total_stub + total_skill + total_static

    # Per-request tool def bytes (what's actually sent)
    total_tool_def_sent = TOTAL_TOOL_DEF_BYTES * total_turns

    print(f"\n--- Projected Savings (all active sessions) ---")
    print(f"  Total API calls:        {total_turns:>14,}")
    print(f"  Tool defs sent:         {total_tool_def_sent:>14,} bytes ({total_tool_def_sent/1e9:.2f} GB)")
    print()
    print(f"  Tool stub savings:      {total_stub:>14,} bytes ({total_stub/1e9:.2f} GB)")
    print(f"  Skill dedup savings:    {total_skill:>14,} bytes ({total_skill/1e9:.2f} GB)")
    print(f"  Static re-send savings: {total_static:>14,} bytes ({total_static/1e9:.2f} GB)")
    print(f"  {'─'*50}")
    print(f"  Total projected:        {total_all:>14,} bytes ({total_all/1e9:.2f} GB)")

    if total_tool_def_sent > 0:
        print(f"\n  Tool stub as % of tool defs:   {total_stub/total_tool_def_sent:.1%}")

    # Breakdown by session type
    from collections import defaultdict
    by_type: dict[str, list[SessionToolProfile]] = defaultdict(list)
    for p in active:
        by_type[p.session_type].append(p)

    print(f"\n--- By Session Type ---")
    for stype in ["main", "subagent", "compact", "prompt_suggestion", "other"]:
        group = by_type.get(stype, [])
        if not group:
            continue
        g_turns = sum(p.assistant_turns for p in group)
        g_stub = sum(p.total_stub_bytes for p in group)
        g_tools = [p.known_tools_used for p in group]
        print(f"\n  [{stype}] {len(group)} sessions, {g_turns:,} API calls")
        if g_tools:
            print(f"    Tools used: median {statistics.median(g_tools):.0f}, max {max(g_tools)}")
        print(f"    Stub savings: {g_stub:,} bytes ({g_stub/1e6:.1f} MB)")

    # Validate against proxy-measured percentages
    print(f"\n{'='*72}")
    print("VALIDATION AGAINST PROXY MEASUREMENTS")
    print(f"{'='*72}")
    print(f"  Proxy sample (14 sessions):  20.2% tool stubs, 2.9% skill dedup")
    print(f"  Corpus projection ({len(active)} sessions):")

    # Estimate total request bytes: tool defs are ~63K out of ~200K per request
    # (measured from proxy: system prompt ~40K + tool defs ~63K + messages vary)
    est_overhead_per_request = 63_088 + 40_000 + 7_453  # tool + system + skills
    total_overhead_sent = est_overhead_per_request * total_turns
    if total_overhead_sent > 0:
        print(f"    Tool stub savings:  {total_stub/total_overhead_sent:.1%} of overhead bytes")
        print(f"    Skill dedup:        {total_skill/total_overhead_sent:.1%} of overhead bytes")
        print(f"    Static re-send:     {total_static/total_overhead_sent:.1%} of overhead bytes")


def output_json(profiles: list[SessionToolProfile]) -> None:
    active = [p for p in profiles if p.assistant_turns > 0]

    # Per-session summaries
    sessions = []
    for p in active:
        sessions.append({
            "path": p.path,
            "session_type": p.session_type,
            "file_bytes": p.file_bytes,
            "assistant_turns": p.assistant_turns,
            "known_tools_used": p.known_tools_used,
            "unique_tools": sorted(p.unique_tools),
            "stubbable_tools": p.stubbable_tools,
            "stub_bytes_per_request": p.stub_bytes_per_request,
            "total_stub_bytes": p.total_stub_bytes,
            "total_skill_dedup_bytes": p.total_skill_dedup_bytes,
            "total_static_bytes": p.total_static_bytes,
            "total_savings": p.total_savings,
        })

    # Aggregate
    total_turns = sum(p.assistant_turns for p in active)
    total_stub = sum(p.total_stub_bytes for p in active)
    total_skill = sum(p.total_skill_dedup_bytes for p in active)
    total_static = sum(p.total_static_bytes for p in active)
    tools_used = [p.known_tools_used for p in active]

    agg = {
        "sessions_total": len(profiles),
        "sessions_active": len(active),
        "total_api_calls": total_turns,
        "tools_used_distribution": {
            "min": min(tools_used),
            "p25": statistics.quantiles(tools_used, n=4)[0],
            "median": statistics.median(tools_used),
            "p75": statistics.quantiles(tools_used, n=4)[2],
            "max": max(tools_used),
        },
        "total_stub_bytes": total_stub,
        "total_skill_dedup_bytes": total_skill,
        "total_static_bytes": total_static,
        "total_savings_bytes": total_stub + total_skill + total_static,
        "constants": {
            "tool_def_bytes_per_request": TOTAL_TOOL_DEF_BYTES,
            "num_known_tools": NUM_KNOWN_TOOLS,
            "skill_dedup_per_request": SKILL_DEDUP_PER_REQUEST,
            "static_per_request": STATIC_BYTES_PER_REQUEST,
        },
    }

    output = {"aggregate": agg, "sessions": sessions}
    print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Corpus-scale trimmer savings projection"
    )
    parser.add_argument(
        "--corpus-dir", action="append", type=Path,
        help="Directory containing JSONL sessions (repeatable)",
    )
    parser.add_argument(
        "--min-size", type=int, default=10000,
        help="Skip files smaller than this (default 10KB)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    if not args.corpus_dir:
        args.corpus_dir = [
            Path.home() / ".claude" / "projects",
            Path("tmp/ubuntu-vm.claude/projects"),
        ]

    sessions = find_sessions(args.corpus_dir, min_size=args.min_size)
    print(f"Found {len(sessions)} sessions", file=sys.stderr)

    profiles = []
    for i, path in enumerate(sessions):
        if (i + 1) % 50 == 0:
            print(
                f"\r  Analyzing {i+1}/{len(sessions)}...",
                end="", flush=True, file=sys.stderr,
            )
        try:
            profiles.append(analyze_session(path))
        except Exception as e:
            print(f"\n  Error: {path}: {e}", file=sys.stderr)

    print(file=sys.stderr)

    if args.json:
        output_json(profiles)
    else:
        print_report(profiles)


if __name__ == "__main__":
    main()
