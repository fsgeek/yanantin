"""Unit tests for the StorageActivityBand witness payload.

Verifies:
- StorageAccessKind bits OR together as a mask
- Band is frozen and open (extra="allow")
- band_id is deterministic uuid5 over identity fields
- band_id differs when principal differs (single-actor identity)
"""
from __future__ import annotations

from datetime import datetime, timezone

from yanantin.activity.band import StorageAccessKind, StorageActivityBand


def _band(**kw):
    base = dict(
        location="path:/data/foo",
        access_kinds=int(StorageAccessKind.CREATE | StorageAccessKind.WRITE),
        band_start=datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc),
        band_end=datetime(2026, 7, 6, 9, 5, tzinfo=timezone.utc),
    )
    base.update(kw)
    return StorageActivityBand(**base)


def test_access_kind_bits_or_together():
    mask = StorageAccessKind.CREATE | StorageAccessKind.DELETE
    assert int(mask) == 1 + 16
    assert StorageAccessKind.CREATE in StorageAccessKind(int(mask))


def test_band_is_frozen():
    band = _band()
    try:
        band.location = "path:/other"
        raised = False
    except Exception:
        raised = True
    assert raised, "band must be frozen"


def test_band_allows_extra_fields():
    band = _band(source_specific_evidence="ntfs-usn-42")
    assert band.model_dump()["source_specific_evidence"] == "ntfs-usn-42"


def test_band_id_deterministic():
    assert _band().band_id() == _band().band_id()


def test_band_id_differs_by_principal():
    a = _band(os_principal="1000")
    b = _band(os_principal="1001")
    assert a.band_id() != b.band_id()
