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


def _lookup_coverage_or_none(
    rel_path: str,
    coverage_map: dict[str, datetime],
    basename_index: dict[str, datetime],
) -> datetime | None:
    """Like _lookup_coverage, but returns None instead of EPOCH_ZERO on miss."""
    # Exact match first
    exact = coverage_map.get(rel_path)
    if exact is not None:
        return exact

    # Fallback: basename
    basename = rel_path.rsplit("/", 1)[-1] if "/" in rel_path else rel_path
    return basename_index.get(basename)


def _lookup_coverage(
    rel_path: str,
    coverage_map: dict[str, datetime],
    basename_index: dict[str, datetime],
) -> datetime:
    """Look up coverage for a file, falling back to basename matching.

    Scout reports often reference files by short names like `evolve.py`
    or `predecessors.md`, while candidate paths are full project-relative
    paths like `src/yanantin/apacheta/operators/evolve.py`. Without
    basename fallback, the coverage map never matches and every file
    appears as "never reviewed" (epoch zero).

    Lookup order:
    1. Exact match on full relative path
    2. Basename match (last component of the path)

    Returns the most recent review timestamp found, or EPOCH_ZERO.
    """
    # Exact match first
    exact = coverage_map.get(rel_path)
    if exact is not None:
        return exact

    # Fallback: basename of the candidate against the coverage map
    basename = rel_path.rsplit("/", 1)[-1] if "/" in rel_path else rel_path
    base_ts = basename_index.get(basename)
    if base_ts is not None:
        return base_ts

    return EPOCH_ZERO


def _build_basename_index(coverage_map: dict[str, datetime]) -> dict[str, datetime]:
    """Build a basename-to-timestamp index from the coverage map.

    When multiple coverage entries share a basename, keep the most
    recent timestamp (same "latest wins" semantics as the main map).
    """
    index: dict[str, datetime] = {}
    for path, ts in coverage_map.items():
        basename = path.rsplit("/", 1)[-1] if "/" in path else path
        existing = index.get(basename)
        if existing is None or ts > existing:
            index[basename] = ts
    return index


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

    basename_index = _build_basename_index(coverage_map)

    weights = []
    for path in candidates:
        try:
            rel = str(path.relative_to(project_root))
        except ValueError:
            rel = str(path)

        last_reviewed = _lookup_coverage(rel, coverage_map, basename_index)
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

    basename_index = _build_basename_index(coverage_map)

    all_files: dict[str, datetime | None] = {}
    for ext in source_extensions:
        for path in project_root.rglob(f"*{ext}"):
            if any(d in path.parts for d in skip_dirs):
                continue
            if not path.is_file():
                continue
            rel = str(path.relative_to(project_root))
            # Try exact match, then basename fallback
            ts = _lookup_coverage_or_none(rel, coverage_map, basename_index)
            all_files[rel] = ts

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


# ── Tensor coverage ──────────────────────────────────────────────────

# Tensor references in report text: T0, T12, T15_pichay, etc.
_TENSOR_REF_PATTERN = re.compile(r"\bT(\d+)(?:_\w+)?\b")

# Target field in scour report header
_TARGET_PATTERN = re.compile(r"Target:\s*(.+)")


def _extract_tensor_refs(text: str) -> set[str]:
    """Extract tensor number references from report text.

    Returns set of tensor numbers as strings: {"0", "12", "32"}.
    """
    return {m.group(1) for m in _TENSOR_REF_PATTERN.finditer(text)}


