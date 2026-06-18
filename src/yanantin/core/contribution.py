"""The contribution-mapping vocabulary: how a recorder declares WHERE its
output lands (ContributionTarget) and the thin provenance-bearing shape it
contributes (ContributedRecord). NOT the #17 uniform StorageObject — that is
a separate, deferred pour. Field names are deliberately minimal; the spec
does not freeze them (2026-06-17-recorder-collection-mapping-design.md)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContributionTarget(BaseModel):
    """One entry in a recorder's `contributes_to` declaration: a collection
    its output lands in. `kind` doc vs edge; `naming` well_known (attach to a
    shared owned collection) vs dynamic (mint own). The registrar stores this
    OPAQUELY in its open tail; only the recorder acts on it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    kind: Literal["doc", "edge"]
    naming: Literal["well_known", "dynamic"]


class ContributedRecord(BaseModel):
    """A thin provenance-bearing document a recorder contributes into an owned
    collection. The typed spine resolves provenance to a registered provider
    (`source`); `raw` is the opaque save-everything payload; the open tail
    carries normalized fields. This embeds provenance whose source resolves to
    a registered provider_id — the spec's frozen requirement — without building
    the uniform StorageObject (#17)."""

    model_config = ConfigDict(frozen=True, extra="allow")

    source: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict = Field(default_factory=dict)

    def to_contribution_fields(self) -> dict:
        """Render to the **fields dict for Registrar.contribute: json mode so
        source/timestamp are storage-ready, open-tail fields included."""
        return self.model_dump(mode="json")
