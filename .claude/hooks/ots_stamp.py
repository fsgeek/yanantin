#!/usr/bin/env python3
"""Post-commit OpenTimestamps hook.

Called after each git commit to create a blockchain timestamp proof.
Submits the commit's SHA-256 digest to OpenTimestamps calendar servers
and stores the pending proof in docs/ots/{short_hash}.ots.

This hook NEVER blocks the commit workflow. All calendar failures are
logged and silently ignored. A failed timestamp is information loss,
not a workflow failure.

Can be invoked in two ways:
  1. As a git post-commit hook (no arguments, gets HEAD)
  2. Directly: python ots_stamp.py [commit_hash]

Install as git hook:
    ln -sf ../../.claude/hooks/ots_stamp.py .git/hooks/post-commit

Or via .githooks:
    mkdir -p .githooks
    ln -sf ../.claude/hooks/ots_stamp.py .githooks/post-commit
    git config core.hooksPath .githooks

Logs to: logs/ots.log
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
OTS_DIR = PROJECT_DIR / "docs" / "ots"
LOG_DIR = PROJECT_DIR / "logs"
LOG_FILE = LOG_DIR / "ots.log"


def setup_logging() -> logging.Logger:
    """Configure file logging for the hook."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    hook_logger = logging.getLogger("ots_stamp")
    hook_logger.setLevel(logging.INFO)

    if not hook_logger.handlers:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        hook_logger.addHandler(handler)

    return hook_logger


def get_head_commit() -> str:
    """Get the current HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def main() -> None:
    log = setup_logging()

    # Accept commit hash as argument or read HEAD.
    if len(sys.argv) > 1:
        commit_hash = sys.argv[1].strip()
    else:
        commit_hash = get_head_commit()

    if not commit_hash:
        log.error("Could not determine commit hash")
        return

    log.info("Post-commit hook triggered for %s", commit_hash[:10])

    # Import here so the hook fails gracefully if dependencies are missing.
    try:
        from yanantin.provenance.timestamp import stamp_commit
    except ImportError as exc:
        log.error("Cannot import provenance module: %s", exc)
        return

    # Configure the provenance module's logger to also write to our log file.
    provenance_logger = logging.getLogger("yanantin.provenance.timestamp")
    provenance_logger.setLevel(logging.INFO)
    for handler in log.handlers:
        if handler not in provenance_logger.handlers:
            provenance_logger.addHandler(handler)

    try:
        result = stamp_commit(commit_hash, OTS_DIR)
        if result:
            log.info("Proof created: %s", result)
        else:
            log.warning("Stamping failed for %s (see above)", commit_hash[:10])
    except Exception as exc:
        # Never let the hook crash the workflow.
        log.error("Unexpected error stamping %s: %s", commit_hash[:10], exc)


if __name__ == "__main__":
    main()
