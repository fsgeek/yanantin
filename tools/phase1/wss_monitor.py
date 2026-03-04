#!/usr/bin/env python3
"""Working Set Size monitor — tails proxy JSONL and displays live context metrics.

Shows two numbers per API call:
    1. What Claude Code sent (pre-intervention working set)
    2. What the proxy forwarded to Anthropic (post-intervention working set)

Plus the API-confirmed token counts from Anthropic's response.

Usage:
    # Monitor a running proxy session
    python tools/phase1/wss_monitor.py tmp/proxy-logs/proxy_*.jsonl

    # Follow mode (default) — tails the file like tail -f
    python tools/phase1/wss_monitor.py --follow tmp/proxy-logs/proxy_*.jsonl

    # One-shot mode — print summary and exit
    python tools/phase1/wss_monitor.py --no-follow tmp/proxy-logs/proxy_*.jsonl

No dependencies outside stdlib. Reads JSONL written by pichay's proxy.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TurnState:
    """Accumulates records for one API call until we can display it."""

    turn_num: int
    timestamp: str = ""

    # Pre-intervention (from "request" record)
    system_bytes: int = 0
    messages_bytes: int = 0
    total_request_bytes: int = 0
    message_count: int = 0
    tool_result_count: int = 0
    tool_result_bytes: int = 0
    text_bytes: int = 0
    thinking_bytes: int = 0
    tool_use_count: int = 0

    # Trimming (from "trimming" record)
    trim_tools_saved: int = 0
    trim_skills_saved: int = 0
    trim_stubs: int = 0
    trim_dupes: int = 0
    trim_static_skippable: int = 0

    # Compaction (from "compaction" record)
    compact_evicted: int = 0
    compact_bytes_saved: int = 0
    compact_messages_before: int = 0
    compact_messages_after: int = 0
    cumulative_evictions: int = 0
    cumulative_faults: int = 0
    cumulative_bytes_saved: int = 0
    fault_rate: float = 0.0

    # Page faults (from "page_faults" record)
    turn_faults: int = 0

    # API response (from "response" or "response_stream" record)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    duration_ms: int = 0
    first_byte_ms: int | None = None

    # Token cap (from "token_cap" record)
    cap_action: str = ""  # "warning", "exceeded", "blocked"
    cap_effective: int = 0
    cap_limit: int = 0
    cap_pct: float = 0.0

    has_request: bool = False
    has_response: bool = False

    @property
    def pre_intervention_bytes(self) -> int:
        return self.total_request_bytes

    @property
    def post_intervention_bytes(self) -> int:
        return self.total_request_bytes - self.trim_tools_saved - self.trim_skills_saved - self.compact_bytes_saved

    @property
    def tool_overhead_pct(self) -> float:
        if self.messages_bytes == 0:
            return 0.0
        return (self.tool_result_bytes / self.messages_bytes) * 100

    @property
    def effective_input_tokens(self) -> int:
        return self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens

    @property
    def savings_bytes(self) -> int:
        return self.trim_tools_saved + self.trim_skills_saved + self.compact_bytes_saved


_YELLOW = "\033[33m"
_RED = "\033[31m"
_RESET = "\033[0m"


def _fmt_bytes(n: int) -> str:
    """Format bytes with K/M suffix."""
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def _fmt_tokens(n: int) -> str:
    """Format token counts."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def _est_tokens(byte_count: int) -> int:
    """Rough byte-to-token estimate (4 chars/token for English + JSON)."""
    return byte_count // 4


