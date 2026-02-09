"""Dissent operator — formal disagreement with a prior tensor or claim."""

from __future__ import annotations

from uuid import UUID

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.models.composition import (
    CompositionEdge,
    DissentRecord,
    RelationType,
)
from yanantin.apacheta.models.provenance import ProvenanceEnvelope


def dissent(
    interface: ApachetaInterface,
    dissenting_tensor: UUID,
    target_tensor: UUID,
    alternative_framework: str,
    reasoning: str,
    *,
    target_claim_id: UUID | None = None,
    provenance: ProvenanceEnvelope | None = None,
) -> DissentRecord:
    """Register formal disagreement with a prior tensor or claim.

    Creates both a DissentRecord and a CompositionEdge (type=dissents_from).
    """
    prov = provenance or ProvenanceEnvelope()
    record = DissentRecord(
        target_tensor=target_tensor,
        target_claim_id=target_claim_id,
        alternative_framework=alternative_framework,
        reasoning=reasoning,
        provenance=prov,
    )
    interface.store_dissent(record)

    edge = CompositionEdge(
        from_tensor=dissenting_tensor,
        to_tensor=target_tensor,
        relation_type=RelationType.DISSENTS_FROM,
        provenance=prov,
    )
    interface.store_composition_edge(edge)

    return record
