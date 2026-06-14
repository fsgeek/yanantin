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


@dataclass(frozen=True)
class FindHit:
    """One match from find(). Address + a bounded snippet + the SHAPE of what
    matched (matched_fields names which fields, not their values — the slice-2
    discipline). record_id is a BARE UUID, suitable for get()."""
    record_id: str                      # bare UUID (no "records/" prefix)
    snippet: str                        # bounded window around the first match
    matched_fields: tuple[str, ...]     # which field paths matched (shape, not values)


@dataclass(frozen=True)
class FindResult:
    """Serializable result of find(). Addresses + total, never full records.

    v1 SCOPE — content axis only, plaintext values. KNOWN GAPS, declared not
    hidden (each tracked as a gh issue in the find spec):
      - filter / structure / window axes: NOT here (content axis only).
      - relevance/BM25 ranking: NOT here (substring match; order is scan order).
      - value-obfuscation (gh #9): values are searched/stored PLAINTEXT under the
        transparent obfuscator. A real value-map would break this substring path;
        that is #9's slice, not this one.
      - Pukara placement (gh #8): this runs in-process against a live handle. The
        agent-facing posture (find behind Pukara) is downstream, not built here.
      - scan_truncated/max_scan: total_matched is EXACT here because the scan is
        full. The lower-bound semantics arrive with the scan guard, later."""
    hits: tuple[FindHit, ...]
    total_matched: int                  # EXACT (full scan); lower-bound semantics are later
    truncated: bool                     # True when limit cut the hit list short
