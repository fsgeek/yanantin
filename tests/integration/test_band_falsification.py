"""Falsification: does the band aggregator tame the real mtime-scan firehose
without lying about identity strength? Spec 2026-07-05 §8.

These are the load-bearing claims of the whole pour, pinned as permanent
regression guards. An ephemeral adversarial workflow (2026-07-06) confirmed
the design survives all three against the built code; this test keeps them
falsifiable on every future change.

Targets:
1. Firehose tamed: repeated access to one file collapses to one band —
   facts-out far less than events-in.
2. Temp-file elision: a file created and deleted within one band emits no fact.
3. Weak-anchor honesty: mtime-scan bands carry path: URIs and os_principal=None;
   a rename (delete old + create new) is TWO bands on TWO paths, never coalesced,
   and RENAME is never inferred.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.activity.band import StorageAccessKind
from yanantin.activity.band_aggregator import BandAggregator
from yanantin.collector.activity.linux.band_adapter import feed_batch
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch
from yanantin.recorder.activity.linux.band_fact_recorder import BandFactRecorder

T0 = datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc)
PID = uuid4()


def _batch(events):
    return FsEventBatch(
        volumes=("/",), events=tuple(events), last_run=None, current_run=T0
    )


def test_firehose_tamed_facts_out_less_than_events_in():
    # 50 modifies to one file → 1 band, not 50 facts.
    events = [
        FsChangeEvent(
            file_path="/repo/hot",
            event_type="modified",
            modified_time=T0 + timedelta(seconds=i),
            size_bytes=i,
        )
        for i in range(50)
    ]
    agg = BandAggregator(quiescence=timedelta(minutes=5))
    feed_batch(agg, _batch(events))
    bands = agg.flush_all()
    store = InMemoryActivityStreamStore()
    n = BandFactRecorder(store).record_bands(PID, bands)
    assert len(events) == 50
    assert n == 1, "firehose not tamed: expected 1 band from 50 events"


def test_temp_file_elided():
    events = [
        FsChangeEvent(
            file_path="/repo/tmp/x",
            event_type="created",
            modified_time=T0,
            size_bytes=0,
        ),
        FsChangeEvent(
            file_path="/repo/tmp/x",
            event_type="deleted",
            modified_time=T0 + timedelta(seconds=1),
            size_bytes=0,
        ),
    ]
    agg = BandAggregator(quiescence=timedelta(minutes=5))
    feed_batch(agg, _batch(events))
    assert agg.flush_all() == [], "temp file (create+delete in band) not elided"


def test_weak_anchor_honesty_no_rename_inference():
    # A rename looks like delete(old) + create(new). The witness must record
    # TWO bands on TWO path: locations, never infer a single rename.
    events = [
        FsChangeEvent(
            file_path="/repo/old",
            event_type="deleted",
            modified_time=T0,
            size_bytes=100,
        ),
        FsChangeEvent(
            file_path="/repo/new",
            event_type="created",
            modified_time=T0 + timedelta(seconds=1),
            size_bytes=100,
        ),
    ]
    agg = BandAggregator(quiescence=timedelta(minutes=5))
    feed_batch(agg, _batch(events))
    bands = agg.flush_all()
    locations = sorted(b.location for b in bands)
    assert locations == ["path:/repo/new", "path:/repo/old"]
    assert all(b.os_principal is None for b in bands)
    assert all(
        StorageAccessKind.RENAME not in StorageAccessKind(b.access_kinds)
        for b in bands
    )
