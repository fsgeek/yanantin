"""Abstract base classes for the collector/wrangler/recorder pipeline.

Three roles, cleanly separated:

- **Collector** gathers data. It never normalizes, never writes to storage.
- **Wrangler** moves data across boundaries. It never transforms.
- **Recorder** normalizes and stores. It owns the database write.

Each is generic over DataT — the serializable Pydantic model that flows
through the pipeline. The wrangler doesn't know what's inside the envelope.
The recorder doesn't know how the data arrived.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Generic, TypeVar
from uuid import UUID

from yanantin.apacheta.interface import ApachetaInterface
from yanantin.collector.models import WranglerEnvelope

DataT = TypeVar("DataT")


class CollectorBase(ABC, Generic[DataT]):
    """Gathers data from a source. Does not normalize or store.

    A collector knows how to talk to one data source — a filesystem,
    an API, a hardware sensor. It produces a DataT and nothing else.
    The collector is the only component that touches the raw source.
    """

    @abstractmethod
    def collect(self) -> DataT:
        """Gather data from the source and return it.

        The returned value must be a serializable Pydantic model.
        No side effects on storage. No normalization.
        """
        ...

    @abstractmethod
    def get_provider_id(self) -> UUID:
        """Stable identifier for this data provider.

        Must be consistent across invocations for the same logical
        source. Used by the wrangler envelope and recorder for
        provenance tracking.
        """
        ...

    @abstractmethod
    def get_description(self) -> str:
        """Human-readable description of what this collector gathers."""
        ...


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
        """Accept an envelope from the collector side and stage it for pickup.

        After delivery, the envelope's delivered_at and wrangler_strategy
        fields should be populated by the concrete implementation.
        """
        ...

    @abstractmethod
    def receive(self) -> WranglerEnvelope[DataT] | None:
        """Retrieve the next envelope for the recorder side.

        Returns None if no data is available. Implementations should
        return envelopes in delivery order when possible.
        """
        ...

    def stamp_delivery(self, envelope: WranglerEnvelope[DataT]) -> WranglerEnvelope[DataT]:
        """Return a copy of the envelope with delivery provenance filled in.

        Concrete wranglers should call this before staging the envelope.
        Since WranglerEnvelope is frozen, this creates a new instance.
        """
        return envelope.model_copy(
            update={
                "delivered_at": datetime.now(timezone.utc),
                "wrangler_strategy": self.strategy_name,
            },
        )

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Short identifier for this wrangler strategy (e.g., 'direct', 'batch', 'queued')."""
        ...


class RecorderBase(ABC, Generic[DataT]):
    """Consumes data from a wrangler and writes to storage.

    The recorder owns the database write. It normalizes the data,
    maps it to Apacheta records, and stores via the ApachetaInterface.
    One recorder per data type — it knows the schema intimately.
    """

    def __init__(self, interface: ApachetaInterface) -> None:
        self._interface = interface

    @property
    def interface(self) -> ApachetaInterface:
        """The storage interface this recorder writes to."""
        return self._interface

    @abstractmethod
    def record(self, envelope: WranglerEnvelope[DataT]) -> UUID:
        """Normalize data from the envelope and write to storage.

        Returns the UUID of the stored record. The recorder is
        responsible for any transformation needed to fit the data
        into the Apacheta schema.
        """
        ...

    @abstractmethod
    def get_recorder_id(self) -> UUID:
        """Stable identifier for this recorder instance."""
        ...

    @abstractmethod
    def get_description(self) -> str:
        """Human-readable description of what this recorder stores."""
        ...
