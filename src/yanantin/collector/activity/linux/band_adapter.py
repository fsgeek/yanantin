"""Adapter: mtime-scan FsChangeEvent stream → BandAggregator.

mtime-scan is a weak-anchor, quiescence-only source: no stable object id
(location is a path: URI), no principal attribution (os_principal=None), no
causal close (banding driven by the caller's flush cadence). It converges to
the same StorageActivityBand shape as any richer source.
"""
from __future__ import annotations

from yanantin.activity.band import StorageAccessKind
from yanantin.activity.band_aggregator import BandAggregator
from yanantin.collector.activity.linux.models import FsEventBatch

_KIND_BY_EVENT = {
    "created": StorageAccessKind.CREATE,
    "modified": StorageAccessKind.WRITE,
    "deleted": StorageAccessKind.DELETE,
}


def event_type_to_kind(event_type: str) -> StorageAccessKind:
    return _KIND_BY_EVENT[event_type]


def mint_location(file_path: str) -> str:
    return f"path:{file_path}"


def feed_batch(agg: BandAggregator, batch: FsEventBatch) -> None:
    for event in batch.events:
        agg.observe(
            location=mint_location(event.file_path),
            kind=event_type_to_kind(event.event_type),
            at=event.modified_time,
            os_principal=None,
        )
