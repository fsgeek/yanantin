"""Coverage tracker — the watchman at the helm.

Scans the cairn to learn which source files have been reviewed by scouts
and when. Files that have never been reviewed start at epoch 0 — maximum
priority for the next dispatch.

The tracker feeds into scout file selection: instead of uniform random
sampling, files are weighted by how long ago they were last reviewed.
Stale coverage floats to the top. New code that nobody has looked at
gets the highest priority.

This exists because:
- The activity stream layer (15 files, 1443 lines) was never reviewed
  by any scout despite being a major new subsystem.
- Scout dispatch used uniform random selection, so popular files got
  reviewed repeatedly while new code was ignored.
- Without a watchman, nobody notices when code isn't getting a review.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Epoch zero — the "never reviewed" timestamp
EPOCH_ZERO = datetime(1970, 1, 1, tzinfo=timezone.utc)

# File paths in scout report content (backtick-wrapped)
_PATH_PATTERN = re.compile(
    r"`([a-zA-Z_][\w/.-]*(?:\.py|\.md|\.toml|\.yaml|\.yml)(?::\d+)?)`"
)

# Timestamp from provenance header
_TIMESTAMP_PATTERN = re.compile(r"Timestamp:\s*([\dT:.+\-Z]+)")


def _parse_report_timestamp(text: str) -> datetime:
    """Extract the timestamp from a scout report's provenance header.

    Falls back to epoch zero if the header is missing or unparseable.
    """
    match = _TIMESTAMP_PATTERN.search(text)
    if not match:
        return EPOCH_ZERO

    raw = match.group(1).strip()
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return EPOCH_ZERO


def _extract_reviewed_files(text: str) -> set[str]:
    """Extract file paths referenced in a scout report.

    Only returns the path portion (strips line numbers).
    """
    paths = set()
    for match in _PATH_PATTERN.finditer(text):
        raw = match.group(1)
        # Strip line number suffix
        path = raw.rsplit(":", 1)[0]
        paths.add(path)
    return paths


def scan_cairn_coverage(
    cairn_dir: Path,
    pattern: str = "scout_*.md",
) -> dict[str, datetime]:
    """Scan the cairn and build a coverage map.

    Returns a dict mapping project-relative file paths to the timestamp
    of the most recent scout report that referenced them. Files never
    mentioned in any report are not in the map — they get epoch zero
    implicitly when coverage_weights is called.

    Args:
        cairn_dir: Path to the cairn directory.
        pattern: Glob pattern for report files.

    Returns:
        {file_path: last_reviewed_at} for all files mentioned in reports.
    """
    if not cairn_dir.is_dir():
        logger.warning("Cairn directory does not exist: %s", cairn_dir)
        return {}

    coverage: dict[str, datetime] = {}
    report_count = 0

    for report_path in cairn_dir.glob(pattern):
        try:
            text = report_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        report_count += 1
        timestamp = _parse_report_timestamp(text)
        reviewed_files = _extract_reviewed_files(text)

        for file_path in reviewed_files:
            existing = coverage.get(file_path)
            if existing is None or timestamp > existing:
                coverage[file_path] = timestamp

    logger.info(
        "Coverage scan: %d reports, %d files tracked",
        report_count, len(coverage),
    )
    return coverage


def coverage_weights(
    candidates: list[Path],
    coverage_map: dict[str, datetime],
    project_root: Path,
    now: datetime | None = None,
) -> list[float]:
    """Compute selection weights based on coverage freshness.

    Weight = seconds since last review. Files never reviewed (not in
    coverage_map) use epoch zero — maximum weight. Recently reviewed
    files get low weight but never zero (minimum weight is 1.0 so
    every file has some chance of being selected).

    Args:
        candidates: List of candidate file paths (absolute).
        coverage_map: {relative_path: last_reviewed_at} from scan_cairn_coverage.
        project_root: Project root for computing relative paths.
        now: Current time. Defaults to UTC now.

    Returns:
        List of weights, same length as candidates.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    weights = []
    for path in candidates:
        try:
            rel = str(path.relative_to(project_root))
        except ValueError:
            rel = str(path)

        last_reviewed = coverage_map.get(rel, EPOCH_ZERO)
        age_seconds = (now - last_reviewed).total_seconds()
        # Minimum weight of 1.0 so every file has some chance
        weights.append(max(1.0, age_seconds))

    return weights


def coverage_report(
    coverage_map: dict[str, datetime],
    project_root: Path,
    source_extensions: frozenset[str] = frozenset({".py"}),
) -> dict[str, datetime | None]:
    """Build a full coverage report for all source files.

    Returns a dict mapping every source file in the project to its
    last-reviewed timestamp, or None if never reviewed. This is the
    view the watchman sees.

    Args:
        coverage_map: {relative_path: last_reviewed_at} from scan_cairn_coverage.
        project_root: Project root directory.
        source_extensions: File extensions to include.

    Returns:
        {relative_path: last_reviewed_at_or_None}
    """
    skip_dirs = {"__pycache__", ".git", ".venv", ".uv-cache", ".serena", ".pytest_cache"}

    all_files: dict[str, datetime | None] = {}
    for ext in source_extensions:
        for path in project_root.rglob(f"*{ext}"):
            if any(d in path.parts for d in skip_dirs):
                continue
            if not path.is_file():
                continue
            rel = str(path.relative_to(project_root))
            all_files[rel] = coverage_map.get(rel)

    return all_files


def unreviewed_files(
    coverage_map: dict[str, datetime],
    project_root: Path,
    source_extensions: frozenset[str] = frozenset({".py"}),
) -> list[str]:
    """List source files that have never been reviewed by a scout.

    Sorted alphabetically. This is the "urgent attention" list.
    """
    report = coverage_report(coverage_map, project_root, source_extensions)
    return sorted(path for path, ts in report.items() if ts is None)


def stalest_files(
    coverage_map: dict[str, datetime],
    project_root: Path,
    n: int = 10,
    source_extensions: frozenset[str] = frozenset({".py"}),
) -> list[tuple[str, datetime | None]]:
    """Return the N files with the oldest (or missing) coverage.

    Never-reviewed files come first (sorted by path), then files
    sorted by last-reviewed timestamp ascending (oldest first).
    """
    report = coverage_report(coverage_map, project_root, source_extensions)

    never_reviewed = [(p, None) for p, ts in report.items() if ts is None]
    never_reviewed.sort(key=lambda x: x[0])

    reviewed = [(p, ts) for p, ts in report.items() if ts is not None]
    reviewed.sort(key=lambda x: x[1])  # type: ignore[arg-type]

    return (never_reviewed + reviewed)[:n]
