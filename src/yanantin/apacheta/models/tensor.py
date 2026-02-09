"""Tensor and strand records — the core data unit of Apacheta."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import Field

from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.epistemics import DeclaredLoss, EpistemicMetadata
from yanantin.apacheta.models.provenance import ProvenanceEnvelope


class KeyClaim(ApachetaBaseModel):
    """A specific claim made within a strand, queryable independently."""

    claim_id: UUID = Field(default_factory=uuid4)
    text: str
    epistemic: EpistemicMetadata = Field(default_factory=EpistemicMetadata)
    evidence_refs: tuple[str, ...] = Field(default_factory=tuple)


class StrandRecord(ApachetaBaseModel):
    """A thematic strand within a tensor."""

    strand_index: int
    title: str
    content: str = ""
    topics: tuple[str, ...] = Field(default_factory=tuple)
    key_claims: tuple[KeyClaim, ...] = Field(default_factory=tuple)
    epistemic: EpistemicMetadata | None = None


class TensorRecord(ApachetaBaseModel):
    """A single tensor — an authored compression with epistemic metadata.

    The narrative_body preserves the full markdown. Log before you parse:
    the raw authored text is the ground truth. Structured fields are
    extracted views, not replacements.
    """

    id: UUID = Field(default_factory=uuid4)
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)
    preamble: str = ""
    strands: tuple[StrandRecord, ...] = Field(default_factory=tuple)
    closing: str = ""
    instructions_for_next: str = ""
    narrative_body: str = ""
    lineage_tags: tuple[str, ...] = Field(default_factory=tuple)
    composition_equation: str | None = None
    declared_losses: tuple[DeclaredLoss, ...] = Field(default_factory=tuple)
    epistemic: EpistemicMetadata = Field(default_factory=EpistemicMetadata)
    open_questions: tuple[str, ...] = Field(default_factory=tuple)
