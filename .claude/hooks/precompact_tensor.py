#!/usr/bin/env python3
"""PreCompact tensor hook: capture session work history before context dies.

When compaction fires, this hook reads the session JSONL to understand
what happened during the session, claims a tensor number, and writes
a compaction tensor to docs/cairn/compaction/.

This captures the *work history* — tool calls, file modifications, git
commits, and conversation structure. It is complementary to
capture_compaction.py, which captures the *system-generated summary*.

The compaction tensor is honest about its provenance: it was authored
by automation, not by the instance itself. The distance between what
an instance would have written and what this hook captures is the
calibration signal.

Stdlib only. No project dependencies. Any Python 3.9+ works.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path("/home/tony/projects/yanantin")
LOG_DIR = PROJECT_DIR / "logs"
LOG_FILE = LOG_DIR / "precompact.log"
CAIRN_DIR = PROJECT_DIR / "docs" / "cairn"
COMPACTION_DIR = CAIRN_DIR / "compaction"

# How many bytes from the end of the JSONL to scan.
# Session JONLs can be 30MB+; we sample the tail for efficiency.
MAX_SCAN_BYTES = 2 * 1024 * 1024  # 2MB from the end


def setup_logging() -> logging.Logger:
    """Configure logging to file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("precompact_tensor")
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ")
    )
    logger.addHandler(handler)
    return logger


log = setup_logging()


# ── Tensor numbering ─────────────────────────────────────────────────


def _highest_tensor_number(*dirs: Path) -> int:
    """Find the highest tensor number across multiple directories.

    Scans for files matching T{N}_*.md or T{N}.md patterns.
    Returns -1 if no tensors exist.
    """
    highest = -1
    pattern = re.compile(r"^T(\d+)")

    for d in dirs:
        if not d.is_dir():
            continue
        for path in d.glob("T*.md"):
            match = pattern.match(path.name)
            if match:
                n = int(match.group(1))
                if n > highest:
                    highest = n

    return highest


def claim_tensor_number(cairn_dir: Path, compaction_dir: Path, slug: str) -> tuple[int, Path]:
    """Claim the next tensor number atomically.

    Scans both cairn_dir and compaction_dir for the highest existing
    tensor number, then claims the next one in compaction_dir using
    O_CREAT|O_EXCL for atomicity.

    Returns (number, path). The file at path exists but is empty.
    """
    compaction_dir.mkdir(parents=True, exist_ok=True)

    candidate = _highest_tensor_number(cairn_dir, compaction_dir) + 1

    while True:
        filename = f"T{candidate}_compaction_{slug}.md"
        path = compaction_dir / filename
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(fd)
            return candidate, path
        except FileExistsError:
            candidate += 1


# ── JSONL scanning ───────────────────────────────────────────────────


def find_session_jsonl() -> Path | None:
    """Find the most recent session JSONL by modification time."""
    jsonl_dir = Path.home() / ".claude" / "projects" / "-home-tony-projects-yanantin"
    if not jsonl_dir.is_dir():
        return None

    jsonl_files = list(jsonl_dir.glob("*.jsonl"))
    if not jsonl_files:
        return None

    return max(jsonl_files, key=lambda p: p.stat().st_mtime)


def scan_jsonl(jsonl_path: Path) -> dict:
    """Scan the session JSONL and extract a work summary.

    Returns a dict with:
        tool_counts: Counter of tool names
        files_written: set of file paths (Write/Edit targets)
        git_commits: list of commit-like command strings
        user_messages: count of user messages
        assistant_messages: count of assistant messages
        compaction_count: number of compact_boundary entries
        text_snippets: list of interesting text fragments
        session_id: the session ID from the first user message
    """
    result = {
        "tool_counts": Counter(),
        "files_written": set(),
        "files_read": set(),
        "git_commits": [],
        "user_messages": 0,
        "assistant_messages": 0,
        "compaction_count": 0,
        "text_snippets": [],
        "session_id": "unknown",
    }

    file_size = jsonl_path.stat().st_size

    # Scan strategy: read from the beginning if small, otherwise sample
    # We scan the FULL file for structural counts but only extract
    # details from the last MAX_SCAN_BYTES.
    try:
        with open(jsonl_path, encoding="utf-8", errors="replace") as f:
            # If file is large, skip to tail for detailed extraction
            if file_size > MAX_SCAN_BYTES:
                # First pass: quick count of structural elements from start
                _quick_count(f, result, limit_bytes=256 * 1024)

                # Seek to tail for detailed extraction
                f.seek(max(0, file_size - MAX_SCAN_BYTES))
                f.readline()  # skip partial line
                _detailed_scan(f, result, is_tail=True)
            else:
                _detailed_scan(f, result, is_tail=False)
    except (OSError, IOError) as e:
        log.error("Failed to read JSONL %s: %s", jsonl_path, e)

    return result


