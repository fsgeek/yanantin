"""LlikaService — a thin facade over a GraphBackend.

The privileged ArangoDB handle is GONE. LlikaService no longer resolves
its own database connection and holds no raw handle of any kind; its only
path to data is the GraphBackend it is *given* at construction. The graph
AQL that used to live here moved into ArangoDBBackend, where it routes
through the storage obfuscator. This is the unwalled-gate fix (yanantin#10):
agent-reachable code reaches Llika's graph surface only through the backend
capability — and, in deployment, only through Pukara, which holds the
backend behind the fortress.

The backend's verbs are PER-CALL (provenance is a per-call argument on
link), matching Pukara's stateless routes. The facade may hold a default
provenance for its own in-process callers' convenience; it passes that (or
a per-call override) down to the backend. No provenance is stored on the
backend.

Append-only: link only; no update/delete. find() is intentionally absent
(a callable predicate cannot cross a wire; the customer filters by
structure)."""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.composition import RelationType
from yanantin.llika.models import EdgeResult, PathResult

if TYPE_CHECKING:
    from yanantin.apacheta.interface.graph import GraphBackend


class LlikaService:
    """Create and traverse native ArangoDB edges, through a GraphBackend.

    Holds NO database handle. Constructed with a backend (its only data
    path) and a default provenance for its own callers. Append-only."""

    def __init__(
        self,
        backend: GraphBackend,
        provenance: ProvenanceEnvelope,
    ) -> None:
        self._backend = backend
        self._provenance = provenance

    def link(
        self,
        from_id: str,
        to_id: str,
        relation_type: RelationType,
        provenance: ProvenanceEnvelope | None = None,
        **fields,
    ) -> EdgeResult:
        """Create one immutable edge from_id -> to_id. Uses the facade's
        default provenance unless a per-call provenance is supplied. Returns
        a serializable EdgeResult."""
        return self._backend.link(
            from_id,
            to_id,
            relation_type,
            provenance if provenance is not None else self._provenance,
            **fields,
        )

    def walk(
        self,
        start_id: str,
        direction: str,
        depth: int,
        relation_types: list[str] | None = None,
        max_results: int = 50,
    ) -> list[PathResult]:
        """Traverse from start_id by structure. See GraphBackend.walk."""
        return self._backend.walk(
            start_id, direction, depth, relation_types, max_results
        )

    def neighbors(
        self,
        start_id: str,
        direction: str,
        relation_types: list[str] | None = None,
    ) -> list[PathResult]:
        """Depth-1 convenience: who is adjacent. walk(..., depth=1)."""
        return self._backend.neighbors(start_id, direction, relation_types)

    def get(self, record_id: UUID) -> ApachetaBaseModel:
        """Read a single record by UUID (records-only). Rides the backend's
        existing get_record — no new result type."""
        return self._backend.get_record(record_id)
