"""Dropbox fact recorder — stores Dropbox entries as individual facts.

Unlike DropboxRecorder (which stores a whole listing as one tensor),
this decomposes the listing into individual facts — one per entry.
Each fact carries the full DropboxEntryData as its data dict, timestamped
by the entry's modified_time (or collected_at for folders/deleted).
"""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.collector.base import FactRecorderBase
from yanantin.collector.dropbox.models import DropboxListing
from yanantin.collector.models import WranglerEnvelope


class DropboxFactRecorder(FactRecorderBase[DropboxListing]):
    """Decomposes a Dropbox listing into individual facts.

    One fact per DropboxEntryData. The fact's timestamp is the entry's
    modified_time (for files) or collected_at (for folders/deleted entries
    which lack a modification time).
    """

    def __init__(self, store: ActivityStreamStore) -> None:
        super().__init__(store)
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.fact_recorder.dropbox",
        )

    def record_facts(self, envelope: WranglerEnvelope[DropboxListing]) -> int:
        """Store one fact per Dropbox entry. Return count stored."""
        data = envelope.data
        count = 0

        for entry in data.entries:
            entry_dict = entry.model_dump(mode="json")
            content_hash = self._entry_content_hash(entry_dict)

            # Files have modified_time; folders/deleted use collected_at
            timestamp = entry.modified_time if entry.modified_time is not None else data.collected_at

            fact = FactRecord(
                provider_id=envelope.provider_id,
                timestamp=timestamp,
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
        return "Dropbox fact recorder — stores one fact per cloud file entry"
