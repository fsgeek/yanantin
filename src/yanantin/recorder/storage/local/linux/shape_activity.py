"""Wire CollectorShapeReport into the activity stream, and fit a synthetic
collector from a measured report (census-then-fit).

The collector run is an activity; this module records its shape as a FactRecord
(criterion 3) and derives synthetic parameters from a real report so the
synthetic corpus matches MEASURED reality rather than a guess (criterion 4).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.collector.storage.local.linux.models import FilesystemSnapshot
from yanantin.collector.storage.local.linux.shape_report import CollectorShapeReport
from yanantin.collector.storage.local.linux.synthetic import (
    SyntheticFilesystemCollector,
)


def record_shape(
    store: ActivityStreamStore,
    snapshot: FilesystemSnapshot,
    provider_id: UUID,
) -> CollectorShapeReport:
    """Compute the shape report for a collection run and record it as a fact
    keyed by the collector's provider_id. Returns the report.

    The collector IS an activity-stream provider reporting on its own run; the
    report rides FactRecord.data (open at the store, structured at the producer).
    """
    report = CollectorShapeReport.from_snapshot(snapshot)
    fact = FactRecord(
        provider_id=provider_id,
        timestamp=datetime.now(timezone.utc),
        data=report.to_fact_data(),
    )
    store.store_fact(fact)
    return report


def latest_shape(
    store: ActivityStreamStore, provider_id: UUID
) -> CollectorShapeReport | None:
    """Read the most recent shape report a provider recorded, or None."""
    fact = store.query_latest(provider_id)
    if fact is None:
        return None
    return CollectorShapeReport.model_validate(fact.data)


def synthetic_from_report(
    report: CollectorShapeReport,
    *,
    seed: int = 0,
) -> SyntheticFilesystemCollector:
    """census-then-fit: build a synthetic collector whose parameters are derived
    from a MEASURED real report, so its corpus approximates the real one.

    The synthetic exposes depth / files_per_dir / time_window_days /
    symlink_probability. We map the measured shape onto those:
      - max_depth → depth, MINUS 1: the synthetic nests `depth` dir levels and
        files sit one level below the deepest dir, so measured max_depth (the
        deepest FILE path) = synthetic depth + 1. Subtracting keeps a fit→
        re-measure roundtrip stable instead of deepening by one each pass.
      - mean_files_per_dir → files_per_dir (rounded, >=1)
      - oldest occupied mtime band → time_window_days (cover the temporal spread)
    Object count is then an emergent function of depth × files_per_dir; the
    tolerance check in the dual-collector proof accounts for that.

    NOTE (honest scope limit): the current synthetic collector emits size-0
    files, so file SIZE is not a matchable characteristic — it is excluded from
    the dual-collector tolerance check until the synthetic learns to generate a
    size distribution. The report still RECORDS sizes (save-it-all); they are
    simply not asserted to match.
    """
    depth = max(1, report.max_depth - 1)
    files_per_dir = max(1, round(report.mean_files_per_dir))

    # Pick a time window that covers the observed mtime spread: the widest age
    # band that actually holds entries.
    window_days = 365
    band_to_days = {
        "<=1": 1, "<=7": 7, "<=30": 30, "<=90": 90,
        "<=365": 365, "<=1095": 1095, ">1095": 1825,
    }
    occupied = [
        band_to_days[b]
        for b, n in report.mtime_age_buckets.items()
        if n > 0 and b in band_to_days
    ]
    if occupied:
        window_days = max(occupied)

    return SyntheticFilesystemCollector(
        seed=seed,
        depth=depth,
        files_per_dir=files_per_dir,
        time_window_days=window_days,
    )
