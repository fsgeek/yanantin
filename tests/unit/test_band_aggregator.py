"""Unit tests for the source-agnostic BandAggregator.

Verifies:
- Repeated accesses to one (location, principal) OR into one band, counts discarded
- Two principals on the same location produce two single-actor bands
- Quiescence emits only entries idle past the window; active ones stay
- create+delete within one band is elided (no band emitted)
- band_start/band_end track first/last access
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from yanantin.activity.band import StorageAccessKind
from yanantin.activity.band_aggregator import BandAggregator

T0 = datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc)
def at(sec): return T0 + timedelta(seconds=sec)
Q = timedelta(minutes=5)


def test_repeated_access_ors_into_one_band():
    agg = BandAggregator(quiescence=Q)
    agg.observe("path:/a", StorageAccessKind.READ, at(0), os_principal="1000")
    agg.observe("path:/a", StorageAccessKind.READ, at(1), os_principal="1000")
    agg.observe("path:/a", StorageAccessKind.WRITE, at(2), os_principal="1000")
    bands = agg.flush_all()
    assert len(bands) == 1
    kinds = StorageAccessKind(bands[0].access_kinds)
    assert StorageAccessKind.READ in kinds and StorageAccessKind.WRITE in kinds
    assert bands[0].band_start == at(0)
    assert bands[0].band_end == at(2)


def test_two_principals_two_bands():
    agg = BandAggregator(quiescence=Q)
    agg.observe("path:/a", StorageAccessKind.WRITE, at(0), os_principal="1000")
    agg.observe("path:/a", StorageAccessKind.WRITE, at(1), os_principal="1001")
    bands = agg.flush_all()
    assert len(bands) == 2
    principals = {b.os_principal for b in bands}
    assert principals == {"1000", "1001"}


def test_quiescence_emits_only_idle_entries():
    agg = BandAggregator(quiescence=Q)
    agg.observe("path:/idle", StorageAccessKind.WRITE, at(0), os_principal="1000")
    agg.observe("path:/active", StorageAccessKind.WRITE, at(60 * 10), os_principal="1000")
    # now is 5m1s after the idle entry's last touch, but the active entry is fresh
    emitted = agg.flush_quiescent(now=at(60 * 10 + 1))
    assert len(emitted) == 1
    assert emitted[0].location == "path:/idle"


def test_create_delete_in_band_is_elided():
    agg = BandAggregator(quiescence=Q)
    agg.observe("path:/tmp/x", StorageAccessKind.CREATE, at(0), os_principal="1000")
    agg.observe("path:/tmp/x", StorageAccessKind.DELETE, at(1), os_principal="1000")
    bands = agg.flush_all()
    assert bands == []


def test_create_write_delete_in_band_is_NOT_elided():
    # elision is create+delete ONLY; if it was also written, it may matter
    agg = BandAggregator(quiescence=Q)
    agg.observe("path:/tmp/x", StorageAccessKind.CREATE, at(0), os_principal="1000")
    agg.observe("path:/tmp/x", StorageAccessKind.WRITE, at(1), os_principal="1000")
    agg.observe("path:/tmp/x", StorageAccessKind.DELETE, at(2), os_principal="1000")
    bands = agg.flush_all()
    assert len(bands) == 1