def display_turn(t: TurnState, file=sys.stderr) -> None:
    """Print a formatted working set summary for one API call."""
    w = 70
    print(f"\n{'─' * w}", file=file)
    print(f" Turn {t.turn_num}  {t.timestamp}", file=file)
    print(f"{'─' * w}", file=file)

    # Pre-intervention
    est_tok = _est_tokens(t.pre_intervention_bytes)
    print(
        f"  Received:   {_fmt_bytes(t.pre_intervention_bytes):>8s} B  "
        f"(~{_fmt_tokens(est_tok)} tok est)",
        file=file,
    )
    print(
        f"    system {_fmt_bytes(t.system_bytes)} + "
        f"messages {_fmt_bytes(t.messages_bytes)} "
        f"({t.message_count} msgs, {t.tool_result_count} tool results)",
        file=file,
    )
    if t.tool_result_bytes > 0:
        print(
            f"    tool output: {_fmt_bytes(t.tool_result_bytes)} B "
            f"({t.tool_overhead_pct:.0f}% of messages)",
            file=file,
        )

    # Post-intervention
    if t.savings_bytes > 0:
        est_post = _est_tokens(t.post_intervention_bytes)
        parts = []
        if t.trim_tools_saved > 0:
            parts.append(f"stubs -{_fmt_bytes(t.trim_tools_saved)}")
        if t.trim_skills_saved > 0:
            parts.append(f"dedup -{_fmt_bytes(t.trim_skills_saved)}")
        if t.compact_bytes_saved > 0:
            parts.append(f"evict -{_fmt_bytes(t.compact_bytes_saved)} ({t.compact_evicted} results)")
        savings_detail = ", ".join(parts)
        print(
            f"  Forwarded:  {_fmt_bytes(t.post_intervention_bytes):>8s} B  "
            f"(~{_fmt_tokens(est_post)} tok est)  [{savings_detail}]",
            file=file,
        )
    else:
        print(
            f"  Forwarded:  {_fmt_bytes(t.post_intervention_bytes):>8s} B  "
            f"(no interventions)",
            file=file,
        )

    # Faults this turn
    if t.turn_faults > 0:
        print(
            f"  PAGE FAULTS: {t.turn_faults} this turn",
            file=file,
        )

    # API response
    if t.has_response:
        eff = t.effective_input_tokens
        timing = ""
        if t.duration_ms > 0:
            timing = f"  [{t.duration_ms / 1000:.1f}s"
            if t.first_byte_ms is not None and t.first_byte_ms > 0:
                timing += f", TTFB {t.first_byte_ms}ms"
            timing += "]"

        print(
            f"  API actual: {_fmt_tokens(eff):>8s} tok context, "
            f"{_fmt_tokens(t.output_tokens)} out{timing}",
            file=file,
        )
        # Breakdown: new vs cached
        parts = []
        if t.input_tokens > 0:
            parts.append(f"new {_fmt_tokens(t.input_tokens)}")
        if t.cache_read_tokens > 0:
            parts.append(f"cache-read {_fmt_tokens(t.cache_read_tokens)}")
        if t.cache_creation_tokens > 0:
            parts.append(f"cache-write {_fmt_tokens(t.cache_creation_tokens)}")
        if parts:
            print(f"    ({', '.join(parts)})", file=file)

    # Token cap status
    if t.cap_action == "warning":
        print(
            f"{_YELLOW}  TOKEN WARNING: {_fmt_tokens(t.cap_effective)} / "
            f"{_fmt_tokens(t.cap_limit)} ({t.cap_pct:.0f}%) — approaching cap{_RESET}",
            file=file,
        )
    elif t.cap_action == "exceeded":
        print(
            f"{_RED}  TOKEN CAP EXCEEDED: {_fmt_tokens(t.cap_effective)} / "
            f"{_fmt_tokens(t.cap_limit)} ({t.cap_pct:.0f}%) — next request blocked{_RESET}",
            file=file,
        )
    elif t.cap_action == "blocked":
        print(
            f"{_RED}  BLOCKED: request refused (last context {_fmt_tokens(t.cap_effective)} "
            f"exceeded cap {_fmt_tokens(t.cap_limit)}){_RESET}",
            file=file,
        )

    # Cumulative (if we have compaction data)
    if t.cumulative_evictions > 0:
        print(
            f"  Cumulative: {t.cumulative_evictions} evictions, "
            f"{t.cumulative_faults} faults ({t.fault_rate:.1f}%), "
            f"{_fmt_bytes(t.cumulative_bytes_saved)} saved",
            file=file,
        )


