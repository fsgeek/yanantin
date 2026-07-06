"""The live banding aggregator: firehose defense at the provider boundary.

Source-agnostic and event-fed. Holds one live entry per (location, principal),
OR-ing access-kind bits across the band. Emits a band on quiescence (idle past
the window) or explicit flush. The ONLY thing it drops that it observed is the
intra-band create+delete lifecycle of a temp file — an exception to persistence,
not to observation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from yanantin.activity.band import StorageAccessKind, StorageActivityBand

_CREATE_DELETE = StorageAccessKind.CREATE | StorageAccessKind.DELETE


@dataclass
class _Entry:
    location: str
    os_principal: str | None
    access_kinds: int
    band_start: datetime
    band_end: datetime


class BandAggregator:
    def __init__(self, quiescence: timedelta) -> None:
        self._quiescence = quiescence
        self._entries: dict[tuple[str, str | None], _Entry] = {}

    def observe(
        self,
        location: str,
        kind: StorageAccessKind,
        at: datetime,
        os_principal: str | None = None,
    ) -> None:
        key = (location, os_principal)
        entry = self._entries.get(key)
        if entry is None:
            self._entries[key] = _Entry(
                location=location,
                os_principal=os_principal,
                access_kinds=int(kind),
                band_start=at,
                band_end=at,
            )
            return
        entry.access_kinds |= int(kind)
        if at < entry.band_start:
            entry.band_start = at
        if at > entry.band_end:
            entry.band_end = at

    def _emit(self, entry: _Entry) -> StorageActivityBand | None:
        # Elision: a whole life of exactly create+delete inside one band.
        if entry.access_kinds == int(_CREATE_DELETE):
            return None
        return StorageActivityBand(
            location=entry.location,
            access_kinds=entry.access_kinds,
            band_start=entry.band_start,
            band_end=entry.band_end,
            os_principal=entry.os_principal,
        )

    def flush_quiescent(self, now: datetime) -> list[StorageActivityBand]:
        cutoff = now - self._quiescence
        idle_keys = [k for k, e in self._entries.items() if e.band_end <= cutoff]
        out: list[StorageActivityBand] = []
        for k in idle_keys:
            band = self._emit(self._entries.pop(k))
            if band is not None:
                out.append(band)
        return out

    def flush_all(self) -> list[StorageActivityBand]:
        out: list[StorageActivityBand] = []
        for k in list(self._entries.keys()):
            band = self._emit(self._entries.pop(k))
            if band is not None:
                out.append(band)
        return out
