#!/usr/bin/env python3
"""Evaluation framework for context paging experiments.

Parses proxy JSONL logs from experimental runs, computes per-turn and
cumulative metrics, and compares across treatment conditions.

Data sources:
    - proxy_*.jsonl: request/response records with usage data
    - pages_*.jsonl: eviction and page fault records

Metrics computed:
    - Token consumption (input, output, cache hits/misses)
    - API call count
    - Context size growth curve
    - Compaction events and savings
    - Fault rate
    - Wall-clock time
    - System prompt overhead

Usage:
    # Analyze a single run
    uv run python tools/phase1/experiment_eval.py --run tmp/api_logs/proxy_*.jsonl

    # Compare treatments
    uv run python tools/phase1/experiment_eval.py \\
        --compare baseline=tmp/exp/baseline/proxy.jsonl \\
                  t1_compact=tmp/exp/t1/proxy.jsonl \\
                  t2_trimmed=tmp/exp/t2/proxy.jsonl

    # JSON output for downstream analysis
    uv run python tools/phase1/experiment_eval.py --run proxy.jsonl --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path


@dataclass
class TurnMetrics:
    """Metrics for a single API call (request + response pair)."""

    turn: int
    timestamp: str
    model: str
    # Token counts from Anthropic's response
    # input_tokens = non-cached only. Effective = input + cache_creation + cache_read
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def effective_input_tokens(self) -> int:
        """Total tokens in context = non-cached + cache_creation + cache_read."""
        return self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens
    # Sizes from proxy measurement
    total_request_bytes: int = 0
    messages_bytes: int = 0
    system_prompt_bytes: int = 0
    tool_result_count: int = 0
    tool_result_bytes: int = 0
    tool_use_count: int = 0
    # Compaction (if active)
    evictions: int = 0
    compaction_bytes_saved: int = 0
    faults: int = 0
    # Timing
    duration_ms: int = 0
    first_byte_ms: int = 0


@dataclass
class RunSummary:
    """Aggregate metrics for one experimental run."""

    label: str
    proxy_log: str
    # Totals
    api_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation: int = 0
    total_cache_read: int = 0
    total_tokens: int = 0  # input + output
    total_effective_input: int = 0  # input + cache_creation + cache_read (context size)
    # Bytes
    total_request_bytes: int = 0
    total_messages_bytes: int = 0
    total_system_prompt_bytes: int = 0
    total_tool_result_bytes: int = 0
    # Compaction
    total_evictions: int = 0
    total_compaction_bytes_saved: int = 0
    total_faults: int = 0
    fault_rate: float = 0.0
    # Timing
    total_duration_ms: int = 0
    wall_clock_seconds: float = 0.0
    avg_first_byte_ms: float = 0.0
    # Context growth
    max_messages_bytes: int = 0
    max_input_tokens: int = 0
    # Per-turn data for curves
    turns: list[TurnMetrics] = field(default_factory=list)

    @property
    def avg_input_tokens(self) -> float:
        if self.api_calls == 0:
            return 0.0
        return self.total_input_tokens / self.api_calls

    @property
    def avg_effective_input(self) -> float:
        if self.api_calls == 0:
            return 0.0
        return self.total_effective_input / self.api_calls

    @property
    def n_squared_cost(self) -> int:
        """Cumulative effective input tokens — the n² metric."""
        return self.total_effective_input

    @property
    def system_prompt_fraction(self) -> float:
        if self.total_request_bytes == 0:
            return 0.0
        return self.total_system_prompt_bytes / self.total_request_bytes


def parse_proxy_log(path: Path) -> list[dict]:
    """Read all records from a proxy JSONL log."""
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
    return records


def parse_page_log(path: Path) -> list[dict]:
    """Read eviction/fault records from a page log."""
    if not path.exists():
        return []
    return parse_proxy_log(path)


def analyze_run(proxy_path: Path, label: str = "") -> RunSummary:
    """Analyze a single experimental run from its proxy log."""
    records = parse_proxy_log(proxy_path)
    if not label:
        label = proxy_path.stem

    # Find matching page log
    page_path = proxy_path.parent / proxy_path.name.replace("proxy_", "pages_")
    page_records = parse_page_log(page_path)

    summary = RunSummary(label=label, proxy_log=str(proxy_path))

    # Pair requests with responses
    pending_request: dict | None = None
    turn_num = 0
    first_timestamp: str | None = None
    last_timestamp: str | None = None

    # Index compaction records by timestamp for matching
    compaction_by_ts: dict[str, dict] = {}
    fault_by_ts: dict[str, dict] = {}
    for rec in records:
        if rec["type"] == "compaction":
            compaction_by_ts[rec["timestamp"]] = rec
        elif rec["type"] == "page_faults":
            fault_by_ts[rec["timestamp"]] = rec

    for rec in records:
        rtype = rec.get("type", "")

        if rtype == "request":
            pending_request = rec
            if first_timestamp is None:
                first_timestamp = rec["timestamp"]
            continue

        if rtype in ("response_stream", "response") and pending_request is not None:
            turn_num += 1
            last_timestamp = rec["timestamp"]

            usage = rec.get("usage", {})
            messages = pending_request.get("messages", {})
            system = pending_request.get("system", {})

            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cache_creation = usage.get("cache_creation_input_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)

            # System prompt bytes
            if isinstance(system, dict):
                sp_bytes = system.get("system_prompt_bytes", 0)
                if isinstance(sp_bytes, str):
                    sp_bytes = 0
            else:
                sp_bytes = 0

            # Messages metrics
            if isinstance(messages, dict):
                msg_bytes = messages.get("messages_total_bytes", 0)
                tr_count = messages.get("tool_result_count", 0)
                tr_bytes = messages.get("tool_result_bytes", 0)
                tu_count = messages.get("tool_use_count", 0)
            else:
                msg_bytes = tr_count = tr_bytes = tu_count = 0

            duration = rec.get("duration_ms", 0)
            first_byte = rec.get("first_byte_ms", 0)

            # Find compaction for this turn (closest timestamp before response)
            turn_evictions = 0
            turn_comp_saved = 0
            turn_faults = 0

            # Simple: find compaction/fault records between request and response
            req_ts = pending_request.get("timestamp", "")
            resp_ts = rec.get("timestamp", "")
            for cts, crec in compaction_by_ts.items():
                if req_ts <= cts <= resp_ts:
                    turn_evictions += crec.get("evicted", 0)
                    turn_comp_saved += crec.get("bytes_saved", 0)
            for fts, frec in fault_by_ts.items():
                if req_ts <= fts <= resp_ts:
                    turn_faults += frec.get("count", 0)

            turn = TurnMetrics(
                turn=turn_num,
                timestamp=rec["timestamp"],
                model=pending_request.get("model", "unknown"),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_creation_tokens=cache_creation,
                cache_read_tokens=cache_read,
                total_request_bytes=pending_request.get("total_request_bytes", 0),
                messages_bytes=msg_bytes,
                system_prompt_bytes=sp_bytes,
                tool_result_count=tr_count,
                tool_result_bytes=tr_bytes,
                tool_use_count=tu_count,
                evictions=turn_evictions,
                compaction_bytes_saved=turn_comp_saved,
                faults=turn_faults,
                duration_ms=duration,
                first_byte_ms=first_byte,
            )
            summary.turns.append(turn)

            # Accumulate
            summary.api_calls += 1
            summary.total_input_tokens += input_tokens
            summary.total_output_tokens += output_tokens
            summary.total_cache_creation += cache_creation
            summary.total_cache_read += cache_read
            summary.total_request_bytes += pending_request.get(
                "total_request_bytes", 0
            )
            summary.total_messages_bytes += msg_bytes
            summary.total_system_prompt_bytes += sp_bytes
            summary.total_tool_result_bytes += tr_bytes
            summary.total_evictions += turn_evictions
            summary.total_compaction_bytes_saved += turn_comp_saved
            summary.total_faults += turn_faults
            summary.total_duration_ms += duration
            if msg_bytes > summary.max_messages_bytes:
                summary.max_messages_bytes = msg_bytes
            if input_tokens > summary.max_input_tokens:
                summary.max_input_tokens = input_tokens

            pending_request = None

    summary.total_tokens = summary.total_input_tokens + summary.total_output_tokens
    summary.total_effective_input = (
        summary.total_input_tokens
        + summary.total_cache_creation
        + summary.total_cache_read
    )

    if summary.total_evictions > 0:
        summary.fault_rate = summary.total_faults / summary.total_evictions

    # Wall clock
    if first_timestamp and last_timestamp:
        try:
            t0 = datetime.fromisoformat(first_timestamp)
            t1 = datetime.fromisoformat(last_timestamp)
            summary.wall_clock_seconds = (t1 - t0).total_seconds()
        except (ValueError, TypeError):
            pass

    # Average first byte latency
    fb_times = [t.first_byte_ms for t in summary.turns if t.first_byte_ms > 0]
    if fb_times:
        summary.avg_first_byte_ms = sum(fb_times) / len(fb_times)

    return summary


def print_run_summary(s: RunSummary) -> None:
    """Print a human-readable summary of one run."""
    print(f"\n{'='*60}")
    print(f"Run: {s.label}")
    print(f"Log: {s.proxy_log}")
    print(f"{'='*60}")

    print(f"\nAPI calls:           {s.api_calls:>10,}")
    print(f"Wall clock:          {s.wall_clock_seconds:>10.0f}s")
    print(f"Avg first byte:      {s.avg_first_byte_ms:>10.0f}ms")

    print(f"\nTokens:")
    print(f"  Input (non-cached):{s.total_input_tokens:>12,}")
    print(f"  Cache creation:    {s.total_cache_creation:>12,}")
    print(f"  Cache read:        {s.total_cache_read:>12,}")
    print(f"  Effective input:   {s.total_effective_input:>12,}  (context size)")
    print(f"  Output:            {s.total_output_tokens:>12,}")
    print(f"  Avg effective/call:{s.avg_effective_input:>12,.0f}")
    print(f"  Max input (1 call):{s.max_input_tokens:>12,}")

    print(f"\nBytes:")
    print(f"  Total request:     {s.total_request_bytes:>12,}")
    print(f"  Messages:          {s.total_messages_bytes:>12,}")
    print(f"  System prompt:     {s.total_system_prompt_bytes:>12,}")
    print(f"  Tool results:      {s.total_tool_result_bytes:>12,}")
    print(f"  Sys prompt %:      {s.system_prompt_fraction:>11.1%}")
    print(f"  Max messages:      {s.max_messages_bytes:>12,}")

    if s.total_evictions > 0:
        print(f"\nCompaction:")
        print(f"  Evictions:         {s.total_evictions:>12,}")
        print(f"  Bytes saved:       {s.total_compaction_bytes_saved:>12,}")
        print(f"  Faults:            {s.total_faults:>12,}")
        print(f"  Fault rate:        {s.fault_rate:>11.2%}")

    # Context growth curve (show every Nth turn for readability)
    if len(s.turns) > 5:
        print(f"\nContext growth (effective input tokens per call):")
        step = max(1, len(s.turns) // 15)
        cum_input = 0
        max_eff = max((t.effective_input_tokens for t in s.turns), default=1)
        for i, t in enumerate(s.turns):
            eff = t.effective_input_tokens
            cum_input += eff
            if i % step == 0 or i == len(s.turns) - 1:
                bar_len = min(50, eff * 50 // max(1, max_eff))
                bar = "#" * bar_len
                print(f"  T{t.turn:>4d}: {eff:>8,} {bar}")
        print(f"  Cumulative (n²):   {cum_input:>12,}")


def print_comparison(summaries: list[RunSummary]) -> None:
    """Print side-by-side comparison of treatment runs."""
    if not summaries:
        return

    baseline = summaries[0]
    print(f"\n{'='*70}")
    print("TREATMENT COMPARISON")
    print(f"{'='*70}")

    # Header
    labels = [s.label for s in summaries]
    header = f"{'Metric':<30s}"
    for label in labels:
        header += f"  {label:>14s}"
    if len(summaries) > 1:
        header += f"  {'vs baseline':>14s}"
    print(f"\n{header}")
    print("-" * len(header))

    def row(metric: str, values: list, fmt: str = ",d", pct: bool = True):
        line = f"{metric:<30s}"
        for v in values:
            line += f"  {v:>14{fmt}}"
        if pct and len(values) > 1 and values[0] != 0:
            delta = (values[-1] - values[0]) / values[0]
            line += f"  {delta:>+13.1%}"
        print(line)

    row("API calls", [s.api_calls for s in summaries])
    row("Effective input tokens", [s.total_effective_input for s in summaries])
    row("  Non-cached", [s.total_input_tokens for s in summaries])
    row("  Cache creation", [s.total_cache_creation for s in summaries])
    row("  Cache read", [s.total_cache_read for s in summaries])
    row("Output tokens", [s.total_output_tokens for s in summaries])
    row("Avg eff input/call", [int(s.avg_effective_input) for s in summaries])
    row("Max input (1 call)", [s.max_input_tokens for s in summaries])
    row("Wall clock (s)", [int(s.wall_clock_seconds) for s in summaries])
    row("Avg first byte (ms)",
        [int(s.avg_first_byte_ms) for s in summaries])
    row("Total request bytes", [s.total_request_bytes for s in summaries])
    row("System prompt bytes", [s.total_system_prompt_bytes for s in summaries])
    row("Tool result bytes", [s.total_tool_result_bytes for s in summaries])
    row("Evictions", [s.total_evictions for s in summaries])
    row("Faults", [s.total_faults for s in summaries])

    # Cost estimate (Opus pricing as of early 2026)
    # Non-cached input: $15/M, Cache write: $18.75/M, Cache read: $1.50/M, Output: $75/M
    def _estimate_cost(s: RunSummary) -> tuple[float, float, float, float]:
        nc = (s.total_input_tokens / 1e6) * 15.0
        cw = (s.total_cache_creation / 1e6) * 18.75
        cr = (s.total_cache_read / 1e6) * 1.50
        out = (s.total_output_tokens / 1e6) * 75.0
        return nc, cw, cr, out

    print()
    costs = []
    for s in summaries:
        nc, cw, cr, out = _estimate_cost(s)
        total = nc + cw + cr + out
        costs.append(total)
        print(f"  {s.label} est. cost: ${total:,.2f} "
              f"(input ${nc:.2f} + cache_write ${cw:.2f} + "
              f"cache_read ${cr:.2f} + output ${out:.2f})")

    if len(summaries) > 1 and costs[0] > 0:
        savings = costs[0] - costs[-1]
        print(f"\n  Savings ({summaries[-1].label} vs {baseline.label}): "
              f"${savings:,.2f} ({savings/costs[0]:.1%})")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate context paging experiment runs"
    )
    parser.add_argument(
        "--run",
        type=Path,
        nargs="*",
        help="Proxy JSONL log(s) to analyze individually",
    )
    parser.add_argument(
        "--compare",
        nargs="*",
        metavar="LABEL=PATH",
        help="Compare treatments: baseline=path/proxy.jsonl t1=path/proxy.jsonl",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON",
    )
    args = parser.parse_args()

    if not args.run and not args.compare:
        parser.print_help()
        return

    summaries: list[RunSummary] = []

    if args.run:
        for path in args.run:
            s = analyze_run(path)
            summaries.append(s)

    if args.compare:
        for spec in args.compare:
            if "=" in spec:
                label, path_str = spec.split("=", 1)
            else:
                label = Path(spec).stem
                path_str = spec
            s = analyze_run(Path(path_str), label=label)
            summaries.append(s)

    if args.json:
        for s in summaries:
            out = asdict(s)
            # Remove per-turn data from JSON summary (too large)
            out["turn_count"] = len(out.pop("turns"))
            print(json.dumps(out))
        return

    if args.compare and len(summaries) > 1:
        print_comparison(summaries)
    else:
        for s in summaries:
            print_run_summary(s)


if __name__ == "__main__":
    main()
