"""Filesystem event fact recorder — stores change events as individual facts."""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.collector.activity.linux.models import FsEventBatch
from yanantin.recorder.base import FactRecorderBase
from yanantin.transport.models import WranglerEnvelope


class FsEventFactRecorder(FactRecorderBase[FsEventBatch]):
    """Decomposes a filesystem event batch into individual facts."""

    def __init__(self, store: ActivityStreamStore) -> None:
        super().__init__(store)
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.fact_recorder.fs_events",
        )

    def record_facts(self, envelope: WranglerEnvelope[FsEventBatch]) -> int:
        """Store one fact per change event. Return count stored."""
        data = envelope.data
        count = 0

        for event in data.events:
            event_dict = event.model_dump(mode="json")
            content_hash = self._event_content_hash(event_dict)

            fact = FactRecord(
                provider_id=envelope.provider_id,
                timestamp=event.detected_at,
                data=event_dict,
                content_hash=content_hash,
            )
            self.store.store_fact(fact)
            count += 1

        return count

    @staticmethod
    def _event_content_hash(event_dict: dict) -> str:
        """SHA-256 of deterministic JSON, truncated to 16 hex chars."""
        serialized = json.dumps(event_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def get_recorder_id(self) -> UUID:
        return self._recorder_id

    def get_description(self) -> str:
        return "Filesystem event fact recorder — stores one fact per change event"
