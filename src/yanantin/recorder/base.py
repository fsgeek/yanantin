"""Abstract base classes for recorders.

- **RecorderBase** normalizes data and writes tensors via ApachetaInterface.
- **FactRecorderBase** writes raw facts to ActivityStreamStore.

Both are generic over DataT and consume WranglerEnvelope from the transport layer.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from uuid import UUID

from yanantin.apacheta.interface import ApachetaInterface
from yanantin.activity.store import ActivityStreamStore
from yanantin.transport.models import WranglerEnvelope

DataT = TypeVar("DataT")


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

    @staticmethod
    def _content_hash(data) -> str:
        """SHA-256 of deterministic JSON serialization, truncated to 16 hex chars."""
        serialized = json.dumps(
            data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    @abstractmethod
    def record(self, envelope: WranglerEnvelope[DataT]) -> UUID:
        """Normalize data from the envelope and write to storage."""
        ...

    @abstractmethod
    def get_recorder_id(self) -> UUID:
        """Stable identifier for this recorder instance."""
        ...

    @abstractmethod
    def get_description(self) -> str:
        """Human-readable description of what this recorder stores."""
        ...


class FactRecorderBase(ABC, Generic[DataT]):
    """Records collected data as facts in the activity stream.

    Unlike RecorderBase (which produces tensors), FactRecorderBase
    produces facts — raw observations stored in ActivityStreamStore.
    Returns int (count of facts stored), not list[UUID].
    """

    def __init__(self, store: ActivityStreamStore) -> None:
        self._store = store

    @property
    def store(self) -> ActivityStreamStore:
        """The activity stream store this recorder writes to."""
        return self._store

    @staticmethod
    def _content_hash(data) -> str:
        """SHA-256 of deterministic JSON serialization, truncated to 16 hex chars."""
        serialized = json.dumps(
            data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    @abstractmethod
    def record_facts(self, envelope: WranglerEnvelope[DataT]) -> int:
        """Store facts from the envelope. Return count stored."""
        ...

    @abstractmethod
    def get_recorder_id(self) -> UUID:
        """Stable identifier for this recorder instance."""
        ...

    @abstractmethod
    def get_description(self) -> str:
        """Human-readable description of what this recorder stores."""
        ...
