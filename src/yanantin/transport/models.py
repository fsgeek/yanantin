"""Data models for the transport pipeline.

Serializable data is the boundary contract. Everything that moves through
the pipeline is a Pydantic model that can go through any wrangler strategy
unchanged. The wrangler doesn't transform data — it moves it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class ProviderRegistration(BaseModel):
    """Registration record for a collector/recorder pair.

    Answers: what is this data source, what does it produce, and when
    did it join the pipeline? The data_schema field carries the JSON
    schema of the DataT so that recorders can validate without knowing
    the concrete type at import time.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    provider_id: UUID = Field(default_factory=uuid4)
    provider_name: str
    collector_description: str = ""
    recorder_description: str = ""
    data_schema: dict = Field(default_factory=dict)
    registered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class WranglerEnvelope(BaseModel, Generic[DataT]):
    """Wraps collected data with transport provenance.

    The envelope is what moves through the wrangler. The data inside
    is untouched — the envelope records who collected it, when, and
    how it was delivered. Sequence numbers are monotonic per provider,
    so a recorder can detect gaps.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    data: DataT
    provider_id: UUID
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    delivered_at: datetime | None = None
    wrangler_strategy: str = ""
    sequence_number: int = 0
