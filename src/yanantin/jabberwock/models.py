"""Data models for the Jabberwock NER system.

All models frozen=True (events don't mutate -- event sourcing).

Stored records (Jabberwock, Tove, Vorpal, Rath) use extra="allow":
future versions may add fields, and old code must deserialize new
records without breaking. This is event-sourced deserialization
flexibility, not mutation permission.

Resolved views (Frabjous, MomeResult) use extra="forbid": they're
ephemeral snapshots, never persisted, strict shape is correct.

The Jabberwocky names ARE the real names. They prevent pattern-matching
to known entity resolution frameworks and force structural reasoning.
See docs/jabberwock-spec.md for the glossary.

Provider UUIDs are deterministic via uuid5 -- same domain string always
produces the same UUID. Each record type gets its own provider so the
activity stream can distinguish Jabberwocks from Toves from Vorpals
from Raths without inspecting data contents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Self
from uuid import UUID, NAMESPACE_DNS, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field, model_validator


# -- Deterministic provider UUIDs -----------------------------------------
# Each record type stored in the activity stream uses a distinct provider.

JABBERWOCK_PROVIDER: UUID = uuid5(NAMESPACE_DNS, "yanantin.jabberwock.entity")
TOVE_PROVIDER: UUID = uuid5(NAMESPACE_DNS, "yanantin.jabberwock.tove")
VORPAL_PROVIDER: UUID = uuid5(NAMESPACE_DNS, "yanantin.jabberwock.vorpal")
RATH_PROVIDER: UUID = uuid5(NAMESPACE_DNS, "yanantin.jabberwock.rath")

# The root bandersnatch — the Ouroboros. Self-referential provider.
ROOT_BANDERSNATCH_ID: UUID = uuid5(NAMESPACE_DNS, "yanantin.jabberwock.root")


def _ensure_utc(dt: datetime) -> datetime:
    """Normalize a datetime to UTC.

    Aware datetimes are converted. Naive datetimes are rejected.
    Same contract as activity.models._ensure_utc.
    """
    if dt.tzinfo is None:
        raise ValueError(
            f"Naive datetime {dt!r} is not allowed. "
            "All Jabberwock timestamps must be timezone-aware (use UTC)."
        )
    return dt.astimezone(timezone.utc)


# -- Entity ---------------------------------------------------------------


class Jabberwock(BaseModel):
    """The entity. Known through its effects, not its properties.

    Three fields. UUID, timestamp, who created it. That's all the
    creature IS. Everything else — including what *kind* of entity
    it is — is a Vorpal observation.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: UUID = Field(default_factory=uuid4)
    brillig: datetime  # when first declared into existence
    bandersnatch: UUID  # jabberwock_id of the provider who declared this

    @model_validator(mode="after")
    def _normalize_timestamps(self) -> Self:
        object.__setattr__(self, "brillig", _ensure_utc(self.brillig))
        return self


# -- Alias -----------------------------------------------------------------


