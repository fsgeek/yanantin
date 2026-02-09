"""Entity resolution — UUID-to-identity mapping with redaction support."""

from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import Field

from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.provenance import ProvenanceEnvelope


class EntityResolution(ApachetaBaseModel):
    """Maps a UUID to an identity. Redaction = delete the mapping.

    Privacy-as-architecture: redacting an entity doesn't touch any
    tensor records. It removes the ability to resolve who the UUID
    refers to.
    """

    id: UUID = Field(default_factory=uuid4)
    entity_uuid: UUID
    identity_type: str
    identity_data: dict = Field(default_factory=dict)
    redacted: bool = False
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)
