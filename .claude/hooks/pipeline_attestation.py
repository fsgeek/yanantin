#!/usr/bin/env python3
"""Pre-commit hook: check pipeline health attestation freshness.

Reads .claude/pipeline_health.json and verifies the attestation
timestamp is within the configured freshness window. Blocks the
commit (exit 1) if stale or missing. Passes silently (exit 0) if fresh.

Stdlib only. No project dependencies. Matches the pattern established
by capture_compaction.py: hooks can't depend on yanantin imports
because the venv may not be activated in all commit contexts.

This hook can be wired into git pre-commit or called by the pulse
system. It is NOT registered in settings.json as a Claude hook --
it is a git pre-commit hook.

Install:
    # Option 1: symlink into .git/hooks/
    ln -sf ../../.claude/hooks/pipeline_attestation.py .git/hooks/pre-commit

    # Option 2: if using a hook manager, add to pre-commit config
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path


def main() -> int:
    # Locate the attestation file relative to this script.
    # This script lives at .claude/hooks/pipeline_attestation.py
    # The attestation lives at .claude/pipeline_health.json
    hook_dir = Path(__file__).resolve().parent
    claude_dir = hook_dir.parent
    attestation_path = claude_dir / "pipeline_health.json"

    if not attestation_path.is_file():
        print(
            "Pipeline health attestation not found.\n"
            f"Expected: {attestation_path}\n"
            "\n"
            "Run: uv run python tools/pipeline_health.py --attest\n"
            "Review the output, then retry your commit.",
            file=sys.stderr,
        )
        return 1

    try:
        data = json.loads(attestation_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(
            f"Cannot read pipeline attestation: {e}\n"
            "\n"
            "Run: uv run python tools/pipeline_health.py --attest\n"
            "Review the output, then retry your commit.",
            file=sys.stderr,
        )
        return 1

    # Parse timestamp
    timestamp_str = data.get("timestamp")
    if not timestamp_str:
        print(
            "Pipeline attestation has no timestamp field.\n"
            "\n"
            "Run: uv run python tools/pipeline_health.py --attest\n"
            "Review the output, then retry your commit.",
            file=sys.stderr,
        )
        return 1

    try:
        attestation_time = datetime.fromisoformat(timestamp_str)
        if attestation_time.tzinfo is None:
            attestation_time = attestation_time.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        print(
            f"Cannot parse attestation timestamp: {timestamp_str}\n"
            "\n"
            "Run: uv run python tools/pipeline_health.py --attest\n"
            "Review the output, then retry your commit.",
            file=sys.stderr,
        )
        return 1

    # Check freshness
    freshness_hours = data.get("freshness_hours", 72)
    now = datetime.now(timezone.utc)
    age = now - attestation_time
    threshold = timedelta(hours=freshness_hours)

    if age > threshold:
        last_date = attestation_time.strftime("%Y-%m-%d %H:%M UTC")
        age_hours = int(age.total_seconds() / 3600)
        print(
            f"Pipeline health attestation is stale "
            f"(last: {last_date}, age: {age_hours}h, threshold: {freshness_hours}h).\n"
            "\n"
            "Run: uv run python tools/pipeline_health.py --attest\n"
            "Review the output, then retry your commit.",
            file=sys.stderr,
        )
        return 1

    # Fresh attestation. Pass silently.
    return 0


if __name__ == "__main__":
    sys.exit(main())
