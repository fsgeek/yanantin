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

from yanantin.collector.storage_object import StorageObject
from yanantin.core.collection_definition import CollectionDefinition, arangodb_schema

WELL_KNOWN: dict[str, CollectionDefinition] = {
    "khipu_self": CollectionDefinition(),
    # The uniform storage object's home (#17, Pour B / folded A2). Bound
    # schema=None in Pour A1 (the StorageObject model did not yet exist); now it
    # does, so the real schema lands. Strict spine validated at the DB boundary;
    # the open lane survives because StorageObject is extra="allow" — its JSON
    # schema carries no additionalProperties:false, so undeclared top-level
    # fields (e.g. the contribute path's contributor_id) flow (the Task-6
    # invariant). Spec §3.
    #
    # Relationships / the registrant catalog are LEFT schema=None for now. §3
    # shows defs for all three, but binding ProvenanceEdge (extra="forbid") to
    # Relationships and RegistrantRecord to the catalog BROKE live inserts in A1
    # (the contribute_edge path writes contributor_id + extra fields the
    # extra="forbid" edge rejects; the catalog write carries a shape
    # RegistrantRecord's required spine lacks). Objects is the Pour B
    # deliverable; the other two settle in their own pours (be conservative).
    "Objects": CollectionDefinition(
        schema=arangodb_schema(StorageObject),
        indices=(
            {
                "type": "persistent",
                "fields": ["object_identifier"],
                "unique": True,
                "name": "obj_id_idx",
            },
            {"type": "persistent", "fields": ["uri"], "name": "uri_idx"},
            # temporal axis, flat ⇒ indexable directly (the search-space reducer)
            {"type": "persistent", "fields": ["modified"], "name": "modified_idx"},
        ),
    ),
}


def lookup(name: str) -> CollectionDefinition:
    """Return the definition for a well-known name; raise KeyError if unknown."""
    if name not in WELL_KNOWN:
        raise KeyError(
            f"{name!r} is not a well-known collection. Add it to WELL_KNOWN "
            "in its owning plan, or pass a definition to watay directly."
        )
    return WELL_KNOWN[name]
