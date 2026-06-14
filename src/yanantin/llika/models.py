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

    total_matched is ALWAYS EXACT — count-at-boundary, not a lower bound:
    if len(hits) < limit you've seen them all (total = len(hits), no extra
    work); if len(hits) == limit you hit the boundary and a count is run. The
    earlier max_scan/scan_truncated/lower-bound apparatus is RETIRED, not
    deferred — counting is cheap exactly when you need it, so honest total is
    free. (Tony, 2026-06-13.)

    Indices/views are TUNING, not part of this contract: the naive full scan is
    correct and sufficient to ~100k objects; you won't notice a view until 100k,
    won't be annoyed until 1M. Don't optimize before then. What's load-bearing
    is the MODEL (this result shape + the predicate + the record), not the engine.

    v1 SCOPE — content axis only, plaintext values. KNOWN GAPS (gh issues):
      - filter / structure / window axes: NOT here (content axis only). The
        filter axis is where the dominant anchor lands — the ordinal/temporal
        field (wall-clock for humans, labeled-Lamport (instance_id, cycle) =
        a vector clock for instances), range-queryable. Model admits it; v1
        doesn't build it.
      - relevance/BM25 ranking: NOT here (substring match; order is scan order).
      - value-obfuscation (gh #9): values stored/searched PLAINTEXT under the
        transparent obfuscator; a real value-map breaks substring — #9's slice.
      - Pukara placement (gh #8): in-process here; agent-facing is downstream."""
    hits: tuple[FindHit, ...]
    total_matched: int                  # ALWAYS EXACT (count-at-boundary)
    truncated: bool                     # True when limit cut the list (len(hits) == limit)
