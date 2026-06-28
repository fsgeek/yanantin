"""Cloud fact recorder — the ACTIVITY leg of the fan-out.

One fact per changed cloud entry into the activity stream (mirror of
DropboxFactRecorder). The SAME delta that feeds the storage leg feeds this leg —
that simultaneity IS the fan-out: one source emission, two destinations, an
activity-vs-storage distinction that lives in the RECORDER, not the source.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.collector.storage.cloud.synthetic.models import CloudEntry


class CloudFactRecorder:
    """Stores one activity fact per changed cloud entry."""

    def __init__(self, store: ActivityStreamStore) -> None:
        self._store = store
        self._recorder_id = uuid5(NAMESPACE_DNS, "yanantin.fact_recorder.cloud.synthetic")

    def record_change(self, entry: CloudEntry, *, provider_id: UUID) -> UUID:
        """Store a single change as a fact. Returns the fact's content hash id."""
        entry_dict = entry.model_dump(mode="json")
        content_hash = self._entry_content_hash(entry_dict)
        # FactRecord.timestamp is required+non-null; CloudEntry.modified is
        # optional (the real twin may omit it). Fall back to observation time
        # rather than crash — mirrors DropboxFactRecorder's collected_at fallback.
        timestamp = entry.modified or datetime.now(timezone.utc)
        fact = FactRecord(
            provider_id=provider_id,
            timestamp=timestamp,
            data=entry_dict,
            content_hash=content_hash,
        )
        self._store.store_fact(fact)
        return fact.id

    @staticmethod
    def _entry_content_hash(entry_dict: dict) -> str:
        serialized = json.dumps(entry_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def get_recorder_id(self) -> UUID:
        return self._recorder_id

    def get_description(self) -> str:
        return "Synthetic cloud fact recorder — one fact per changed cloud entry"
