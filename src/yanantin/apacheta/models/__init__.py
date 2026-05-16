"""Apacheta data models — re-exported from tiksi.

The model definitions live in tiksi (the foundation package). This
module keeps the historical import path `yanantin.apacheta.models`
working for callers that have not yet migrated to `tiksi` directly.
"""

from tiksi import (
    ApachetaBaseModel,
    BootstrapRecord,
    CompositionEdge,
    CorrectionRecord,
    DeclaredLoss,
    DisagreementType,
    DissentRecord,
    EntityResolution,
    EpistemicMetadata,
    KeyClaim,
    LossCategory,
    NegationRecord,
    ProvenanceEnvelope,
    RelationType,
    RepresentationType,
    SchemaEvolutionRecord,
    SourceIdentifier,
    StrandRecord,
    TensorRecord,
)

__all__ = [
    "ApachetaBaseModel",
    "BootstrapRecord",
    "CompositionEdge",
    "CorrectionRecord",
    "DeclaredLoss",
    "DisagreementType",
    "DissentRecord",
    "EntityResolution",
    "EpistemicMetadata",
    "KeyClaim",
    "LossCategory",
    "NegationRecord",
    "ProvenanceEnvelope",
    "RelationType",
    "RepresentationType",
    "SchemaEvolutionRecord",
    "SourceIdentifier",
    "StrandRecord",
    "TensorRecord",
]
