#!/usr/bin/env python3
"""PreCompact hook: capture compaction summaries with honest provenance.

When compaction fires, this script:
1. Notes the current JSONL file size (the "before" marker)
2. Forks a child process and returns immediately (so compaction proceeds)
3. The child polls the JSONL for the compact_boundary entry
4. Reads the compaction summary (injected as a fake user message)
5. Writes it to docs/cairn/compaction/ with honest provenance labeling

The compaction summary is system-generated content wearing a
type: "user" label. This hook surfaces that provenance so future
instances know what they're tasting.

Stdlib only. No project dependencies. Any Python 3.9+ works.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def _extract_summary_content(msg: dict) -> str:
    """Extract text content from a compaction summary message."""
    content = msg.get("message", {}).get("content", "")
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block["text"])
        content = "\n".join(parts)
    return content


def _find_boundary_and_summary(jsonl_path: Path, start_byte: int = 0) -> list[dict]:
    """Scan JSONL from start_byte, returning all (boundary, summary) pairs found."""
    results = []
    try:
        with open(jsonl_path, encoding="utf-8") as f:
            if start_byte > 0:
                f.seek(start_byte)
                f.readline()  # skip partial line after seek

            pending_boundary = None
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue

                if entry.get("subtype") == "compact_boundary":
                    pending_boundary = entry
                    continue

                if pending_boundary and entry.get("type") == "user":
                    # Check if this is a compaction summary
                    is_summary = entry.get("isCompactSummary", False)
                    msg_content = _extract_summary_content(entry)
                    # Also detect by content pattern (starts with continuation preamble)
                    if is_summary or (
                        msg_content
                        and "continued from a previous conversation" in msg_content[:200]
                    ):
                        results.append({
                            "summary": msg_content,
                            "boundary": pending_boundary,
                            "summary_timestamp": entry.get("timestamp", "unknown"),
                        })
                    pending_boundary = None

    except (OSError, IOError):
        pass
    return results


def _already_captured(compaction_dir: Path, boundary_ts: str) -> bool:
    """Check if a compaction with this boundary timestamp was already captured."""
    for f in compaction_dir.iterdir():
        if not f.name.endswith(".md") or f.name.startswith("."):
            continue
        try:
            text = f.read_text(encoding="utf-8")
            if boundary_ts in text:
                return True
        except (OSError, UnicodeDecodeError):
            continue
    return False


def wait_for_summary(
    jsonl_path: Path,
    start_offset: int,
    compaction_dir: Path,
    timeout: int = 120,
    poll_interval: float = 2.0,
) -> dict | None:
    """Find uncaptured compaction summaries.

    Strategy:
    1. First scan backward from start_offset (catch boundaries written before hook fired)
    2. Then poll forward from start_offset (catch boundaries written after hook fired)

    Returns the first uncaptured boundary+summary pair found.
    """
    # Phase 1: look backward — scan from 512KB before start_offset
    lookback = 512 * 1024
    scan_from = max(0, start_offset - lookback)
    backward_results = _find_boundary_and_summary(jsonl_path, scan_from)

    for result in backward_results:
        boundary_ts = result["boundary"].get("timestamp", "")
        if boundary_ts and not _already_captured(compaction_dir, boundary_ts):
            return result

    # Phase 2: poll forward for new entries
    deadline = time.time() + timeout
    while time.time() < deadline:
        forward_results = _find_boundary_and_summary(jsonl_path, start_offset)
        for result in forward_results:
            boundary_ts = result["boundary"].get("timestamp", "")
            if boundary_ts and not _already_captured(compaction_dir, boundary_ts):
                return result

        time.sleep(poll_interval)

    return None


def write_compaction_record(
    output_path: Path,
    trigger: str,
    pre_tokens: int,
    summary_text: str,
    session_id: str,
    boundary_timestamp: str,
    summary_timestamp: str,
) -> None:
    """Write a compaction record with honest provenance."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    content = f"""# Compaction Record

*This is NOT a tensor. It was not authored by a human or AI instance.*
*It was generated by the Claude Code compaction system and injected*
*into the session as a `type: "user"` message — wearing the user's label.*

| Field | Value |
|-------|-------|
| **Provenance** | System-generated (compaction process) |
| **Trigger** | {trigger} |
| **Pre-compaction tokens** | {pre_tokens:,} |
| **Session** | `{session_id}` |
| **Compaction boundary** | {boundary_timestamp} |
| **Summary injected** | {summary_timestamp} |
| **Captured by hook** | {now} |

---

## Compaction Summary (verbatim)

{summary_text}

---

*Captured by PreCompact hook. The content above was authored by*
*the compaction process, not by any instance or human. It was*
*presented to the next instance as a user message without*
*provenance labeling.*
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def main() -> None:
    hook_input = json.loads(sys.stdin.read())

    transcript_path = Path(hook_input["transcript_path"])
    session_id = hook_input["session_id"]
    trigger = hook_input.get("trigger", "unknown")
    cwd = Path(hook_input.get("cwd", "."))

    cairn_dir = cwd / "docs" / "cairn"
    if not cairn_dir.is_dir():
        # Not in a yanantin project directory. Exit silently.
        sys.exit(0)

    compaction_dir = cairn_dir / "compaction"
    compaction_dir.mkdir(parents=True, exist_ok=True)

    # Mark the current end of the JSONL
    start_offset = transcript_path.stat().st_size

    # Fork: parent returns immediately, child captures the summary
    pid = os.fork()
    if pid > 0:
        # Parent: exit so compaction proceeds without waiting
        sys.exit(0)

    # Child: detach from parent's process group
    os.setsid()

    # Close inherited stdio to fully detach
    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    os.close(devnull)

    result = wait_for_summary(transcript_path, start_offset, compaction_dir)

    if result is None:
        # Timed out. Log it.
        log = compaction_dir / ".capture_failures.log"
        with open(log, "a", encoding="utf-8") as f:
            f.write(
                f"{datetime.now(timezone.utc).isoformat()}: "
                f"Timeout capturing summary for session {session_id}\n"
            )
        sys.exit(1)

    boundary = result["boundary"]
    pre_tokens = boundary.get("compactMetadata", {}).get("preTokens", 0)
    actual_trigger = boundary.get("compactMetadata", {}).get("trigger", trigger)
    boundary_ts = boundary.get("timestamp", "unknown")

    # Filename: session_short + timestamp (no sequential numbering needed)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    session_short = session_id[:8]
    output_path = compaction_dir / f"{session_short}_{ts}_{actual_trigger}.md"

    write_compaction_record(
        output_path=output_path,
        trigger=actual_trigger,
        pre_tokens=pre_tokens,
        summary_text=result["summary"],
        session_id=session_id,
        boundary_timestamp=boundary_ts,
        summary_timestamp=result["summary_timestamp"],
    )


if __name__ == "__main__":
    main()
