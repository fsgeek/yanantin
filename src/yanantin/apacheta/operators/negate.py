"""Negate operator — declares that two tensors do not compose."""

from __future__ import annotations

from uuid import UUID

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.models.composition import (
    CompositionEdge,
    NegationRecord,
    RelationType,
)
from yanantin.apacheta.models.provenance import ProvenanceEnvelope


def negate(
    interface: ApachetaInterface,
    tensor_a: UUID,
    tensor_b: UUID,
    reasoning: str,
    *,
    provenance: ProvenanceEnvelope | None = None,
) -> NegationRecord:
    """Declare that two tensors do not compose.

    Creates a NegationRecord and a CompositionEdge (type=does_not_compose_with).
    """
    prov = provenance or ProvenanceEnvelope()
    record = NegationRecord(
        tensor_a=tensor_a,
        tensor_b=tensor_b,
        reasoning=reasoning,
        provenance=prov,
    )
    interface.store_negation(record)

    edge = CompositionEdge(
        from_tensor=tensor_a,
        to_tensor=tensor_b,
        relation_type=RelationType.DOES_NOT_COMPOSE_WITH,
        provenance=prov,
    )
    interface.store_composition_edge(edge)

    return record