def scan_tensor_coverage(
    cairn_dir: Path,
    pattern: str = "scour_*.md",
) -> dict[str, datetime]:
    """Scan scour reports and build a tensor coverage map.

    Returns {tensor_number: last_scoured_at} for all tensors
    referenced in scour reports. Tensor numbers are strings
    ("0", "12", "32") matching the T-prefix naming convention.

    Only counts references to tensors that actually exist in the
    cairn (have T*_*.md files). This prevents phantom matches —
    line numbers, counts, and other numeric text in report prose
    that happen to match the T-number pattern.

    A tensor is considered "covered" if a scour report either:
    - Targeted it directly (Target: T32*)
    - Referenced it in body text (mentions T32)
    """
    if not cairn_dir.is_dir():
        logger.warning("Cairn directory does not exist: %s", cairn_dir)
        return {}

    # Ground truth: only track tensors that actually exist
    known_tensors = set(list_tensors(cairn_dir))

    coverage: dict[str, datetime] = {}
    report_count = 0

    for report_path in cairn_dir.glob(pattern):
        try:
            text = report_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        report_count += 1
        timestamp = _parse_report_timestamp(text)
        tensor_refs = _extract_tensor_refs(text) & known_tensors

        for tensor_num in tensor_refs:
            existing = coverage.get(tensor_num)
            if existing is None or timestamp > existing:
                coverage[tensor_num] = timestamp

    logger.info(
        "Tensor coverage scan: %d reports, %d tensors tracked",
        report_count, len(coverage),
    )
    return coverage


def list_tensors(cairn_dir: Path) -> list[str]:
    """List all tensor numbers present in the cairn.

    Scans for T*_*.md files and extracts tensor numbers.
    Returns sorted list of tensor number strings.
    """
    tensor_nums: set[str] = set()
    for path in cairn_dir.glob("T*_*.md"):
        m = re.match(r"T(\d+)", path.name)
        if m:
            tensor_nums.add(m.group(1))
    return sorted(tensor_nums, key=int)


def stalest_tensors(
    cairn_dir: Path,
    n: int = 10,
) -> list[tuple[str, datetime | None]]:
    """Return the N tensors with oldest (or missing) scour coverage.

    Never-scoured tensors come first, then by last-scoured ascending.
    Returns (tensor_number, last_scoured_or_None) tuples.
    """
    all_tensors = list_tensors(cairn_dir)
    tensor_coverage = scan_tensor_coverage(cairn_dir)

    never_scoured = [
        (t, None) for t in all_tensors
        if t not in tensor_coverage
    ]
    scoured = [
        (t, tensor_coverage[t]) for t in all_tensors
        if t in tensor_coverage
    ]
    scoured.sort(key=lambda x: x[1])  # type: ignore[arg-type]

    return (never_scoured + scoured)[:n]


def dynamic_scour_targets(
    cairn_dir: Path,
    max_tensor_targets: int = 6,
) -> list[tuple[str, str]]:
    """Generate scour targets weighted by tensor coverage freshness.

    Returns a list of (target, scope) pairs for the pulse hook,
    replacing hardcoded SCOUR_TARGETS. Includes:
    - Stalest tensors as specific targets (tensor scope)
    - One "T*" wildcard for broad coverage
    - Synthesis targets (fixed)
    - Introspection targets (fixed, reduced)

    The tensor targets auto-update as new tensors are written.
    """
    targets: list[tuple[str, str]] = []

    # Dynamic tensor targets: stalest first
    stalest = stalest_tensors(cairn_dir, n=max_tensor_targets)
    for tensor_num, _ in stalest:
        targets.append((f"T{tensor_num}*", "tensor"))

    # Broad wildcard — catches new tensors between updates
    targets.append(("T*", "tensor"))

    # Synthesis — fixed, these find cross-report patterns
    targets.append(("scout_*", "synthesis"))
    targets.append(("scout_*", "synthesis"))  # doubled weight

    # Introspection — fixed, reduced set
    targets.append(("src/yanantin/apacheta", "introspection"))
    targets.append(("src/yanantin/chasqui", "introspection"))
    targets.append(("src/yanantin/activity", "introspection"))

    # Sibling projects — external scope
    # These are part of the same research program; cross-pollination is valuable
    siblings = Path(__file__).resolve().parents[4]  # src/yanantin/chasqui → projects/
    for sibling_name in ("tinkuy", "hamutay"):
        sibling_path = siblings / sibling_name
        if sibling_path.is_dir():
            targets.append((str(sibling_path), "external"))

    return targets
