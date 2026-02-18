"""In-memory backend for the activity stream store.

Dict-based storage with bisect for temporal queries and threading.RLock
for thread safety. Deep-copy on read/write — same pattern as Apacheta's
InMemoryBackend.
"""

from __future__ import annotations

import bisect
import threading
from datetime import datetime, timedelta
from uuid import UUID

from yanantin.activity.models import FactRecord, MemoryAnchor
from yanantin.activity.store import ActivityStreamStore
from yanantin.apacheta.interface.errors import ImmutabilityError, NotFoundError


class InMemoryActivityStreamStore(ActivityStreamStore):
    """In-memory implementation of ActivityStreamStore.

    Thread-safe via RLock. Enforces immutability: duplicate UUID/handle
    on store raises ImmutabilityError. Uses bisect for O(log n) temporal
    queries on sorted lists.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._facts: dict[UUID, FactRecord] = {}
        # Per-provider sorted lists: list of (timestamp, fact_id) for bisect
        self._facts_by_provider: dict[UUID, list[tuple[datetime, UUID]]] = {}
        self._anchors: dict[UUID, MemoryAnchor] = {}
        # Sorted list: (timestamp, handle) for temporal anchor queries
        self._anchors_by_time: list[tuple[datetime, UUID]] = []

    @staticmethod
    def _deep_copy(record):
        """Deep-copy a record via serialize/deserialize roundtrip."""
        return type(record).model_validate(record.model_dump(mode="python"))

    # -- Fact operations -----------------------------------------------

    def store_fact(self, fact: FactRecord) -> None:
        with self._lock:
            if fact.id in self._facts:
                raise ImmutabilityError(
                    f"Fact {fact.id} already exists. "
                    "Facts are immutable — append, don't overwrite."
                )
            self._facts[fact.id] = self._deep_copy(fact)

            # Maintain sorted index for temporal queries
            if fact.provider_id not in self._facts_by_provider:
                self._facts_by_provider[fact.provider_id] = []
            index_list = self._facts_by_provider[fact.provider_id]
            bisect.insort(index_list, (fact.timestamp, fact.id))

    def get_fact(self, fact_id: UUID) -> FactRecord:
        with self._lock:
            if fact_id not in self._facts:
                raise NotFoundError(f"Fact {fact_id} not found.")
            return self._deep_copy(self._facts[fact_id])

    def query_latest(
        self,
        provider_id: UUID,
        before: datetime | None = None,
    ) -> FactRecord | None:
        with self._lock:
            index_list = self._facts_by_provider.get(provider_id)
            if not index_list:
                return None

            if before is None:
                # Return the most recent fact
                _, fact_id = index_list[-1]
                return self._deep_copy(self._facts[fact_id])

            # Binary search for the latest fact at or before `before`.
            # Use before + 1us so bisect_left lands after all entries
            # with timestamp == before (tuple prefix comparison).
            pos = bisect.bisect_left(index_list, (before + timedelta(microseconds=1),))
            if pos == 0:
                return None
            _, fact_id = index_list[pos - 1]
            return self._deep_copy(self._facts[fact_id])

    def query_range(
        self,
        provider_id: UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[FactRecord]:
        with self._lock:
            index_list = self._facts_by_provider.get(provider_id)
            if not index_list:
                return []

            # Determine range boundaries
            if start is not None:
                lo = bisect.bisect_left(index_list, (start,))
            else:
                lo = 0

            if end is not None:
                # Use end + 1us so bisect_left lands after all entries
                # with timestamp == end (tuple prefix comparison).
                hi = bisect.bisect_left(index_list, (end + timedelta(microseconds=1),))
            else:
                hi = len(index_list)

            return [
                self._deep_copy(self._facts[fact_id])
                for _, fact_id in index_list[lo:hi]
            ]

    # -- Anchor operations ---------------------------------------------

    def store_anchor(self, anchor: MemoryAnchor) -> None:
        with self._lock:
            if anchor.handle in self._anchors:
                raise ImmutabilityError(
                    f"Anchor {anchor.handle} already exists. "
                    "Anchors are immutable — advance, don't overwrite."
                )
            self._anchors[anchor.handle] = self._deep_copy(anchor)
            bisect.insort(self._anchors_by_time, (anchor.timestamp, anchor.handle))

    def get_anchor(self, handle: UUID) -> MemoryAnchor:
        with self._lock:
            if handle not in self._anchors:
                raise NotFoundError(f"Anchor {handle} not found.")
            return self._deep_copy(self._anchors[handle])

    def get_latest_anchor(self) -> MemoryAnchor | None:
        with self._lock:
            if not self._anchors_by_time:
                return None
            _, handle = self._anchors_by_time[-1]
            return self._deep_copy(self._anchors[handle])

    # -- Discovery -----------------------------------------------------

    def list_providers(self) -> list[UUID]:
        with self._lock:
            return list(self._facts_by_provider.keys())

    def count_facts(self, provider_id: UUID | None = None) -> int:
        with self._lock:
            if provider_id is not None:
                index_list = self._facts_by_provider.get(provider_id)
                return len(index_list) if index_list else 0
            return len(self._facts)
