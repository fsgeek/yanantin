"""CollectorShapeReport — the shape of what a collector collected, as activity data.

A storage collector RUNNING is an activity, and the SHAPE of what it collected
IS the activity event. This report is the payload: count + temporal spread +
tree shape + extension/size distributions. It is structured at the PRODUCER (so
real-vs-synthetic comparison is a model diff, not an eyeball) but rides
FactRecord.data OPEN at the activity store (the store stays schema-agnostic).

Two uses, one artifact:
  1. census-then-fit: read the REAL run's report, parameterize the synthetic
     collector from its measured values (no guessing).
  2. dual-collector-honest proof: diff the real report against the synthetic
     report — a query over collection history, not a one-time glance.

See the memory `storage-collectors-are-activity-stream-providers-...`.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from yanantin.collector.storage.local.linux.models import FilesystemSnapshot

# The mtime histogram is bucketed by age (days before the report time). These
# bounds give coarse, comparable bands without committing to a query shape.
_AGE_BUCKET_DAYS: tuple[int, ...] = (1, 7, 30, 90, 365, 1095)


def _quantile(sorted_vals: list[int], q: float) -> int:
    """Nearest-rank quantile of a pre-sorted list. Empty → 0."""
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, int(q * len(sorted_vals)))
    return sorted_vals[idx]


class CollectorShapeReport(BaseModel):
    """Measured shape of one collection run — the activity payload.

    All fields are computed from a FilesystemSnapshot via ``from_snapshot``.
    Open lane (extra="allow") so a richer collector can add fields without a
    schema migration — save-it-all at the report level.
    """

    model_config = ConfigDict(extra="allow")

    object_count: int  # total entries (files + dirs)
    file_count: int
    dir_count: int

    # Temporal axis — the search-space reducer. Histogram of mtime AGE in days,
    # keyed by upper-bound bucket ("<=7" etc.) → count. The shares (count/total)
    # are what real-vs-synthetic comparison checks.
    mtime_age_buckets: dict[str, int] = Field(default_factory=dict)

    # Tree shape.
    max_depth: int = 0
    mean_files_per_dir: float = 0.0

    # Name/extension distribution: extension (lowercased, incl. dot; "" if none)
    # → count.
    extension_counts: dict[str, int] = Field(default_factory=dict)

    # Size distribution (bytes), heavy-tailed → report quantiles not mean.
    size_p50: int = 0
    size_p90: int = 0
    size_p99: int = 0

    reported_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @classmethod
    def from_snapshot(cls, snapshot: FilesystemSnapshot) -> CollectorShapeReport:
        """Compute the shape report from a collected snapshot."""
        now = datetime.now(timezone.utc)
        entries = snapshot.entries

        files = [e for e in entries if not e.is_directory]
        dirs = [e for e in entries if e.is_directory]

        # mtime age histogram
        age_buckets: Counter[str] = Counter()
        for e in entries:
            age_days = (now - e.timestamps.modified).total_seconds() / 86400.0
            label = f">{_AGE_BUCKET_DAYS[-1]}"
            for bound in _AGE_BUCKET_DAYS:
                if age_days <= bound:
                    label = f"<={bound}"
                    break
            age_buckets[label] += 1

        # tree depth: deepest path component count relative to root
        root_depth = snapshot.root_path.rstrip("/").count("/")
        max_depth = 0
        for e in entries:
            depth = e.path.rstrip("/").count("/") - root_depth
            max_depth = max(max_depth, depth)

        mean_fpd = (len(files) / len(dirs)) if dirs else 0.0

        # extension distribution (files only)
        ext_counts: Counter[str] = Counter()
        for e in files:
            name = e.name
            dot = name.rfind(".")
            ext = name[dot:].lower() if dot > 0 else ""
            ext_counts[ext] += 1

        # size quantiles (files only — dirs are nominal 4096)
        sizes = sorted(e.size for e in files)

        return cls(
            object_count=len(entries),
            file_count=len(files),
            dir_count=len(dirs),
            mtime_age_buckets=dict(age_buckets),
            max_depth=max_depth,
            mean_files_per_dir=round(mean_fpd, 3),
            extension_counts=dict(ext_counts),
            size_p50=_quantile(sizes, 0.50),
            size_p90=_quantile(sizes, 0.90),
            size_p99=_quantile(sizes, 0.99),
        )

    def to_fact_data(self) -> dict:
        """Render to the open dict that rides FactRecord.data (json mode so
        timestamps are storage-ready). Structured here, open at the store."""
        return self.model_dump(mode="json")
