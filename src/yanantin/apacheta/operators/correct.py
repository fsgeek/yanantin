"""Correct operator — creates a correction record and composition edge."""

from __future__ import annotations

from uuid import UUID

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.models.composition import (
    CompositionEdge,
    CorrectionRecord,
    RelationType,
)
from yanantin.apacheta.models.provenance import ProvenanceEnvelope


def correct(
    interface: ApachetaInterface,
    target_tensor: UUID,
    original_claim: str,
    corrected_claim: str,
    *,
    correcting_tensor: UUID | None = None,
    target_strand_index: int | None = None,
    target_claim_id: UUID | None = None,
    evidence: str = "",
    provenance: ProvenanceEnvelope | None = None,
) -> CorrectionRecord:
    """Correct a prior claim. Original is preserved — always queryable.

    Creates both a CorrectionRecord and a CompositionEdge (type=corrects).
    """
    prov = provenance or ProvenanceEnvelope()
    correction = CorrectionRecord(
        target_tensor=target_tensor,
        target_strand_index=target_strand_index,
        target_claim_id=target_claim_id,
        original_claim=original_claim,
        corrected_claim=corrected_claim,
        evidence=evidence,
        provenance=prov,
    )
    interface.store_correction(correction)

    if correcting_tensor is not None:
        edge = CompositionEdge(
            from_tensor=correcting_tensor,
            to_tensor=target_tensor,
            relation_type=RelationType.CORRECTS,
            provenance=prov,
        )
        interface.store_composition_edge(edge)

    return correction