class Tove(BaseModel):
    """Alias -- a projection of an entity into a coordinate system.

    A Tove can be mome: jabberwock_id=None means the projection was
    observed but hasn't connected to an entity yet.

    Namespace normalization happens before construction -- the gimble
    stored here is already canonical. Raw observed values go in a
    Vorpal if preservation is needed.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: UUID = Field(default_factory=uuid4)
    jabberwock_id: UUID | None = None  # None = mome (still walking)
    wabe: str  # namespace
    gimble: str  # canonical identifier within the wabe
    gyre_from: datetime  # asserted validity start (world time)
    gyre_to: datetime | None = None  # asserted validity end (None = current)
    bandersnatch: UUID  # jabberwock_id of the observing provider
    brillig: datetime  # when this alias was observed (event time)

    @model_validator(mode="after")
    def _normalize_timestamps(self) -> Self:
        object.__setattr__(self, "brillig", _ensure_utc(self.brillig))
        object.__setattr__(self, "gyre_from", _ensure_utc(self.gyre_from))
        if self.gyre_to is not None:
            object.__setattr__(self, "gyre_to", _ensure_utc(self.gyre_to))
        return self

    @model_validator(mode="after")
    def _validate_gyre_order(self) -> Self:
        if self.gyre_to is not None and self.gyre_to < self.gyre_from:
            raise ValueError(
                f"gyre_to ({self.gyre_to}) cannot precede "
                f"gyre_from ({self.gyre_from})"
            )
        return self

    @model_validator(mode="after")
    def _reject_empty_strings(self) -> Self:
        if not self.wabe.strip():
            raise ValueError("Tove.wabe must be non-empty (got empty or whitespace-only string)")
        if not self.gimble.strip():
            raise ValueError("Tove.gimble must be non-empty (got empty or whitespace-only string)")
        return self


# -- Membership edge -------------------------------------------------------


class Rath(BaseModel):
    """Membership edge -- an entity belongs to a group.

    Groups are Jabberwocks observed with a species Vorpal of "group".
    Raths are graph edges: the thing SQL can't do gracefully.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: UUID = Field(default_factory=uuid4)
    jabberwock_id: UUID  # the member
    borogove_id: UUID  # the group (a Jabberwock with species Vorpal)
    mimsy: str  # role within group
    gyre_from: datetime  # asserted membership start (world time)
    gyre_to: datetime | None = None  # asserted membership end
    bandersnatch: UUID  # jabberwock_id of the observing provider
    brillig: datetime  # when this membership was observed (event time)

    @model_validator(mode="after")
    def _normalize_timestamps(self) -> Self:
        object.__setattr__(self, "brillig", _ensure_utc(self.brillig))
        object.__setattr__(self, "gyre_from", _ensure_utc(self.gyre_from))
        if self.gyre_to is not None:
            object.__setattr__(self, "gyre_to", _ensure_utc(self.gyre_to))
        return self

    @model_validator(mode="after")
    def _validate_gyre_order(self) -> Self:
        if self.gyre_to is not None and self.gyre_to < self.gyre_from:
            raise ValueError(
                f"gyre_to ({self.gyre_to}) cannot precede "
                f"gyre_from ({self.gyre_from})"
            )
        return self


# -- Observation -----------------------------------------------------------


class Vorpal(BaseModel):
    """Observation -- a fact about an entity, pushed and persisted.

    Can be mome: jabberwock_id=None means the blade cut something
    but we don't know what yet. Connection happens via a new claim
    event, not mutation of this record.

    Special tulgey values:
    - "species" -- entity type (person, machine, file, group, model)
    - "claim" -- connects a mome record to an entity
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: UUID = Field(default_factory=uuid4)
    jabberwock_id: UUID | None = None  # None = mome (still walking)
    tulgey: str  # category
    snicker_snack: Any  # the value -- JSON-serializable
    bandersnatch: UUID  # jabberwock_id of the observing provider
    brillig: datetime  # when this observation was made (event time)

    @model_validator(mode="after")
    def _normalize_timestamps(self) -> Self:
        object.__setattr__(self, "brillig", _ensure_utc(self.brillig))
        return self

    @model_validator(mode="after")
    def _reject_empty_tulgey(self) -> Self:
        if not self.tulgey.strip():
            raise ValueError("Vorpal.tulgey must be non-empty (got empty or whitespace-only string)")
        return self


# -- Resolved view ---------------------------------------------------------


class Frabjous(BaseModel):
    """Resolved entity view -- ephemeral, a fold over events.

    Never cached, never stored. Constructed fresh on every resolution.
    Carries its proof envelope: which events caused this resolution.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    jabberwock: Jabberwock
    toves: tuple[Tove, ...] = ()  # all known aliases
    vorpals: tuple[Vorpal, ...] = ()  # all observations
    raths: tuple[Rath, ...] = ()  # all group memberships
    evidence_ids: tuple[UUID, ...] = ()  # IDs of events that built this view
    excluded_count: int = 0  # events excluded (expired gyre, etc.)
    callooh: datetime  # when this resolution was materialized

    @model_validator(mode="after")
    def _normalize_timestamps(self) -> Self:
        object.__setattr__(self, "callooh", _ensure_utc(self.callooh))
        return self


# -- Partial resolution ----------------------------------------------------


class MomeResult(BaseModel):
    """Partial resolution -- the walk isn't over yet.

    Returned when galumph finds matching Toves but can't fully resolve.
    Empty toves means nothing was found at all.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    toves: tuple[Tove, ...] = ()  # matching aliases (possibly unresolved)
    candidates: tuple[Jabberwock, ...] = ()  # possible entities
    mome_vorpals: tuple[Vorpal, ...] = ()  # related unresolved observations
