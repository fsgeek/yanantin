"""Tensor numbering ballot — atomic claim of the next tensor number.

Lamport's bakery on POSIX: scan existing T*.md files for the highest
number, then claim the next one with O_CREAT|O_EXCL. Safe across
concurrent instances and projects.

Same pattern as Chasqui's scout numbering, different namespace.
Scouts are numbered within a date+model. Tensors are numbered globally.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path


def _highest_tensor_number(cairn_dir: Path) -> int:
    """Find the highest tensor number in the cairn.

    Scans for files matching T{N}_*.md or T{N}.md patterns.
    Returns -1 if no tensors exist.
    """
    highest = -1
    pattern = re.compile(r"^T(\d+)")

    for path in cairn_dir.glob("T*.md"):
        match = pattern.match(path.name)
        if match:
            n = int(match.group(1))
            if n > highest:
                highest = n

    return highest


def claim_tensor_number(
    cairn_dir: Path,
    title_slug: str,
    date: datetime | None = None,
) -> tuple[int, Path]:
    """Claim the next tensor number atomically.

    Uses O_CREAT|O_EXCL to prevent two instances from claiming the
    same number. If the file already exists, increments and retries.

    Args:
        cairn_dir: Path to docs/cairn/ directory.
        title_slug: Short title for the filename (e.g., "the_wheel").
            Will be lowercased and cleaned.
        date: Date for the filename. Defaults to today (UTC).

    Returns:
        Tuple of (tensor_number, claimed_path).
        The file at claimed_path exists but is empty — caller fills it.
    """
    cairn_dir.mkdir(parents=True, exist_ok=True)

    if date is None:
        date = datetime.now(timezone.utc)

    date_str = date.strftime("%Y%m%d")
    slug = re.sub(r"[^a-z0-9_]", "", title_slug.lower().replace(" ", "_").replace("-", "_"))

    # Start from one above the highest existing number
    candidate = _highest_tensor_number(cairn_dir) + 1

    # Bakery loop: try to claim this number atomically
    while True:
        filename = f"T{candidate}_{date_str}_{slug}.md"
        path = cairn_dir / filename
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(fd)
            return candidate, path
        except FileExistsError:
            candidate += 1


def next_tensor_number(cairn_dir: Path) -> int:
    """Peek at the next available tensor number without claiming it.

    Useful for display/planning. Does NOT create a file.
    """
    return _highest_tensor_number(cairn_dir) + 1
