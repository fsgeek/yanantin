"""ProvenanceEdge — cross-collection directed edge for ArangoDB graph traversal.

CompositionEdge (from tiksi) connects tensors to tensors with a closed
RelationType enum. ProvenanceEdge connects any two collections with a
free-string relation_type, enabling machine→fact and collector→fact edges.

ArangoDB requires native _from and _to fields in the format
"collection/key" for a collection to be traversable as a graph edge.
"""

from __future__ import annotations

from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from yanantin.apacheta.models.provenance import ProvenanceEnvelope


class ProvenanceEdge(BaseModel):
    """A directed edge between any two ArangoDB documents.

    _from and _to use ArangoDB's native edge format: "collection/key".
    The document _key is set to str(id) by the backend's store method.
    relation_type is a free string — no enum — to avoid premature
    vocabulary lock-in.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
        populate_by_name=True,
    )

    id: UUID = Field(default_factory=uuid4)
    from_ref: str = Field(alias="_from")
    to_ref: str = Field(alias="_to")
    relation_type: str
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)

    @model_validator(mode="after")
    def _check_ref_format(self) -> Self:
        for field_name, value in (("_from", self.from_ref), ("_to", self.to_ref)):
            if "/" not in value:
                raise ValueError(
                    f"{field_name}={value!r} must be collection/key format, "
                    "e.g. 'entities/8ae0edf526f3453ab1abaf04e1c75a4a'"
                )
        return self
