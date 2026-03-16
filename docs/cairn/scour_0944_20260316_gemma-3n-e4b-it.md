<!-- Chasqui Scour Tensor
     Run: 944
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Target: src/yanantin/chasqui
     Scope: introspection
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 18616, 'completion_tokens': 1409, 'total_tokens': 20025, 'cost': 0.00042868, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00042868, 'upstream_inference_prompt_cost': 0.00037232, 'upstream_inference_completions_cost': 5.636e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-16T15:08:50.743857+00:00
-->

```python
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


def _lookup_coverage_or_none(
    rel_path: str,
    coverage_map: dict[str, datetime],
    basename_index: dict[str, datetime],
) -> datetime | None:
    """Like _lookup_coverage, but returns None instead of EPOCH_ZERO."""
    exact = coverage_map.get(rel_path)
    if exact is not None:
        return exact

    basename = rel_path.rsplit("/", 1)[-1] if "/" in rel_path else rel_path
    base_ts = basename_index.get(basename)
    if base_ts is not None:
        return base_ts

    return None


def _lookup_coverage(
    rel_path: str,
    coverage_map: dict[str, datetime],
    basename_index: dict[str, datetime],
) -> datetime:
    """Look up coverage for a file, falling back to basename matching."""
    exact = coverage_map.get(rel_path)
    if exact is not None:
        return exact

    basename = rel_path.rsplit("/", 1)[-1] if "/" in rel_path else rel_path
    base_ts = basename_index.get(basename)
    if base_ts is not None:
        return base_ts

    return EPOCH_ZERO


def _build_basename_index(coverage_map: dict[str, datetime]) -> dict[str, datetime]:
    """Build a basename-to-timestamp index from the coverage map."""
    index: dict[str, datetime] = {}
    for path, ts in coverage_map.items():
        basename = path.rsplit("/", 1)[-1] if "/" in path else path
        existing = index.get(basename)
        if existing is None or ts > existing:
            index[basename] = ts
    return index


def coverage_weights(
    candidates: list[str],
    coverage_map: dict[str, datetime],
    project_root: Path,
    now: datetime | None = None,
) -> list[float]:
    """Compute weights based on freshness."""
    weights = []
    for candidate in candidates:
        # If it exists, assign it to a relatively recent date-time
        if candidate in coverage_map:
            weights.append(
                (now - coverage_map[candidate]).total_seconds()
            )
        # If it doesn't exist, assign it a zero weight
        else:
            weights.append(float("inf"))
    return weights
```