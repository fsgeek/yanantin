"""Abstract interface for the activity stream store.

Two kinds of records: facts (from providers) and anchors (from the
anchor service). Both append-only, both immutable once stored.

Reuses ImmutabilityError and NotFoundError from apacheta.interface.errors.
Same contract: append-only, no update, no delete.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from yanantin.activity.models import FactRecord, MemoryAnchor


class ActivityStreamStore(ABC):
    """Temporal store for facts and memory anchors.

    Two kinds of records: facts (from providers) and anchors (from the
    anchor service). Both append-only, both immutable once stored.
    """

    # -- Fact operations -----------------------------------------------

    @abstractmethod
    def store_fact(self, fact: FactRecord) -> None:
        """Store a fact. Raises ImmutabilityError on duplicate UUID."""
        ...

    @abstractmethod
    def get_fact(self, fact_id: UUID) -> FactRecord:
        """Retrieve a fact by ID. Raises NotFoundError if missing."""
        ...

    @abstractmethod
    def query_latest(
        self,
        provider_id: UUID,
        before: datetime | None = None,
    ) -> FactRecord | None:
        """Latest fact from provider at or before timestamp.

        Returns None if no facts match.
        """
        ...

    @abstractmethod
    def query_range(
        self,
        provider_id: UUID,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[FactRecord]:
        """All facts from provider in [start, end].

        Sorted by timestamp ascending.
        """
        ...

    # -- Anchor operations ---------------------------------------------

    @abstractmethod
    def store_anchor(self, anchor: MemoryAnchor) -> None:
        """Store an anchor. Raises ImmutabilityError on duplicate handle."""
        ...

    @abstractmethod
    def get_anchor(self, handle: UUID) -> MemoryAnchor:
        """Retrieve an anchor by handle. Raises NotFoundError if missing."""
        ...

    @abstractmethod
    def get_latest_anchor(self) -> MemoryAnchor | None:
        """Most recent anchor by timestamp. None if none stored."""
        ...

    # -- Discovery -----------------------------------------------------

    @abstractmethod
    def list_providers(self) -> list[UUID]:
        """All provider_ids that have stored at least one fact."""
        ...

    @abstractmethod
    def count_facts(self, provider_id: UUID | None = None) -> int:
        """Count facts, optionally filtered by provider."""
        ...
