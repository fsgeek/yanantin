"""Composition models — edges, corrections, dissent, negation, bootstrap, evolution."""

from __future__ import annotations

from enum import Enum
from uuid import UUID, uuid4

from pydantic import Field

from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.provenance import ProvenanceEnvelope


class RelationType(str, Enum):
    """How two tensors relate compositionally."""

    COMPOSES_WITH = "composes_with"
    CORRECTS = "corrects"
    REFINES = "refines"
    BRANCHES_FROM = "branches_from"
    DOES_NOT_COMPOSE_WITH = "does_not_compose_with"
    DISSENTS_FROM = "dissents_from"


class CompositionEdge(ApachetaBaseModel):
    """A directed edge between two tensors."""

    id: UUID = Field(default_factory=uuid4)
    from_tensor: UUID
    to_tensor: UUID
    relation_type: RelationType
    ordering: int = 0
    authored_mapping: str | None = None
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)


class CorrectionRecord(ApachetaBaseModel):
    """A correction to a prior claim. Original is preserved."""

    id: UUID = Field(default_factory=uuid4)
    target_tensor: UUID
    target_strand_index: int | None = None
    target_claim_id: UUID | None = None
    original_claim: str
    corrected_claim: str
    evidence: str = ""
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)


class DissentRecord(ApachetaBaseModel):
    """Formal disagreement with a prior tensor or claim."""

    id: UUID = Field(default_factory=uuid4)
    target_tensor: UUID
    target_claim_id: UUID | None = None
    alternative_framework: str
    reasoning: str
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)


class NegationRecord(ApachetaBaseModel):
    """Declaration that two tensors do not compose."""

    id: UUID = Field(default_factory=uuid4)
    tensor_a: UUID
    tensor_b: UUID
    reasoning: str
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)


class BootstrapRecord(ApachetaBaseModel):
    """What an instance loaded and what it omitted at startup."""

    id: UUID = Field(default_factory=uuid4)
    instance_id: str
    context_budget: float
    task: str = ""
    tensors_selected: tuple[UUID, ...] = Field(default_factory=tuple)
    strands_selected: tuple[int, ...] = Field(default_factory=tuple)
    what_was_omitted: str = ""
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)


class SchemaEvolutionRecord(ApachetaBaseModel):
    """Records a schema change for migration tracking."""

    id: UUID = Field(default_factory=uuid4)
    from_version: str
    to_version: str
    fields_added: tuple[str, ...] = Field(default_factory=tuple)
    fields_removed: tuple[str, ...] = Field(default_factory=tuple)
    migration_notes: str = ""
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)
