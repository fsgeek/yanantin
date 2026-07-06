"""Records emitted StorageActivityBands as facts in the activity stream.

Deliberately NOT a FactRecorderBase subclass: that base is stateless
one-fact-per-event batch (the firehose this supersedes). The banding stage
emits already-reduced bands; this recorder just persists them, keyed by the
band's deterministic identity so re-recording is idempotent.
"""
from __future__ import annotations

import hashlib
import json
from uuid import UUID

from yanantin.activity.band import StorageActivityBand
from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.apacheta.interface.errors import ImmutabilityError


class BandFactRecorder:
    def __init__(self, store: ActivityStreamStore) -> None:
        self._store = store

    def record_bands(
        self, provider_id: UUID, bands: list[StorageActivityBand]
    ) -> int:
        count = 0
        for band in bands:
            data = band.model_dump(mode="json")
            fact = FactRecord(
                id=band.band_id(),
                provider_id=provider_id,
                timestamp=band.band_end,
                data=data,
                content_hash=self._content_hash(data),
            )
            try:
                self._store.store_fact(fact)
            except ImmutabilityError:
                # Deterministic band_id collides across overlapping scan
                # windows by design — the band is already persisted. Skip.
                continue
            count += 1
        return count

    @staticmethod
    def _content_hash(data: dict) -> str:
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