def display_session_summary(turns: list[TurnState], file=sys.stderr) -> None:
    """Print end-of-session summary."""
    if not turns:
        return
    w = 70
    print(f"\n{'═' * w}", file=file)
    print(f" SESSION SUMMARY ({len(turns)} API calls)", file=file)
    print(f"{'═' * w}", file=file)

    total_pre = sum(t.pre_intervention_bytes for t in turns)
    total_post = sum(t.post_intervention_bytes for t in turns)
    total_savings = sum(t.savings_bytes for t in turns)
    total_input_tok = sum(t.input_tokens for t in turns)
    total_output_tok = sum(t.output_tokens for t in turns)
    total_cache_read = sum(t.cache_read_tokens for t in turns)
    total_cache_write = sum(t.cache_creation_tokens for t in turns)
    total_effective = sum(t.effective_input_tokens for t in turns)

    print(f"  Total received:   {_fmt_bytes(total_pre)}", file=file)
    print(f"  Total forwarded:  {_fmt_bytes(total_post)}", file=file)
    if total_savings > 0:
        pct = (total_savings / total_pre * 100) if total_pre > 0 else 0
        print(f"  Total savings:    {_fmt_bytes(total_savings)} ({pct:.1f}%)", file=file)

    if total_input_tok > 0:
        print(f"  API input tokens: {_fmt_tokens(total_input_tok)} (effective: {_fmt_tokens(total_effective)})", file=file)
        print(f"  API output tokens:{_fmt_tokens(total_output_tok)}", file=file)
        if total_cache_read > 0:
            hit_rate = total_cache_read / total_effective * 100 if total_effective > 0 else 0
            print(f"  Cache hit rate:   {hit_rate:.1f}%", file=file)

    # Growth curve — show how working set grows across turns
    if len(turns) > 1:
        print(f"\n  Working set growth:", file=file)
        for t in turns:
            bar_len = int(t.pre_intervention_bytes / max(t2.pre_intervention_bytes for t2 in turns) * 40) if any(t2.pre_intervention_bytes > 0 for t2 in turns) else 0
            bar = "█" * bar_len
            post_bar = ""
            if t.savings_bytes > 0:
                post_len = int(t.post_intervention_bytes / max(t2.pre_intervention_bytes for t2 in turns) * 40)
                bar = "█" * post_len + "░" * (bar_len - post_len)
            if t.has_response and t.effective_input_tokens > 0:
                print(
                    f"  T{t.turn_num:>3d} {bar} {_fmt_bytes(t.pre_intervention_bytes):>7s} → {_fmt_tokens(t.effective_input_tokens):>6s} tok",
                    file=file,
                )
            else:
                print(
                    f"  T{t.turn_num:>3d} {bar} {_fmt_bytes(t.pre_intervention_bytes):>7s}",
                    file=file,
                )
        print(f"         {'█' * 3} = forwarded  {'░' * 3} = trimmed/evicted", file=file)

    print(f"{'═' * w}", file=file)