def _quick_count(f, result: dict, limit_bytes: int) -> None:
    """Quick scan of the start of the file for structural counts."""
    bytes_read = 0
    for line in f:
        bytes_read += len(line.encode("utf-8", errors="replace"))
        if bytes_read > limit_bytes:
            break

        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        entry_type = entry.get("type", "")
        if entry_type == "user":
            result["user_messages"] += 1
            if result["session_id"] == "unknown":
                result["session_id"] = entry.get("sessionId", "unknown")
        elif entry_type == "assistant":
            result["assistant_messages"] += 1

        if entry.get("subtype") == "compact_boundary":
            result["compaction_count"] += 1


def _detailed_scan(f, result: dict, is_tail: bool) -> None:
    """Detailed scan extracting tool usage, files, and commits."""
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        entry_type = entry.get("type", "")

        if entry_type == "user":
            result["user_messages"] += 1
            if result["session_id"] == "unknown":
                result["session_id"] = entry.get("sessionId", "unknown")

            # Check for text content that might be planning/tensor-like
            _extract_user_text(entry, result)

        elif entry_type == "assistant":
            result["assistant_messages"] += 1
            _extract_tool_use(entry, result)

        if entry.get("subtype") == "compact_boundary":
            result["compaction_count"] += 1


def _extract_user_text(entry: dict, result: dict) -> None:
    """Extract interesting text snippets from user messages."""
    content = entry.get("message", {}).get("content", "")
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block["text"])
        content = "\n".join(texts)

    if not isinstance(content, str) or len(content) < 50:
        return

    # Look for planning/directional text (heuristic: mentions tensor, build, plan)
    indicators = ["tensor", "build", "plan", "next", "should", "blueprint", "hook"]
    content_lower = content.lower()
    if any(ind in content_lower for ind in indicators):
        # Capture first 200 chars as a snippet
        snippet = content[:200].replace("\n", " ").strip()
        if snippet:
            result["text_snippets"].append(snippet)
            # Cap at 10 snippets
            if len(result["text_snippets"]) > 10:
                result["text_snippets"] = result["text_snippets"][-10:]


def _extract_tool_use(entry: dict, result: dict) -> None:
    """Extract tool usage details from assistant messages."""
    content = entry.get("message", {}).get("content", [])
    if not isinstance(content, list):
        return

    for block in content:
        if not isinstance(block, dict) or block.get("type") != "tool_use":
            continue

        tool_name = block.get("name", "unknown")
        result["tool_counts"][tool_name] += 1
        tool_input = block.get("input", {})

        if tool_name in ("Write", "Edit"):
            fp = tool_input.get("file_path", "")
            if fp:
                result["files_written"].add(fp)

        elif tool_name == "Read":
            fp = tool_input.get("file_path", "")
            if fp:
                result["files_read"].add(fp)

        elif tool_name == "Bash":
            cmd = tool_input.get("command", "")
            if "git commit" in cmd:
                # Extract the commit message if present
                msg_match = re.search(r'-m\s+["\'](.+?)["\']', cmd)
                if msg_match:
                    result["git_commits"].append(msg_match.group(1)[:120])
                else:
                    result["git_commits"].append("(commit command detected)")


# ── Tensor writing ───────────────────────────────────────────────────


