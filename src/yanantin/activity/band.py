"""The banded storage-activity witness payload.

A band is "this file had these kinds of things done to it during this time
band" — the episodic unit a memory owner can recall. It is an OPEN witness
(extra="allow"): source-specific evidence rides along and is never required.
It is serialized into FactRecord.data; the store does not understand it.
"""
from __future__ import annotations

from datetime import datetime
from enum import IntFlag
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict


class StorageAccessKind(IntFlag):
    CREATE = 1 << 0
    READ = 1 << 1
    WRITE = 1 << 2
    RENAME = 1 << 3
    DELETE = 1 << 4


class StorageActivityBand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow", validate_default=True)

    location: str
    access_kinds: int
    band_start: datetime
    band_end: datetime
    granularity: str = "band"
    compaction_level: int = 0

    source_sequence: str | None = None
    os_principal: str | None = None
    process_id: int | None = None
    process_name: str | None = None

    def band_id(self) -> UUID:
        # access_kinds is deliberately NOT in the key: one aggregator entry
        # OR-s kinds in place and emits ONCE per (location, principal, window),
        # so no two DISTINCT bands share these six fields in the current design.
        # HAZARD if that invariant is ever broken (e.g. a second producer emits
        # a richer band for an already-flushed window): two bands differing only
        # in access_kinds collide here, and BandFactRecorder's ImmutabilityError
        # catch would SILENTLY DROP the second. Falsification-confirmed 2026-07-06.
        key = "|".join(
            str(x)
            for x in (
                self.location,
                self.os_principal,
                self.band_start.isoformat(),
                self.band_end.isoformat(),
                self.granularity,
                self.compaction_level,
            )
        )
        return uuid5(NAMESPACE_URL, key)
