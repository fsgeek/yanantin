"""LlikaService — tenant-bound graph service over the shared ArangoDB handle.

Constructed against a TIER (the tenant); resolves its own db handle internally
via ApachetaDBConfig().connect(tier). No db/db_name crosses the constructor.
Returns serializable result types — never raw arango docs or pydantic models.
Append-only: link only; no update/delete. find() is intentionally absent (a
callable predicate cannot cross a wire; the customer filters by structure)."""
from __future__ import annotations

from datetime import datetime, timezone

from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.composition import RelationType
from yanantin.infra.config import ApachetaDBConfig
from yanantin.llika.models import CompositionEdge, EdgeResult, PathResult, PathStep

_EDGE_COLLECTION = "llika_composition"

_DIRECTION_AQL = {"forward": "OUTBOUND", "backward": "INBOUND", "both": "ANY"}

# fields the service must NOT surface as content shape (framework envelope)
_ENVELOPE_FIELDS = frozenset({"_id", "_key", "_rev", "_from", "_to",
                              "provenance", "lineage_tags"})


def _field_names(vertex: dict) -> tuple[str, ...]:
    """The vertex's content field NAMES (shape), envelope fields stripped."""
    return tuple(sorted(k for k in vertex if k not in _ENVELOPE_FIELDS))


class LlikaService:
    """Create and traverse native ArangoDB edges. Tenant-bound; append-only."""

    def __init__(self, tier: str, provenance: ProvenanceEnvelope):
        """Bind to a tenant (tier) and resolve the shared db handle internally.

        tier: "app" | "test" | "admin" — the tenant. The caller does NOT name a
        database; the tier->db_name mapping lives in config.
        """
        self._db = ApachetaDBConfig().connect(tier)
        self._provenance = provenance
        if not self._db.has_collection(_EDGE_COLLECTION):
            self._db.create_collection(_EDGE_COLLECTION, edge=True)
        self._edges = self._db.collection(_EDGE_COLLECTION)

    def link(
        self,
        from_id: str,
        to_id: str,
        relation_type: RelationType,
        **fields,
    ) -> EdgeResult:
        """Create one immutable edge from_id -> to_id. Returns a serializable
        EdgeResult — not the raw doc, not the CompositionEdge model."""
        edge = CompositionEdge(
            **{"_from": from_id, "_to": to_id},
            created_at=datetime.now(timezone.utc),
            relation_type=relation_type,
            provenance=self._provenance,
            **fields,
        )
        doc = edge.model_dump(by_alias=True, mode="json")
        self._edges.insert(doc)
        return EdgeResult(
            edge_id=str(edge.id),
            from_id=from_id,
            to_id=to_id,
            relation_type=edge.relation_type.value,
            created_at=doc["created_at"],
        )

    def walk(
        self,
        start_id: str,
        direction: str,
        depth: int,
        relation_types: list[str] | None = None,
        max_results: int = 50,
    ) -> list[PathResult]:
        """Traverse from start_id by structure: direction + depth + optional
        relation_type filter. Returns serializable PathResults carrying every
        intermediate vertex. Capped at max_results in traversal order.

        direction: "forward" (OUTBOUND) | "backward" (INBOUND) | "both" (ANY).
        relation_types: RelationType VALUES to follow (e.g. "composes_with",
            i.e. RelationType.COMPOSES_WITH.value — the stored form that
            EdgeResult/PathStep also report); None follows all."""
        aql_dir = _DIRECTION_AQL[direction]
        rel_filter = ""
        bind_vars: dict = {"start": start_id, "max_depth": depth,
                           "max_results": max_results}
        if relation_types:
            rel_filter = "FILTER e.relation_type IN @relation_types"
            bind_vars["relation_types"] = relation_types
        aql = f"""
        FOR v, e, p IN 1..@max_depth {aql_dir} @start {_EDGE_COLLECTION}
            {rel_filter}
            LIMIT @max_results
            RETURN p
        """
        cursor = self._db.aql.execute(aql, bind_vars=bind_vars)
        results: list[PathResult] = []
        for p in cursor:
            steps = tuple(
                PathStep(
                    record_id=vertex["_id"],
                    relation_type=edge["relation_type"],
                    field_names=_field_names(vertex),
                )
                for vertex, edge in zip(p["vertices"][1:], p["edges"])
            )
            results.append(PathResult(start_id=start_id, steps=steps))
        return results

    def neighbors(
        self,
        start_id: str,
        direction: str,
        relation_types: list[str] | None = None,
    ) -> list[PathResult]:
        """Depth-1 convenience: who is adjacent. walk(..., depth=1)."""
        return self.walk(start_id, direction, depth=1,
                         relation_types=relation_types)