class Monitor:
    """Reads proxy JSONL and emits working set displays."""

    def __init__(self):
        self.turn_num = 0
        self.current: TurnState | None = None
        self.turns: list[TurnState] = []

    def process_record(self, record: dict) -> TurnState | None:
        """Process one JSONL record. Returns a completed TurnState when a turn finishes."""
        rtype = record.get("type", "")

        if rtype == "request":
            # Start of a new turn
            if self.current is not None and self.current.has_request:
                # Previous turn never got a response — display what we have
                completed = self.current
                self.turns.append(completed)
                display_turn(completed)

            self.turn_num += 1
            self.current = TurnState(turn_num=self.turn_num)
            self.current.timestamp = record.get("timestamp", "")
            self.current.has_request = True

            sys_metrics = record.get("system", {})
            self.current.system_bytes = sys_metrics.get("system_prompt_bytes", 0)

            msg_metrics = record.get("messages", {})
            self.current.messages_bytes = msg_metrics.get("messages_total_bytes", 0)
            self.current.message_count = msg_metrics.get("message_count", 0)
            self.current.tool_result_count = msg_metrics.get("tool_result_count", 0)
            self.current.tool_result_bytes = msg_metrics.get("tool_result_bytes", 0)
            self.current.text_bytes = msg_metrics.get("text_bytes", 0)
            self.current.thinking_bytes = msg_metrics.get("thinking_bytes", 0)
            self.current.tool_use_count = msg_metrics.get("tool_use_count", 0)

            self.current.total_request_bytes = record.get("total_request_bytes", 0)
            return None

        if self.current is None:
            return None

        if rtype == "trimming":
            tools = record.get("tools", {})
            self.current.trim_tools_saved = tools.get("bytes_before", 0) - tools.get("bytes_after", 0)
            self.current.trim_stubs = tools.get("stubbed_tools", 0)

            skills = record.get("skills", {})
            self.current.trim_skills_saved = skills.get("bytes_before", 0) - skills.get("bytes_after", 0)
            self.current.trim_dupes = skills.get("duplicates_removed", 0)

            static = record.get("static", {})
            self.current.trim_static_skippable = static.get("static_bytes_skippable", 0)

        elif rtype == "compaction":
            self.current.compact_evicted = record.get("evicted", 0)
            self.current.compact_bytes_saved = record.get("bytes_saved", 0)
            self.current.compact_messages_before = record.get("messages_bytes_before", 0)
            self.current.compact_messages_after = record.get("messages_bytes_after", 0)
            self.current.cumulative_evictions = record.get("cumulative_evictions", 0)
            self.current.cumulative_faults = record.get("cumulative_faults", 0)
            self.current.cumulative_bytes_saved = record.get("cumulative_bytes_saved", 0)
            self.current.fault_rate = record.get("fault_rate", 0.0)

        elif rtype == "page_faults":
            self.current.turn_faults = record.get("count", 0)
            self.current.cumulative_faults = record.get("cumulative_faults", 0)
            self.current.fault_rate = record.get("fault_rate", 0.0)

        elif rtype == "token_cap":
            action = record.get("action", "")
            if action == "blocked":
                # Blocked request — display immediately as its own turn
                if self.current is not None and self.current.has_request:
                    self.current.cap_action = action
                    self.current.cap_effective = record.get("last_effective_tokens", 0)
                    self.current.cap_limit = record.get("token_cap", 0)
                    completed = self.current
                    self.turns.append(completed)
                    display_turn(completed)
                    self.current = None
                    return completed
            else:
                # warning or exceeded — attach to current turn
                self.current.cap_action = action
                self.current.cap_effective = record.get("effective_tokens", 0)
                self.current.cap_limit = record.get("token_cap", 0)
                self.current.cap_pct = record.get("pct", 0.0)

        elif rtype in ("response", "response_stream"):
            usage = record.get("usage", {})
            self.current.input_tokens = usage.get("input_tokens", 0)
            self.current.output_tokens = usage.get("output_tokens", 0)
            self.current.cache_read_tokens = usage.get("cache_read_input_tokens", 0)
            self.current.cache_creation_tokens = usage.get("cache_creation_input_tokens", 0)
            self.current.duration_ms = record.get("duration_ms", 0)
            self.current.first_byte_ms = record.get("first_byte_ms")
            self.current.has_response = True

            # Turn is complete — display it
            completed = self.current
            self.turns.append(completed)
            display_turn(completed)
            self.current = None
            return completed

        return None


def tail_jsonl(path: Path, follow: bool = True) -> Monitor:
    """Read a JSONL file, optionally following new data."""
    monitor = Monitor()

    try:
        with open(path, "r", encoding="utf-8") as f:
            while True:
                line = f.readline()
                if line:
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            monitor.process_record(record)
                        except json.JSONDecodeError:
                            pass
                elif follow:
                    time.sleep(0.25)
                else:
                    break
    except KeyboardInterrupt:
        pass

    return monitor


def wait_for_file(pattern: str, directory: Path, timeout: float = 300) -> Path | None:
    """Wait for a file matching the glob pattern to appear."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0)
        if matches:
            return matches[-1]  # newest
        time.sleep(0.5)
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Working Set Size monitor — tails proxy JSONL and displays live context metrics"
    )
    parser.add_argument(
        "log_file",
        type=Path,
        nargs="?",
        help="Proxy JSONL log file to monitor. If omitted, watches tmp/proxy-logs/ for new files.",
    )
    parser.add_argument(
        "--no-follow", action="store_true",
        help="Process existing records and exit (don't tail)",
    )
    parser.add_argument(
        "--log-dir", type=Path, default=None,
        help="Directory to watch for proxy log files (default: tmp/proxy-logs/)",
    )
    args = parser.parse_args()

    log_path = args.log_file

    if log_path is None:
        log_dir = args.log_dir or Path("tmp/proxy-logs")
        print(f"Watching {log_dir}/ for proxy log files...", file=sys.stderr)
        log_path = wait_for_file("proxy_*.jsonl", log_dir)
        if log_path is None:
            print("No proxy log file found. Is the proxy running?", file=sys.stderr)
            sys.exit(1)

    if not log_path.exists():
        print(f"Log file not found: {log_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Monitoring: {log_path}", file=sys.stderr)
    print(f"Press Ctrl-C to stop and see session summary.\n", file=sys.stderr)

    monitor = tail_jsonl(log_path, follow=not args.no_follow)

    # Show summary on exit
    display_session_summary(monitor.turns)


if __name__ == "__main__":
    main()
