"""Abstract base class for wrangler transport strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Generic, TypeVar

from yanantin.transport.models import WranglerEnvelope

DataT = TypeVar("DataT")


class WranglerBase(ABC, Generic[DataT]):
    """Moves data from collector to recorder across a boundary.

    The wrangler is a transport. It wraps data in a WranglerEnvelope
    with delivery provenance and hands it off. Concrete strategies
    differ in coupling: in-memory (direct), file-based (batch), or
    queue-based (async).

    The wrangler never transforms the data. Transformation is the
    recorder's job.
    """

    @abstractmethod
    def deliver(self, envelope: WranglerEnvelope[DataT]) -> None:
        """Accept an envelope from the collector side and stage it for pickup."""
        ...

    @abstractmethod
    def receive(self) -> WranglerEnvelope[DataT] | None:
        """Retrieve the next envelope for the recorder side."""
        ...

    def stamp_delivery(self, envelope: WranglerEnvelope[DataT]) -> WranglerEnvelope[DataT]:
        """Return a copy of the envelope with delivery provenance filled in."""
        return envelope.model_copy(
            update={
                "delivered_at": datetime.now(timezone.utc),
                "wrangler_strategy": self.strategy_name,
            },
        )

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Short identifier for this wrangler strategy."""
        ...
