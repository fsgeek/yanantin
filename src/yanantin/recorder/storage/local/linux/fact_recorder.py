"""Filesystem fact recorder — stores directory walk results as facts.

Unlike FilesystemRecorder (which stores a whole snapshot as one tensor),
this decomposes the snapshot into individual facts — one per file entry.
Each fact carries the full FileEntryData as its data dict, timestamped
by the entry's modified time.
"""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.collector.storage.local.linux.models import FilesystemSnapshot
from yanantin.recorder.base import FactRecorderBase
from yanantin.transport.models import WranglerEnvelope


class FilesystemFactRecorder(FactRecorderBase[FilesystemSnapshot]):
    """Decomposes a filesystem snapshot into individual facts.

    One fact per FileEntryData entry. The fact's timestamp is the
    entry's modified time. The fact's data is the full entry as a dict.
    """

    def __init__(self, store: ActivityStreamStore) -> None:
        super().__init__(store)
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.fact_recorder.filesystem",
        )

    def record_facts(self, envelope: WranglerEnvelope[FilesystemSnapshot]) -> int:
        """Store one fact per file entry. Return count stored."""
        data = envelope.data
        count = 0

        for entry in data.entries:
            entry_dict = entry.model_dump(mode="json")
            content_hash = self._entry_content_hash(entry_dict)

            fact = FactRecord(
                provider_id=envelope.provider_id,
                timestamp=entry.timestamps.modified,
                data=entry_dict,
                content_hash=content_hash,
            )
            self.store.store_fact(fact)
            count += 1

        return count

    @staticmethod
    def _entry_content_hash(entry_dict: dict) -> str:
        """SHA-256 of deterministic JSON, truncated to 16 hex chars."""
        serialized = json.dumps(entry_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def get_recorder_id(self) -> UUID:
        return self._recorder_id

    def get_description(self) -> str:
        return "Filesystem fact recorder — stores one fact per file entry"
