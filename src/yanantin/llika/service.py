"""LlikaService — thin graph service over a shared ArangoDB handle."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from arango.database import StandardDatabase

from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.composition import RelationType
from yanantin.llika.models import CompositionEdge, Path

_EDGE_COLLECTION = "llika_composition"


class LlikaService:
    """Create and traverse native ArangoDB edges. Append-only; no update/delete."""

    def __init__(self, db: StandardDatabase, provenance: ProvenanceEnvelope):
        self._db = db
        self._provenance = provenance
        if not db.has_collection(_EDGE_COLLECTION):
            db.create_collection(_EDGE_COLLECTION, edge=True)
        self._edges = db.collection(_EDGE_COLLECTION)

    def link(
        self,
        from_id: str,
        to_id: str,
        relation_type: RelationType,
        **kwargs,
    ) -> CompositionEdge:
        """Create one immutable edge from_id -> to_id. kwargs become open fields."""
        edge = CompositionEdge(
            **{"_from": from_id, "_to": to_id},
            created_at=datetime.now(timezone.utc),
            relation_type=relation_type,
            provenance=self._provenance,
            **kwargs,
        )
        doc = edge.model_dump(by_alias=True, mode="json")
        self._edges.insert(doc)
        return edge

    def find(
        self,
        vertex_id: str,
        predicate: Callable[[dict], bool],
        max_depth: int = 4,
        max_results: int = 50,
    ) -> list[Path]:
        """Walk OUTBOUND from vertex_id; return paths to vertices matching
        predicate (Python-side), capped at max_results in traversal order.

        SCOPE (Phase 1): raw traversal — walks ALL edges including superseded
        ones; honors NO retraction semantics. The path is the answer."""
        aql = f"""
        FOR v, e, p IN 1..@max_depth OUTBOUND @start {_EDGE_COLLECTION}
            RETURN p
        """
        cursor = self._db.aql.execute(
            aql, bind_vars={"max_depth": max_depth, "start": vertex_id}
        )
        results: list[Path] = []
        for p in cursor:
            terminal = p["vertices"][-1]
            if predicate(terminal):
                results.append(
                    Path(vertices=tuple(p["vertices"]), edges=tuple(p["edges"]))
                )
                if len(results) >= max_results:
                    break
        return results
