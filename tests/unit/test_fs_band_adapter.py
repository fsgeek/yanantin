"""Unit tests for the mtime-scan → band aggregator adapter.

Verifies:
- event_type maps to the correct access kind
- location is a weak path: URI (no stable anchor)
- a scan batch feeds every event; principal is None (mtime-scan can't attribute)
- accumulation across two batches (scan runs) lands in one band per file
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from yanantin.activity.band import StorageAccessKind
from yanantin.activity.band_aggregator import BandAggregator
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch
from yanantin.collector.activity.linux.band_adapter import (
    event_type_to_kind,
    feed_batch,
    mint_location,
)

T0 = datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc)


def _batch(events, cur):
    return FsEventBatch(volumes=("/",), events=tuple(events), last_run=None, current_run=cur)


def test_event_type_maps_to_kind():
    assert event_type_to_kind("created") == StorageAccessKind.CREATE
    assert event_type_to_kind("modified") == StorageAccessKind.WRITE
    assert event_type_to_kind("deleted") == StorageAccessKind.DELETE


def test_location_is_weak_path_uri():
    assert mint_location("/data/foo") == "path:/data/foo"


def test_feed_batch_bands_with_no_principal():
    agg = BandAggregator(quiescence=timedelta(minutes=5))
    ev = FsChangeEvent(file_path="/data/foo", event_type="created",
                       modified_time=T0, size_bytes=10)
    feed_batch(agg, _batch([ev], cur=T0))
    bands = agg.flush_all()
    assert len(bands) == 1
    assert bands[0].location == "path:/data/foo"
    assert bands[0].os_principal is None


def test_accumulation_across_two_scan_runs():
    agg = BandAggregator(quiescence=timedelta(minutes=5))
    ev1 = FsChangeEvent(file_path="/data/foo", event_type="created",
                        modified_time=T0, size_bytes=10)
    ev2 = FsChangeEvent(file_path="/data/foo", event_type="modified",
                        modified_time=T0 + timedelta(seconds=30), size_bytes=20)
    feed_batch(agg, _batch([ev1], cur=T0))
    feed_batch(agg, _batch([ev2], cur=T0 + timedelta(seconds=30)))
    bands = agg.flush_all()
    assert len(bands) == 1
    kinds = StorageAccessKind(bands[0].access_kinds)
    assert StorageAccessKind.CREATE in kinds and StorageAccessKind.WRITE in kinds
