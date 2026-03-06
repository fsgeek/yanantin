"""Context window pager — evicts stale tool results from the messages array.

This is the intervention layer for the phase 1 context utilization experiment.
It sits between Claude Code and Anthropic's API (inside the proxy) and replaces
old, large tool results with compact summaries. The originals are stored in a
page file for logging and analysis.

Design decisions:
- FIFO eviction: oldest results first (data shows Q1 results have 0.896
  amplification ratio — evicting them captures the most benefit)
- No recall tool injection: if the model needs evicted content, it already
  knows how to re-issue the tool call (Read, Grep, etc.). The "page fault"
  is just a new tool call. PDP-11 overlays, not virtual memory.
- Error results are never evicted (the model needs those for debugging)
- Small results (<min_size bytes) aren't worth compacting

Metrics for success (from Tony):
- Lower token consumption
- Better quality output (fewer tokens → LLMs work better)
- Faster responses
- Slower consumption of the context window
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class PageEntry:
    """A single evicted tool result."""

    tool_use_id: str
    tool_name: str
    tool_input: dict
    original_content: str | list
    original_size: int
    summary: str
    evicted_at: float  # time.monotonic()
    turn_index: int
    turns_from_end: int


@dataclass
class PageFault:
    """A tool call that re-requests evicted content."""

    tool_use_id: str
    tool_name: str
    tool_input: dict
    original_eviction: PageEntry
    detected_at: float  # time.monotonic()


@dataclass
class CompactionStats:
    """What happened during a single compaction pass."""

    total_tool_results: int = 0
    evicted_count: int = 0
    bytes_before: int = 0
    bytes_after: int = 0
    skipped_small: int = 0
    skipped_recent: int = 0
    skipped_error: int = 0

    @property
    def bytes_saved(self) -> int:
        return self.bytes_before - self.bytes_after

    @property
    def reduction_pct(self) -> float:
        if self.bytes_before == 0:
            return 0.0
        return (self.bytes_saved / self.bytes_before) * 100


class PageStore:
    """Stores evicted tool result content and detects page faults.

    In-memory for now. The page file is for analysis, not production.

    A page fault is when the model re-issues a tool call for content
    that was evicted. This is the key observability signal: it tells
    us whether eviction was wrong (costly) or right (content was dead).
    """

    def __init__(self, log_path: Path | None = None):
        self.pages: dict[str, PageEntry] = {}
        self.log_path = log_path
        self.cumulative_bytes_saved: int = 0
        self.cumulative_evictions: int = 0
        self.faults: list[PageFault] = []
        # Index for fault detection: (tool_name, key) → PageEntry
        # Key is the identifying parameter (file_path for Read, etc.)
        self._eviction_index: dict[tuple[str, str], PageEntry] = {}

    def store(self, entry: PageEntry) -> None:
        self.pages[entry.tool_use_id] = entry
        self.cumulative_bytes_saved += entry.original_size - len(
            entry.summary.encode("utf-8")
        )
        self.cumulative_evictions += 1

        # Index for fault detection
        key = _eviction_key(entry.tool_name, entry.tool_input)
        if key is not None:
            self._eviction_index[(entry.tool_name, key)] = entry

        if self.log_path is not None:
            record = {
                "type": "eviction",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tool_use_id": entry.tool_use_id,
                "tool_name": entry.tool_name,
                "original_size": entry.original_size,
                "summary_size": len(entry.summary.encode("utf-8")),
                "turn_index": entry.turn_index,
                "turns_from_end": entry.turns_from_end,
            }
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")

    def detect_faults(self, messages: list[dict]) -> list[PageFault]:
        """Scan recent tool_use blocks for re-requests of evicted content.

        Looks at tool_use blocks in assistant messages and checks if any
        match evicted pages. A match means the model needed content we
        took away — a page fault.
        """
        new_faults = []
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") != "tool_use":
                    continue

                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                tool_use_id = block.get("id", "")

                # Skip the original tool_use that produced the
                # evicted result — that's not a fault, it's history
                if tool_use_id in self.pages:
                    continue

                key = _eviction_key(tool_name, tool_input)
                if key is None:
                    continue

                evicted = self._eviction_index.get((tool_name, key))
                if evicted is None:
                    continue

                # Don't double-count: check if this tool_use_id
                # was already recorded as a fault
                if any(f.tool_use_id == tool_use_id for f in self.faults):
                    continue

                fault = PageFault(
                    tool_use_id=tool_use_id,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    original_eviction=evicted,
                    detected_at=time.monotonic(),
                )
                new_faults.append(fault)
                self.faults.append(fault)

                if self.log_path is not None:
                    record = {
                        "type": "page_fault",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "tool_name": tool_name,
                        "eviction_key": key,
                        "original_tool_use_id": evicted.tool_use_id,
                        "original_size": evicted.original_size,
                        "original_turn": evicted.turn_index,
                    }
                    with open(self.log_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(record) + "\n")

        return new_faults

    def retrieve(self, tool_use_id: str) -> PageEntry | None:
        return self.pages.get(tool_use_id)

    def summary(self) -> dict:
        """Current state for the health endpoint."""
        return {
            "total_evictions": self.cumulative_evictions,
            "total_bytes_saved": self.cumulative_bytes_saved,
            "total_page_faults": len(self.faults),
            "fault_rate": (
                len(self.faults) / self.cumulative_evictions
                if self.cumulative_evictions > 0
                else 0.0
            ),
            "pages_in_store": len(self.pages),
            "faults_by_tool": _count_by(
                self.faults, lambda f: f.tool_name
            ),
            "evictions_by_tool": _count_by(
                list(self.pages.values()), lambda p: p.tool_name
            ),
        }


def _count_by(items: list, key_fn) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        k = key_fn(item)
        counts[k] = counts.get(k, 0) + 1
    return counts


def _eviction_key(tool_name: str, tool_input: dict) -> str | None:
    """Extract the identifying key for a tool call, for fault matching.

    Returns None for tools where re-invocation isn't meaningful
    (e.g., Agent results can't be re-requested by input match).
    """
    if tool_name == "Read":
        return tool_input.get("file_path")
    elif tool_name == "Grep":
        # pattern + path is the identity
        pattern = tool_input.get("pattern", "")
        path = tool_input.get("path", ".")
        return f"{pattern}@{path}"
    elif tool_name == "Glob":
        return tool_input.get("pattern")
    elif tool_name == "Bash":
        return tool_input.get("command")
    elif tool_name == "WebFetch":
        return tool_input.get("url")
    elif tool_name == "WebSearch":
        return tool_input.get("query")
    return None


def _content_size(content: str | list | None) -> int:
    """Measure content size in bytes."""
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content.encode("utf-8"))
    return len(json.dumps(content).encode("utf-8"))


def _build_tool_use_index(messages: list[dict]) -> dict[str, dict]:
    """Map tool_use_id → {name, input} from assistant messages."""
    index = {}
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                index[block["id"]] = {
                    "name": block.get("name", "unknown"),
                    "input": block.get("input", {}),
                }
    return index


def _make_summary(tool_name: str, tool_input: dict, original_size: int,
                  original_content: str | list | None = None) -> str:
    """Generate a compact summary for an evicted tool result.

    The summary tells the model what WAS here and how to get it back
    (re-issue the same tool call). No magic — just information.
    """
    size_str = f"{original_size:,}"

    if tool_name == "Read":
        path = tool_input.get("file_path", "unknown")
        line_count = ""
        if isinstance(original_content, str):
            lines = original_content.count("\n")
            line_count = f", {lines} lines"
        return (
            f"[Paged out: Read {path} ({size_str} bytes{line_count}). "
            f"Re-read the file if you need its content.]"
        )

    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "?")
        path = tool_input.get("path", ".")
        mode = tool_input.get("output_mode", "files_with_matches")
        # Count result lines if string content
        match_info = ""
        if isinstance(original_content, str):
            result_lines = len(original_content.strip().splitlines())
            match_info = f", {result_lines} result lines"
        return (
            f"[Paged out: Grep '{pattern}' in {path} "
            f"(mode={mode}{match_info}, {size_str} bytes). "
            f"Re-run the search if you need results.]"
        )

    elif tool_name == "Glob":
        pattern = tool_input.get("pattern", "?")
        match_info = ""
        if isinstance(original_content, str):
            matches = len(original_content.strip().splitlines())
            match_info = f", {matches} matches"
        return (
            f"[Paged out: Glob '{pattern}'{match_info} ({size_str} bytes). "
            f"Re-run if you need the file list.]"
        )

    elif tool_name == "Bash":
        cmd = tool_input.get("command", "?")
        # Truncate long commands
        if len(cmd) > 120:
            cmd = cmd[:117] + "..."
        return (
            f"[Paged out: Bash `{cmd}` ({size_str} bytes). "
            f"Re-run the command if you need its output.]"
        )

    elif tool_name == "WebFetch":
        url = tool_input.get("url", "?")
        return (
            f"[Paged out: WebFetch {url} ({size_str} bytes). "
            f"Re-fetch if you need the content.]"
        )

    elif tool_name == "WebSearch":
        query = tool_input.get("query", "?")
        return (
            f"[Paged out: WebSearch '{query}' ({size_str} bytes). "
            f"Re-search if you need results.]"
        )

    elif tool_name in ("Agent", "TaskOutput"):
        return (
            f"[Paged out: {tool_name} result ({size_str} bytes). "
            f"Content was consumed when originally returned.]"
        )

    else:
        return (
            f"[Paged out: {tool_name} ({size_str} bytes). "
            f"Re-invoke the tool if you need this content.]"
        )


def compact_messages(
    messages: list[dict],
    age_threshold: int = 4,
    min_size: int = 500,
    page_store: PageStore | None = None,
) -> CompactionStats:
    """Replace old, large tool results with compact summaries.

    Mutates the messages list in place. Returns stats about what was done.

    Args:
        messages: The messages array from the API request body.
        age_threshold: Results older than this many user-turns from the
            end get evicted. Default 4.
        min_size: Results smaller than this (bytes) are kept as-is.
            Not worth compacting a 22-byte Edit confirmation. Default 500.
        page_store: If provided, evicted content is stored here.
    """
    stats = CompactionStats()
    tool_use_index = _build_tool_use_index(messages)

    # Count user turns (each user message is a "turn")
    user_turn_indices: list[int] = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            user_turn_indices.append(i)

    total_user_turns = len(user_turn_indices)

    # Walk through messages and compact old tool results
    current_user_turn = 0
    for msg_idx, msg in enumerate(messages):
        if msg.get("role") != "user":
            continue

        current_user_turn += 1
        turns_from_end = total_user_turns - current_user_turn

        content = msg.get("content", [])
        if not isinstance(content, list):
            continue

        for block_idx, block in enumerate(content):
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_result":
                continue

            stats.total_tool_results += 1
            original_content = block.get("content", "")
            original_size = _content_size(original_content)

            # Skip errors — model needs those
            if block.get("is_error", False):
                stats.skipped_error += 1
                continue

            # Skip recent results
            if turns_from_end < age_threshold:
                stats.skipped_recent += 1
                stats.bytes_before += original_size
                stats.bytes_after += original_size
                continue

            # Skip small results
            if original_size < min_size:
                stats.skipped_small += 1
                stats.bytes_before += original_size
                stats.bytes_after += original_size
                continue

            # This result gets evicted
            tool_use_id = block.get("tool_use_id", "")
            tool_info = tool_use_index.get(tool_use_id, {})
            tool_name = tool_info.get("name", "unknown")
            tool_input = tool_info.get("input", {})

            summary = _make_summary(
                tool_name, tool_input, original_size, original_content
            )

            # Store the original
            if page_store is not None:
                entry = PageEntry(
                    tool_use_id=tool_use_id,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    original_content=original_content,
                    original_size=original_size,
                    summary=summary,
                    evicted_at=time.monotonic(),
                    turn_index=current_user_turn,
                    turns_from_end=turns_from_end,
                )
                page_store.store(entry)

            # Replace the content
            content[block_idx] = {**block, "content": summary}

            stats.evicted_count += 1
            stats.bytes_before += original_size
            stats.bytes_after += len(summary.encode("utf-8"))

    return stats
