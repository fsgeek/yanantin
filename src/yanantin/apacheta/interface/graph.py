"""GraphBackend — narrow graph capability, OFF the public ApachetaInterface.

The find spec forbids adding graph verbs to the public ApachetaInterface
domain catalog ("it is already the leak"). So Llika's graph surface lives
here, in a small protocol Pukara can import without dragging in the ~40-method
domain catalog. ArangoDBBackend implements both ApachetaInterface and this.

The verbs are PER-CALL and stateless (provenance is a per-call argument on
link, not constructor state) so the protocol maps one-to-one onto Pukara's
stateless routes — a library→network-service transport swap with no shape
change. The result types are the frozen, wire-safe dataclasses from
yanantin.llika.models (EdgeResult / PathStep / PathResult); no raw arango
docs cross this boundary. `get` rides the existing get_record on
ApachetaInterface — no new result type is invented for it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.composition import RelationType
from yanantin.llika.models import EdgeResult, PathResult


@runtime_checkable
class GraphBackend(Protocol):
    """Llika's graph surface: link / walk / neighbors / get.

    id-shape convention (resolved mixed, per-verb — yanantin#10 SEAM 1):
    - link / walk / neighbors take "collection/<uuid>" slash-form refs,
      because a composition edge crosses collections (e.g.
      tensors/<uuid> -> records/<uuid>) and a bare UUID is ambiguous.
    - get takes a bare UUID (records-only via get_record, unambiguous).
    """

    def link(
        self,
        from_ref: str,
        to_ref: str,
        relation_type: RelationType,
        provenance: ProvenanceEnvelope,
        **fields: object,
    ) -> EdgeResult: ...

    def walk(
        self,
        start_id: str,
        direction: str,
        depth: int,
        relation_types: list[str] | None = None,
        max_results: int = 50,
    ) -> list[PathResult]: ...

    def neighbors(
        self,
        start_id: str,
        direction: str,
        relation_types: list[str] | None = None,
    ) -> list[PathResult]: ...

    def get_record(self, record_id: UUID) -> ApachetaBaseModel: ...


__all__ = ["GraphBackend"]
