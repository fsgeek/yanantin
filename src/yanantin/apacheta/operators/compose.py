"""Compose operator — creates composition edges between tensors.

Bridge = Compose with authored_mapping populated. Single operator,
two modes.
"""

from __future__ import annotations

from uuid import UUID

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.models.composition import CompositionEdge, RelationType
from yanantin.apacheta.models.provenance import ProvenanceEnvelope


def compose(
    interface: ApachetaInterface,
    from_tensor: UUID,
    to_tensor: UUID,
    *,
    ordering: int = 0,
    authored_mapping: str | None = None,
    provenance: ProvenanceEnvelope | None = None,
) -> CompositionEdge:
    """Create a composition edge between two tensors.

    If authored_mapping is provided, this is a bridge composition —
    the mapping describes how strands/claims relate across tensors.

    Composition is non-commutative: compose(A, B) != compose(B, A).
    """
    edge = CompositionEdge(
        from_tensor=from_tensor,
        to_tensor=to_tensor,
        relation_type=RelationType.COMPOSES_WITH,
        ordering=ordering,
        authored_mapping=authored_mapping,
        provenance=provenance or ProvenanceEnvelope(),
    )
    interface.store_composition_edge(edge)
    return edge
