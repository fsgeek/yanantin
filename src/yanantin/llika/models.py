"""Llika edge and traversal models.

CompositionEdge is the stored (pydantic) edge form — frozen, extra='allow',
append-only. EdgeResult/PathStep/PathResult are the SERIALIZABLE result types
the service returns across the (eventually-RPC) boundary: plain frozen
dataclasses, JSON-representable, carrying record-id strings and edge metadata —
never raw ArangoDB documents (_id/_rev). field_names is SHAPE, not values."""
from __future__ import annotations

from dataclasses import dataclass
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
    leading-underscore field names."""
    id: UUID = Field(default_factory=uuid4)
    from_ref: str = Field(alias="_from")   # e.g. "tensors/<uuid>"
    to_ref: str = Field(alias="_to")
    created_at: datetime
    relation_type: RelationType
    provenance: ProvenanceEnvelope


@dataclass(frozen=True)
class EdgeResult:
    """Serializable result of link(). No raw arango doc, no pydantic model."""
    edge_id: str          # the edge's UUID, as a string
    from_id: str          # record-id ref
    to_id: str            # record-id ref
    relation_type: str    # RelationType name
    created_at: str       # ISO-8601


@dataclass(frozen=True)
class PathStep:
    """One hop in a traversal. field_names is SHAPE (which fields), not values."""
    record_id: str         # the vertex reached at this step
    relation_type: str     # the edge type that reached it
    field_names: tuple[str, ...]


@dataclass(frozen=True)
class PathResult:
    """An ordered walk from a start vertex. steps[-1] is the far end."""
    start_id: str
    steps: tuple[PathStep, ...]
