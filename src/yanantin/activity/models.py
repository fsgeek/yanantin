"""Data models for the activity stream layer.

Facts are raw observations — schema-agnostic, high-volume, append-only.
Anchors are lightweight cursors — timestamp + UUID, immutable once issued.
Views are ephemeral resolutions — never cached, never stored.

The lifecycle: Anchor (immutable cursor) -> View (ephemeral resolution)
-> Tensor (frozen/pinned view, an authored act).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _ensure_utc(dt: datetime) -> datetime:
    """Normalize a datetime to UTC.

    Aware datetimes are converted. Naive datetimes are rejected —
    ambiguous timestamps corrupt sort order in every backend.
    ISO 8601 strings sort correctly only when the timezone offset
    is uniform; UTC is that uniform representation.
    """
    if dt.tzinfo is None:
        raise ValueError(
            f"Naive datetime {dt!r} is not allowed. "
            "All activity stream timestamps must be timezone-aware (use UTC)."
        )
    return dt.astimezone(timezone.utc)


class FactRecord(BaseModel):
    """A single observation from a data provider.

    Facts are raw, unedited, schema-agnostic. The store doesn't know
    what's inside ``data`` — that's between the collector and whoever
    queries it later.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="allow",
        validate_default=True,
    )

    id: UUID = Field(default_factory=uuid4)
    provider_id: UUID
    timestamp: datetime
    data: dict
    content_hash: str = ""

    @model_validator(mode="after")
    def _normalize_timestamp(self) -> Self:
        object.__setattr__(self, "timestamp", _ensure_utc(self.timestamp))
        return self


class AnchorCursor(BaseModel):
    """One provider's position in the activity stream.

    Mirrors Indaleko's ActivityDataModel: a provider reference that
    advances when the provider reports new data.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    provider: UUID
    reference: UUID
    data: str | None = None
    attributes: dict[str, str] | None = None


class MemoryAnchor(BaseModel):
    """Immutable snapshot of cursor state at a point in time.

    Written to the store only when the write gate opens. Each anchor
    is a Lamport clock tick — UUID advances only on state change.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    handle: UUID
    timestamp: datetime
    cursors: tuple[AnchorCursor, ...]

    @model_validator(mode="after")
    def _normalize_timestamp(self) -> Self:
        object.__setattr__(self, "timestamp", _ensure_utc(self.timestamp))
        return self


class AnchorView(BaseModel):
    """Ephemeral resolution of an anchor against current streams.

    Never cached, never stored. Constructed fresh on every
    materialize() call. Late-bound: includes providers registered
    after the anchor was created.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    handle: UUID
    timestamp: datetime
    facts: dict[UUID, FactRecord]
    providers: tuple[UUID, ...]
    anchor: MemoryAnchor
