"""A collection's shape: schema (from a Pydantic model), indices, views.

`Khipu.watay` consumes a CollectionDefinition to create+shape a collection.
Schema is generated from the model via arangodb_schema() — Indaleko's envelope
(data_models/base.py:93) ported verbatim: level 'strict' = validate on every
write (NOT 'no extra fields'; that is additionalProperties, governed by the
model's extra= config). A model with extra='allow' keeps an open lane.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def arangodb_schema(model: type[BaseModel]) -> dict:
    """Wrap a Pydantic model's JSON schema in ArangoDB's validation envelope."""
    return {
        "message": "Document did not conform to the collection schema.",
        "level": "strict",
        "type": "json",
        "rule": model.model_json_schema(),
    }


class CollectionDefinition(BaseModel):
    """The shape of one collection. Pure data; no DB handle, no identity."""

    model_config = ConfigDict(frozen=True)

    schema: dict | None = None
    indices: tuple[dict, ...] = ()
    views: tuple[dict, ...] = ()
    edge: bool = False
