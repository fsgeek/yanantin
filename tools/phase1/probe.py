#!/usr/bin/env python3
"""Phase 1 probe: measure context window waste in Claude Code sessions.

Reads JSONL conversation transcripts and computes:
1. Per-tool-result size distribution
2. Turn survival (how many turns each tool result persists)
3. Amplification factor (total bytes reprocessed)
4. Consumption lag (turns between result and next action)
5. Session-level overhead ratio

Does NOT load full files into memory. Streams line by line.

Usage:
    python tools/phase1/probe.py [--corpus-dir DIR] [--sample N] [--min-size BYTES]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolResult:
    """A single tool result record."""
    uuid: str
    tool_use_id: str
    tool_name: str  # inferred from the assistant message that triggered it
    content_bytes: int
    line_bytes: int
    turn_index: int
    timestamp: str


@dataclass
class SessionAnalysis:
    """Analysis of a single JSONL session."""
    path: Path
    file_bytes: int
    total_records: int = 0
    user_records: int = 0
    assistant_records: int = 0
    tool_result_records: int = 0
    progress_records: int = 0
    other_records: int = 0

    # Size accounting
    total_tool_result_bytes: int = 0
    total_assistant_bytes: int = 0
    total_user_text_bytes: int = 0
    total_thinking_bytes: int = 0
    total_progress_bytes: int = 0

    # Tool results detail
    tool_results: list[ToolResult] = field(default_factory=list)
    tool_names: Counter = field(default_factory=Counter)

    # Turn structure
    conversation_turns: int = 0  # user→assistant pairs
    tool_use_count: int = 0

    # Session classification
    session_type: str = "unknown"  # "main", "subagent", "compact", "other"

    # Token accounting (from API usage metadata)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0

    @property
    def tool_overhead_ratio(self) -> float:
        """Fraction of conversation bytes that are tool results."""
        conversation_bytes = (
            self.total_tool_result_bytes
            + self.total_assistant_bytes
            + self.total_user_text_bytes
        )
        if conversation_bytes == 0:
            return 0.0
        return self.total_tool_result_bytes / conversation_bytes

    @property
    def amplification_factor(self) -> float:
        """Sum of (result_size * turns_survived) / sum(result_size).

        How many times, on average, each byte of tool output is
        reprocessed across subsequent turns.
        """
        if not self.tool_results:
            return 0.0
        total_reprocessed = sum(
            tr.content_bytes * self._turns_survived(tr)
            for tr in self.tool_results
        )
        total_original = sum(tr.content_bytes for tr in self.tool_results)
        if total_original == 0:
            return 0.0
        return total_reprocessed / total_original

    def _turns_survived(self, tr: ToolResult) -> int:
        """How many conversation turns this tool result survives in context.

        Conservative: counts from the tool result's turn to end of session.
        In reality, context compaction may evict it earlier.
        """
        return max(0, self.conversation_turns - tr.turn_index)


def classify_session(path: Path) -> str:
    """Classify session type from filename."""
    name = path.name
    if name.startswith("agent-acompact"):
        return "compact"
    elif name.startswith("agent-aprompt_suggestion"):
        return "prompt_suggestion"
    elif name.startswith("agent-"):
        return "subagent"
    elif name == "history.jsonl" or name == "pretty.jsonl":
        return "other"
    else:
        # UUID-named files are main sessions
        return "main"


def analyze_session(path: Path) -> SessionAnalysis:
    """Stream-analyze a single JSONL session file."""
    analysis = SessionAnalysis(path=path, file_bytes=path.stat().st_size)
    analysis.session_type = classify_session(path)

    # First pass: build record sequence and identify tool results
    records = []  # (type, uuid, parent_uuid, line_bytes, parsed)
    tool_use_to_name: dict[str, str] = {}  # tool_use_id → tool name

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            line_bytes = len(line.encode("utf-8"))
            record_type = record.get("type", "unknown")
            uuid = record.get("uuid", "")
            parent_uuid = record.get("parentUuid", "")

            analysis.total_records += 1

            if record_type == "assistant":
                analysis.assistant_records += 1
                message = record.get("message", {})
                content = message.get("content", [])

                # Track token usage
                usage = message.get("usage", {})
                analysis.total_input_tokens += usage.get("input_tokens", 0)
                analysis.total_output_tokens += usage.get("output_tokens", 0)
                analysis.total_cache_read_tokens += usage.get(
                    "cache_read_input_tokens", 0
                )
                analysis.total_cache_creation_tokens += usage.get(
                    "cache_creation_input_tokens", 0
                )

                # Measure content blocks
                assistant_text_bytes = 0
                thinking_bytes = 0
                for block in content if isinstance(content, list) else []:
                    block_type = block.get("type", "")
                    if block_type == "tool_use":
                        tool_id = block.get("id", "")
                        tool_name = block.get("name", "unknown")
                        tool_use_to_name[tool_id] = tool_name
                        analysis.tool_use_count += 1
                        analysis.tool_names[tool_name] += 1
                    elif block_type == "text":
                        text = block.get("text", "")
                        assistant_text_bytes += len(text.encode("utf-8"))
                    elif block_type == "thinking":
                        thinking = block.get("thinking", "")
                        thinking_bytes += len(thinking.encode("utf-8"))

                analysis.total_assistant_bytes += assistant_text_bytes
                analysis.total_thinking_bytes += thinking_bytes

            elif record_type == "user":
                analysis.user_records += 1
                message = record.get("message", {})
                content = message.get("content", [])

                is_tool_result = False
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_result":
                            is_tool_result = True
                            tool_use_id = block.get("tool_use_id", "")
                            result_content = block.get("content", "")
                            if isinstance(result_content, str):
                                content_bytes = len(
                                    result_content.encode("utf-8")
                                )
                            else:
                                content_bytes = len(
                                    json.dumps(result_content).encode("utf-8")
                                )

                            analysis.tool_result_records += 1
                            analysis.total_tool_result_bytes += content_bytes

                            tool_name = tool_use_to_name.get(
                                tool_use_id, "unknown"
                            )
                            tr = ToolResult(
                                uuid=uuid,
                                tool_use_id=tool_use_id,
                                tool_name=tool_name,
                                content_bytes=content_bytes,
                                line_bytes=line_bytes,
                                turn_index=analysis.conversation_turns,
                                timestamp=record.get("timestamp", ""),
                            )
                            analysis.tool_results.append(tr)

                if not is_tool_result:
                    # Plain user message
                    if isinstance(content, str):
                        analysis.total_user_text_bytes += len(
                            content.encode("utf-8")
                        )
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                analysis.total_user_text_bytes += len(
                                    block.get("text", "").encode("utf-8")
                                )
                            elif isinstance(block, str):
                                analysis.total_user_text_bytes += len(
                                    block.encode("utf-8")
                                )

                # Every user record (including tool results) is a turn boundary
                analysis.conversation_turns += 1

            elif record_type in ("progress", "hook_progress"):
                analysis.progress_records += 1
                analysis.total_progress_bytes += line_bytes
            else:
                analysis.other_records += 1

    return analysis


def find_sessions(corpus_dirs: list[Path], min_size: int = 1000) -> list[Path]:
    """Find all JSONL session files in corpus directories."""
    sessions = []
    for corpus_dir in corpus_dirs:
        if not corpus_dir.exists():
            print(f"Warning: {corpus_dir} does not exist", file=sys.stderr)
            continue
        for jsonl in corpus_dir.rglob("*.jsonl"):
            if jsonl.stat().st_size >= min_size:
                sessions.append(jsonl)
    return sorted(sessions, key=lambda p: p.stat().st_size, reverse=True)


def print_session_report(analysis: SessionAnalysis) -> None:
    """Print analysis for a single session."""
    print(f"\n{'='*70}")
    print(f"Session: {analysis.path.name} [{analysis.session_type}]")
    print(f"  Size: {analysis.file_bytes:,} bytes")
    print(f"  Records: {analysis.total_records} total")
    print(
        f"    User: {analysis.user_records} | Assistant: {analysis.assistant_records}"
        f" | Tool results: {analysis.tool_result_records}"
        f" | Progress: {analysis.progress_records}"
        f" | Other: {analysis.other_records}"
    )
    print(f"  Conversation turns: {analysis.conversation_turns}")
    print(f"  Tool uses: {analysis.tool_use_count}")

    print(f"\n  Content breakdown (conversation bytes only):")
    conv_total = (
        analysis.total_tool_result_bytes
        + analysis.total_assistant_bytes
        + analysis.total_user_text_bytes
    )
    if conv_total > 0:
        print(
            f"    Tool results: {analysis.total_tool_result_bytes:>10,} bytes"
            f" ({analysis.total_tool_result_bytes/conv_total*100:.1f}%)"
        )
        print(
            f"    Assistant text: {analysis.total_assistant_bytes:>10,} bytes"
            f" ({analysis.total_assistant_bytes/conv_total*100:.1f}%)"
        )
        print(
            f"    User text:     {analysis.total_user_text_bytes:>10,} bytes"
            f" ({analysis.total_user_text_bytes/conv_total*100:.1f}%)"
        )
        print(
            f"    Thinking:      {analysis.total_thinking_bytes:>10,} bytes"
            f" (not in API context)"
        )
        print(f"    TOTAL:         {conv_total:>10,} bytes")

    print(f"\n  Tool overhead ratio: {analysis.tool_overhead_ratio:.1%}")
    print(f"  Amplification factor: {analysis.amplification_factor:.1f}x")

    if analysis.tool_results:
        sizes = [tr.content_bytes for tr in analysis.tool_results]
        print(f"\n  Tool result sizes:")
        print(f"    Min: {min(sizes):,} bytes")
        print(f"    Median: {statistics.median(sizes):,.0f} bytes")
        print(f"    Mean: {statistics.mean(sizes):,.0f} bytes")
        print(f"    Max: {max(sizes):,} bytes")
        print(f"    Total: {sum(sizes):,} bytes")

    if analysis.tool_names:
        print(f"\n  Tool usage by type:")
        for name, count in analysis.tool_names.most_common(10):
            tool_sizes = [
                tr.content_bytes
                for tr in analysis.tool_results
                if tr.tool_name == name
            ]
            total = sum(tool_sizes)
            avg = statistics.mean(tool_sizes) if tool_sizes else 0
            print(f"    {name:20s}: {count:4d} calls, {total:>10,} bytes total, {avg:>8,.0f} avg")

    if analysis.total_input_tokens > 0:
        print(f"\n  Token accounting:")
        print(f"    Input tokens:          {analysis.total_input_tokens:>12,}")
        print(f"    Output tokens:         {analysis.total_output_tokens:>12,}")
        print(f"    Cache read tokens:     {analysis.total_cache_read_tokens:>12,}")
        print(f"    Cache creation tokens: {analysis.total_cache_creation_tokens:>12,}")
        total_input = (
            analysis.total_input_tokens
            + analysis.total_cache_read_tokens
            + analysis.total_cache_creation_tokens
        )
        if total_input > 0:
            cache_ratio = analysis.total_cache_read_tokens / total_input
            print(f"    Cache hit ratio:       {cache_ratio:>11.1%}")


def print_corpus_summary(analyses: list[SessionAnalysis]) -> None:
    """Print aggregate summary across all sessions."""
    print(f"\n{'='*70}")
    print(f"CORPUS SUMMARY ({len(analyses)} sessions)")
    print(f"{'='*70}")

    total_file_bytes = sum(a.file_bytes for a in analyses)
    total_tool_bytes = sum(a.total_tool_result_bytes for a in analyses)
    total_assistant_bytes = sum(a.total_assistant_bytes for a in analyses)
    total_user_bytes = sum(a.total_user_text_bytes for a in analyses)
    total_thinking_bytes = sum(a.total_thinking_bytes for a in analyses)
    total_tool_results = sum(a.tool_result_records for a in analyses)
    total_tool_uses = sum(a.tool_use_count for a in analyses)
    total_turns = sum(a.conversation_turns for a in analyses)

    conv_total = total_tool_bytes + total_assistant_bytes + total_user_bytes

    print(f"\n  Corpus size: {total_file_bytes:,} bytes ({total_file_bytes/1024/1024:.1f} MB)")
    print(f"  Sessions: {len(analyses)}")
    print(f"  Total turns: {total_turns:,}")
    print(f"  Total tool uses: {total_tool_uses:,}")
    print(f"  Total tool results: {total_tool_results:,}")

    if conv_total > 0:
        print(f"\n  Aggregate content breakdown:")
        print(
            f"    Tool results:  {total_tool_bytes:>12,} bytes"
            f" ({total_tool_bytes/conv_total*100:.1f}%)"
        )
        print(
            f"    Assistant text:{total_assistant_bytes:>12,} bytes"
            f" ({total_assistant_bytes/conv_total*100:.1f}%)"
        )
        print(
            f"    User text:     {total_user_bytes:>12,} bytes"
            f" ({total_user_bytes/conv_total*100:.1f}%)"
        )
        print(
            f"    Thinking:      {total_thinking_bytes:>12,} bytes"
            f" (not in API context)"
        )
        print(f"    TOTAL:         {conv_total:>12,} bytes")
        print(f"\n  Aggregate tool overhead: {total_tool_bytes/conv_total:.1%}")

    # Distribution of per-session overhead
    overheads = [a.tool_overhead_ratio for a in analyses if a.conversation_turns > 5]
    if overheads:
        print(f"\n  Per-session overhead distribution (sessions with >5 turns):")
        print(f"    N: {len(overheads)}")
        print(f"    Min: {min(overheads):.1%}")
        print(f"    P25: {statistics.quantiles(overheads, n=4)[0]:.1%}")
        print(f"    Median: {statistics.median(overheads):.1%}")
        print(f"    P75: {statistics.quantiles(overheads, n=4)[2]:.1%}")
        print(f"    Max: {max(overheads):.1%}")

    # Amplification factors
    amps = [a.amplification_factor for a in analyses if a.tool_results]
    if amps:
        print(f"\n  Amplification factor distribution:")
        print(f"    N: {len(amps)}")
        print(f"    Min: {min(amps):.1f}x")
        print(f"    Median: {statistics.median(amps):.1f}x")
        print(f"    Mean: {statistics.mean(amps):.1f}x")
        print(f"    Max: {max(amps):.1f}x")

    # Tool type breakdown across corpus
    corpus_tool_names: Counter = Counter()
    corpus_tool_bytes: defaultdict[str, int] = defaultdict(int)
    for a in analyses:
        for tr in a.tool_results:
            corpus_tool_names[tr.tool_name] += 1
            corpus_tool_bytes[tr.tool_name] += tr.content_bytes

    if corpus_tool_names:
        print(f"\n  Tool usage across corpus:")
        for name, count in corpus_tool_names.most_common(15):
            total = corpus_tool_bytes[name]
            avg = total / count if count > 0 else 0
            print(
                f"    {name:20s}: {count:6,} calls,"
                f" {total:>12,} bytes total,"
                f" {avg:>8,.0f} avg"
            )

    # Token accounting
    total_input = sum(a.total_input_tokens for a in analyses)
    total_output = sum(a.total_output_tokens for a in analyses)
    total_cache_read = sum(a.total_cache_read_tokens for a in analyses)
    total_cache_create = sum(a.total_cache_creation_tokens for a in analyses)

    if total_input > 0:
        print(f"\n  Token accounting (aggregate):")
        print(f"    Input tokens:          {total_input:>14,}")
        print(f"    Output tokens:         {total_output:>14,}")
        print(f"    Cache read tokens:     {total_cache_read:>14,}")
        print(f"    Cache creation tokens: {total_cache_create:>14,}")
        api_total = total_input + total_cache_read + total_cache_create
        if api_total > 0:
            print(f"    Cache hit ratio:       {total_cache_read/api_total:>13.1%}")

    # Segmented analysis by session type
    type_groups: dict[str, list[SessionAnalysis]] = defaultdict(list)
    for a in analyses:
        type_groups[a.session_type].append(a)

    if len(type_groups) > 1:
        print(f"\n{'='*70}")
        print("SEGMENTED BY SESSION TYPE")
        print(f"{'='*70}")

        for stype in ["main", "subagent", "compact", "prompt_suggestion", "other"]:
            group = type_groups.get(stype, [])
            if not group:
                continue

            g_tool = sum(a.total_tool_result_bytes for a in group)
            g_asst = sum(a.total_assistant_bytes for a in group)
            g_user = sum(a.total_user_text_bytes for a in group)
            g_conv = g_tool + g_asst + g_user
            g_turns = sum(a.conversation_turns for a in group)

            g_overheads = [
                a.tool_overhead_ratio
                for a in group
                if a.conversation_turns > 5
            ]
            g_amps = [
                a.amplification_factor for a in group if a.tool_results
            ]

            print(f"\n  [{stype}] {len(group)} sessions, {g_turns:,} turns")
            if g_conv > 0:
                print(f"    Tool overhead: {g_tool/g_conv:.1%}")
            if g_overheads and len(g_overheads) >= 2:
                print(
                    f"    Per-session overhead: "
                    f"median {statistics.median(g_overheads):.1%}, "
                    f"P75 {statistics.quantiles(g_overheads, n=4)[2]:.1%}"
                )
            if g_amps and len(g_amps) >= 2:
                print(
                    f"    Amplification: "
                    f"median {statistics.median(g_amps):.1f}x, "
                    f"mean {statistics.mean(g_amps):.1f}x, "
                    f"max {max(g_amps):.1f}x"
                )


def main():
    parser = argparse.ArgumentParser(
        description="Phase 1 probe: measure context window waste"
    )
    parser.add_argument(
        "--corpus-dir",
        action="append",
        type=Path,
        help="Directory containing JSONL transcripts (can specify multiple)",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        help="Analyze only N largest sessions (0 = all)",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=10000,
        help="Skip files smaller than this (bytes, default 10KB)",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print only corpus summary, not per-session reports",
    )
    args = parser.parse_args()

    # Default corpus directories
    if not args.corpus_dir:
        args.corpus_dir = [
            Path.home() / ".claude" / "projects",
            Path("tmp/ubuntu-vm.claude/projects"),
        ]

    sessions = find_sessions(args.corpus_dir, min_size=args.min_size)
    print(f"Found {len(sessions)} sessions across {len(args.corpus_dir)} corpus directories")

    if args.sample > 0:
        sessions = sessions[: args.sample]
        print(f"Sampling {args.sample} largest sessions")

    analyses = []
    for i, session_path in enumerate(sessions):
        print(
            f"\r  Analyzing {i+1}/{len(sessions)}: {session_path.name[:40]}...",
            end="",
            flush=True,
        )
        try:
            analysis = analyze_session(session_path)
            analyses.append(analysis)
        except Exception as e:
            print(f"\n  Error analyzing {session_path}: {e}", file=sys.stderr)

    print()  # newline after progress

    if not args.summary_only:
        # Print top 10 sessions by tool overhead
        by_overhead = sorted(
            [a for a in analyses if a.conversation_turns > 5],
            key=lambda a: a.tool_overhead_ratio,
            reverse=True,
        )
        print(f"\nTop 10 sessions by tool overhead (>5 turns):")
        for analysis in by_overhead[:10]:
            print_session_report(analysis)

    print_corpus_summary(analyses)


if __name__ == "__main__":
    main()
