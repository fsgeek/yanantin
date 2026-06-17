"""OpenRouter fact recorder — stores each API call as a fact.

Each OpenRouterActivityRow becomes one FactRecord in the activity
stream. The generation_id serves as a natural dedup key — if the
same CSV is ingested twice, content hashes will match and downstream
queries can detect duplicates.

The fact's data dict preserves every field from the CSV row. The
fact's timestamp is the row's created_at. The provider_id ties back
to the collector (and thus to the source CSV file).
"""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.collector.semantic.openrouter.models import OpenRouterActivity
from yanantin.recorder.base import FactRecorderBase
from yanantin.transport.models import WranglerEnvelope


class OpenRouterFactRecorder(FactRecorderBase[OpenRouterActivity]):
    """Decomposes an OpenRouter activity snapshot into individual facts.

    One fact per API call. The fact's timestamp is the call's created_at.
    The content_hash is derived from the generation_id (the natural key).
    """

    def __init__(self, store: ActivityStreamStore) -> None:
        super().__init__(store)
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.fact_recorder.openrouter_activity",
        )

    def record_facts(self, envelope: WranglerEnvelope[OpenRouterActivity]) -> int:
        """Store one fact per API call row. Return count stored."""
        data = envelope.data
        count = 0

        for row in data.rows:
            row_dict = row.model_dump(mode="json")
            content_hash = self._row_content_hash(row.generation_id)

            fact = FactRecord(
                provider_id=envelope.provider_id,
                timestamp=row.created_at,
                data=row_dict,
                content_hash=content_hash,
            )
            self.store.store_fact(fact)
            count += 1

        return count

    @staticmethod
    def _row_content_hash(generation_id: str) -> str:
        """Hash the generation_id — the natural dedup key.

        Using generation_id rather than the full row dict means the
        same API call always produces the same hash, regardless of
        any future CSV format changes in non-essential columns.
        """
        return hashlib.sha256(generation_id.encode()).hexdigest()[:16]

    def get_recorder_id(self) -> UUID:
        return self._recorder_id

    def get_description(self) -> str:
        return "OpenRouter fact recorder — stores one fact per API call"
