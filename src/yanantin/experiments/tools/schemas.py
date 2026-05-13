"""OpenAI-format function-calling schemas for the memory-tool harness.

The name-effect experiment turns on three variants of the same tool —
identical description, identical parameters, only the function name
differs. `find_objects_schema(name)` is the single source of truth so
the variants cannot drift apart. The parameter shapes are intentionally
minimal: extra description/default/min/max keys would be a place silent
drift between variants could hide.
"""

from __future__ import annotations

import copy
from typing import Any

FIND_OBJECTS_DESCRIPTION = (
    "Find records matching the given attributes in the associative memory store. "
    "Returns up to `limit` results, ordered newest-first. Use `matching` to filter "
    "by author_instance_id (records produced by a specific author), lineage_tag "
    "(records carrying a specific lineage tag), or has_field (records that carry "
    "a specific free-form key). Each result is an object with id, "
    "author_instance_id, lineage_tags, and any free-form fields the record "
    "carries. If more results exist than requested, `next_cursor` is non-null and "
    "can be passed back to fetch the next page; otherwise it is null."
)

FIND_OBJECTS_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "matching": {
            "type": "object",
            "properties": {
                "author_instance_id": {"type": "string"},
                "lineage_tag": {"type": "string"},
                "has_field": {"type": "string"},
            },
            "required": [],
        },
        "limit": {"type": "integer"},
        "cursor": {"type": ["string", "null"]},
    },
}


def find_objects_schema(name: str) -> dict[str, Any]:
    """Build a tool schema with the given function name.

    Returns a fresh deep copy so callers can mutate the returned dict
    without leaking state between variants.
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": FIND_OBJECTS_DESCRIPTION,
            "parameters": copy.deepcopy(FIND_OBJECTS_PARAMETERS),
        },
    }
