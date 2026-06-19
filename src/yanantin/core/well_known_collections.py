"""The well-known collections registry: semantic name -> CollectionDefinition.

PURE DATA. No logic, no creation. Khipu.watay consults this for a well-known
name's definition ON binding (pulled on demand — NOT an eager startup walk).
This keeps Indaleko's db_collections.py registry SHAPE while deleting its eager
static creator.

This plan (the mechanism) seeds ONE marker entry to prove the registry shape.
Real well-known definitions (Objects, activity_facts, semantic extractors) are
added by their OWN later plans — do not add them here speculatively.
"""

from __future__ import annotations

from yanantin.core.collection_definition import CollectionDefinition

WELL_KNOWN: dict[str, CollectionDefinition] = {
    "khipu_self": CollectionDefinition(),
}


def lookup(name: str) -> CollectionDefinition:
    """Return the definition for a well-known name; raise KeyError if unknown."""
    if name not in WELL_KNOWN:
        raise KeyError(
            f"{name!r} is not a well-known collection. Add it to WELL_KNOWN "
            "in its owning plan, or pass a definition to watay directly."
        )
    return WELL_KNOWN[name]
