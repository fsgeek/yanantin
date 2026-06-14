"""CollectorBase — the data-gathering half of the pipeline.

Private module. Import from yanantin.collector.base (the public shim)
or yanantin.collector directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

DataT = TypeVar("DataT")


class CollectorBase(ABC, Generic[DataT]):
    """Gathers data from a source. Does not normalize or store.

    A collector knows how to talk to one data source — a filesystem,
    an API, a hardware sensor. It produces a DataT and nothing else.
    The collector is the only component that touches the raw source.
    """

    @abstractmethod
    def collect(self, since: datetime | None = None) -> DataT:
        """Gather data from the source and return it.

        The returned value must be a serializable Pydantic model.
        No side effects on storage. No normalization.
        """
        ...

    @abstractmethod
    def get_provider_id(self) -> UUID:
        """Stable identifier for this data provider."""
        ...

    @abstractmethod
    def get_description(self) -> str:
        """Human-readable description of what this collector gathers."""
        ...
