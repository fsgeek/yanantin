"""Llika edge and traversal models. Frozen, extra='allow', append-only."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import Field

from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.composition import RelationType


class CompositionEdge(ApachetaBaseModel):
    """A native ArangoDB edge between two vertices. Immutable once created.

    Distinct from the flat tiksi.CompositionEdge (from_tensor/to_tensor plain
    fields): this is the *graph* form, carrying ArangoDB's required `_from`/`_to`
    edge refs (e.g. "tensors/<uuid>") via aliases, since pydantic forbids
    leading-underscore field names. This is the migration target the Llika spec
    describes."""
    id: UUID = Field(default_factory=uuid4)
    from_ref: str = Field(alias="_from")   # e.g. "tensors/<uuid>"
    to_ref: str = Field(alias="_to")
    created_at: datetime
    relation_type: RelationType
    provenance: ProvenanceEnvelope


class Path(ApachetaBaseModel):
    """An ordered traversal result: the path is the answer, not just the end.

    vertices and edges are raw dicts as returned by ArangoDB — Llika does not
    interpret vertex kinds (per llika-spec)."""
    vertices: tuple[dict, ...]
    edges: tuple[dict, ...]
