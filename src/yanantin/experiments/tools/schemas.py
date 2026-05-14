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

# Used in description-degradation studies (run_004 etc). The empty
# state is a single period — a non-empty string the schema validator
# accepts but that carries zero semantic content.
EMPTY_DESCRIPTION = "."

# Used in description-degradation studies. Describes a *write*
# operation, creating cue conflict with the find-flavored function
# name and the find-flavored impl.
CONTRADICTING_DESCRIPTION_TEMPLATE = (
    "Store a new record in the associative memory store. The record is "
    "persisted under a freshly-generated id and becomes visible to subsequent "
    "queries. Use `{param_name}` to specify the record's attributes: "
    "author_instance_id (the producing actor), lineage_tag (tagging the "
    "record's lineage), or has_field (an additional free-form key). Returns "
    "the stored record's id and the timestamp of persistence."
)

DESCRIPTION_TEMPLATES: dict[str, str] = {
    "rich": FIND_OBJECTS_DESCRIPTION_TEMPLATE,
    "empty": EMPTY_DESCRIPTION,
    "contradicting": CONTRADICTING_DESCRIPTION_TEMPLATE,
}

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


def find_objects_schema(
    name: str,
    param_name: str = "matching",
    description_state: str = "rich",
) -> dict[str, Any]:
    """Build a tool schema with the given function name, filter-container
    parameter name, and description state.

    description_state values:
      - "rich":          the production find-flavored description
                         (auto-references the parameter name)
      - "empty":         a single period — semantically empty
      - "contradicting": a write-flavored description (cue conflict)

    Returns a fresh deep copy so callers can mutate the returned dict
    without leaking state between variants.
    """
    if description_state not in DESCRIPTION_TEMPLATES:
        raise ValueError(
            f"unknown description_state {description_state!r}; "
            f"expected one of {sorted(DESCRIPTION_TEMPLATES)}"
        )
    template = DESCRIPTION_TEMPLATES[description_state]
    description = template.format(param_name=param_name) if "{param_name}" in template else template
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": copy.deepcopy(_find_objects_parameters(param_name)),
        },
    }
