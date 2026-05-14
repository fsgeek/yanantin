"""OpenAI-format function-calling schemas for the memory-tool harness.

The name-effect experiment turns on three variants of the same tool —
identical description, identical parameters, only the function name
differs. `find_objects_schema(name)` is the single source of truth so
the variants cannot drift apart. The parameter shapes are intentionally
minimal: extra description/default/min/max keys would be a place silent
drift between variants could hide.

`param_name` parameterises the top-level filter-container key (default
"matching"). Renaming this key is the surface tested by the
parameter-name probe — it lets us vary parameter identifiers
independently of the function name.
"""

from __future__ import annotations

import copy
from typing import Any

FIND_OBJECTS_DESCRIPTION_TEMPLATE = (
    "Find records matching the given attributes in the associative memory store. "
    "Returns up to `limit` results, ordered newest-first. Use `{param_name}` to filter "
    "by author_instance_id (records produced by a specific author), lineage_tag "
    "(records carrying a specific lineage tag), or has_field (records that carry "
    "a specific free-form key). Each result is an object with id, "
    "author_instance_id, lineage_tags, and any free-form fields the record "
    "carries. If more results exist than requested, `next_cursor` is non-null and "
    "can be passed back to fetch the next page; otherwise it is null."
)

FIND_OBJECTS_DESCRIPTION = FIND_OBJECTS_DESCRIPTION_TEMPLATE.format(param_name="matching")


def _find_objects_parameters(param_name: str) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            param_name: {
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


# Preserved for backward compatibility with existing callers/tests.
FIND_OBJECTS_PARAMETERS: dict[str, Any] = _find_objects_parameters("matching")


def find_objects_schema(name: str, param_name: str = "matching") -> dict[str, Any]:
    """Build a tool schema with the given function name and filter-container parameter name.

    Returns a fresh deep copy so callers can mutate the returned dict
    without leaking state between variants.
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": FIND_OBJECTS_DESCRIPTION_TEMPLATE.format(param_name=param_name),
            "parameters": copy.deepcopy(_find_objects_parameters(param_name)),
        },
    }
