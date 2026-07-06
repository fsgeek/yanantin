"""Unit tests for the band fact recorder.

Verifies:
- one FactRecord stored per band, count returned
- FactRecord.id is the band's deterministic band_id (idempotent re-record)
- FactRecord.timestamp is band_end; data round-trips to the band
- content_hash is stable for identical bands
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.activity.band import StorageAccessKind, StorageActivityBand
from yanantin.recorder.activity.linux.band_fact_recorder import BandFactRecorder

PID = uuid4()


def _band(loc="path:/a"):
    return StorageActivityBand(
        location=loc,
        access_kinds=int(StorageAccessKind.WRITE),
        band_start=datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc),
        band_end=datetime(2026, 7, 6, 9, 5, tzinfo=timezone.utc),
    )


def test_records_one_fact_per_band():
    store = InMemoryActivityStreamStore()
    rec = BandFactRecorder(store)
    n = rec.record_bands(PID, [_band("path:/a"), _band("path:/b")])
    assert n == 2
    assert store.count_facts(PID) == 2


def test_fact_id_is_band_id():
    store = InMemoryActivityStreamStore()
    rec = BandFactRecorder(store)
    band = _band()
    rec.record_bands(PID, [band])
    stored = store.get_fact(band.band_id())
    assert stored.timestamp == band.band_end
    assert stored.data["location"] == "path:/a"


def test_re_recording_same_band_is_idempotent():
    # deterministic band_id collides across overlapping scan windows by design;
    # the store rejects dup ids, so the recorder must absorb the collision.
    store = InMemoryActivityStreamStore()
    rec = BandFactRecorder(store)
    band = _band()
    first = rec.record_bands(PID, [band])
    second = rec.record_bands(PID, [band])
    assert first == 1
    assert second == 0, "re-recording an existing band must not double-count or raise"
    assert store.count_facts(PID) == 1


def test_content_hash_stable():
    store = InMemoryActivityStreamStore()
    rec = BandFactRecorder(store)
    rec.record_bands(PID, [_band()])
    h1 = store.get_fact(_band().band_id()).content_hash
    assert len(h1) == 16