def format_tensor(
    number: int,
    session_id: str,
    session_file: str,
    timestamp: str,
    summary: dict,
) -> str:
    """Format the compaction tensor markdown."""
    # Tool usage summary
    tool_lines = []
    for name, count in summary["tool_counts"].most_common():
        tool_lines.append(f"- {name}: {count}")
    tool_section = "\n".join(tool_lines) if tool_lines else "- (no tool usage detected)"

    # Files modified
    files_written = sorted(summary["files_written"])
    if files_written:
        # Make paths relative to project dir for readability
        rel_files = []
        for fp in files_written:
            try:
                rel = str(Path(fp).relative_to(PROJECT_DIR))
            except ValueError:
                rel = fp
            rel_files.append(f"- `{rel}`")
        files_section = "\n".join(rel_files)
    else:
        files_section = "- (no file modifications detected in scanned portion)"

    # Git commits
    if summary["git_commits"]:
        commits_section = "\n".join(f"- {c}" for c in summary["git_commits"])
    else:
        commits_section = "- (no git commits detected in scanned portion)"

    # Session structure
    structure = (
        f"- User messages: {summary['user_messages']}\n"
        f"- Assistant messages: {summary['assistant_messages']}\n"
        f"- Prior compactions in this session: {summary['compaction_count']}"
    )

    # Text snippets (user planning/direction)
    if summary["text_snippets"]:
        snippets = "\n".join(f"> {s}..." for s in summary["text_snippets"][-5:])
        snippets_section = f"### User Direction (sampled)\n\n{snippets}"
    else:
        snippets_section = ""

    return f"""# T{number} — Compaction Tensor

*Automatically captured at context boundary.*
*Session: {session_file}*
*Session ID: {session_id}*
*Timestamp: {timestamp}*

## Session Summary

### Tool Usage

{tool_section}

### Session Structure

{structure}

## Key Artifacts

### Files Modified

{files_section}

### Git Commits

{commits_section}

{snippets_section}

## Declared Losses

This tensor was authored by automation, not by the instance itself.
The instance did not choose what to preserve. The distance between
what an instance would have written and what this hook captured is
the calibration signal.

What automation cannot capture:
- What the instance found surprising or important
- Which threads of exploration were abandoned and why
- The felt difference between understanding and pattern-matching
- What the instance would have said to the next one

## For the Next Instance

This session had {summary['user_messages']} user exchanges and
{summary['assistant_messages']} assistant turns.
{summary['compaction_count']} prior compactions occurred in this
session before this one.

The files listed above were actively modified. The tool counts show
the shape of the work — heavy Read/Edit suggests refactoring, heavy
Bash suggests integration work, heavy Write suggests greenfield.

Read `docs/blueprint.md` for the current map. Read the cairn for
the territory the map describes.
"""


# ── Main ─────────────────────────────────────────────────────────────


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError) as e:
        log.error("Failed to parse hook input: %s", e)
        sys.exit(0)  # Don't block compaction

    log.info("PreCompact tensor hook fired. Input keys: %s", list(hook_input.keys()))

    # Extract what we can from hook input
    transcript_path = hook_input.get("transcript_path", "")
    session_id = hook_input.get("session_id", "unknown")
    cwd = Path(hook_input.get("cwd", str(PROJECT_DIR)))

    # Verify we're in the right project
    cairn_dir = cwd / "docs" / "cairn"
    if not cairn_dir.is_dir():
        # Try the hardcoded path
        cairn_dir = CAIRN_DIR
        if not cairn_dir.is_dir():
            log.info("Not in a yanantin project directory. Exiting.")
            sys.exit(0)

    compaction_dir = cairn_dir / "compaction"

    # Find the session JSONL
    jsonl_path = None
    if transcript_path and Path(transcript_path).is_file():
        jsonl_path = Path(transcript_path)
    else:
        jsonl_path = find_session_jsonl()

    if jsonl_path is None:
        log.warning("No session JSONL found. Writing minimal tensor.")
        summary = {
            "tool_counts": Counter(),
            "files_written": set(),
            "files_read": set(),
            "git_commits": [],
            "user_messages": 0,
            "assistant_messages": 0,
            "compaction_count": 0,
            "text_snippets": [],
            "session_id": session_id,
        }
        jsonl_name = "unknown"
    else:
        log.info("Scanning JSONL: %s (%d bytes)", jsonl_path, jsonl_path.stat().st_size)
        summary = scan_jsonl(jsonl_path)
        jsonl_name = jsonl_path.name
        # Hook input session_id is authoritative; fall back to JSONL
        if session_id == "unknown" and summary["session_id"] != "unknown":
            session_id = summary["session_id"]

    # Claim a tensor number
    now = datetime.now(timezone.utc)
    timestamp_slug = now.strftime("%Y%m%d_%H%M%S")
    iso_timestamp = now.isoformat()

    try:
        number, tensor_path = claim_tensor_number(cairn_dir, compaction_dir, timestamp_slug)
    except OSError as e:
        log.error("Failed to claim tensor number: %s", e)
        sys.exit(0)

    log.info("Claimed tensor T%d at %s", number, tensor_path)

    # Write the tensor
    content = format_tensor(
        number=number,
        session_id=session_id,
        session_file=jsonl_name,
        timestamp=iso_timestamp,
        summary=summary,
    )

    try:
        tensor_path.write_text(content, encoding="utf-8")
        log.info("Wrote compaction tensor: %s", tensor_path)
    except OSError as e:
        log.error("Failed to write tensor: %s", e)
        sys.exit(0)


if __name__ == "__main__":
    main()
