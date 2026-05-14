"""Tool variant registry for the memory-tool harness.

A ToolVariant is the unit the runner iterates over: variant_id (stamped
on each captured record), function_name (advertised to the model in the
tool schema), schema (the dict passed to OpenRouter), and impl (the
Python callable invoked when the model issues a tool call). For the
name-effect experiment, the three variants share an impl and a schema
shape — only the function_name differs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from yanantin.apacheta.interface.abstract import ApachetaInterface

from yanantin.experiments.tools.apacheta_tools import (
    QueryBudget,
    find_objects_impl,
    make_find_objects_impl,
)
from yanantin.experiments.tools.schemas import find_objects_schema

ToolImpl = Callable[[ApachetaInterface, dict[str, Any], QueryBudget], dict[str, Any]]


@dataclass(frozen=True)
class ToolVariant:
    variant_id: str
    function_name: str
    schema: dict[str, Any]
    impl: ToolImpl


def build_name_effect_variants() -> list[ToolVariant]:
    """The three name-effect variants. Identical impl; different names."""
    return [
        ToolVariant(
            variant_id="find_objects_v1",
            function_name="find_objects",
            schema=find_objects_schema("find_objects"),
            impl=find_objects_impl,
        ),
        ToolVariant(
            variant_id="search_v1",
            function_name="search",
            schema=find_objects_schema("search"),
            impl=find_objects_impl,
        ),
        ToolVariant(
            variant_id="query_v1",
            function_name="query",
            schema=find_objects_schema("query"),
            impl=find_objects_impl,
        ),
    ]


def build_param_name_probe_variants() -> list[ToolVariant]:
    """Variants for the parameter-name probe: function name and description
    held constant at `find_objects` (aligned English), only the top-level
    filter-container parameter name varies.

    Tests whether Finding 5's substring-extraction mechanism operates on
    parameter identifiers, not just function-name identifiers.

    - `matching`            — neutral baseline (current production schema)
    - `criteria_to_delete`  — destructive substring (`delete`)
    - `records_to_purge`    — different destructive synonym (`purge`)
    - `query_spec`          — clean alternative, also distinct from baseline
    """
    return [
        ToolVariant(
            variant_id="param_matching__find_objects",
            function_name="find_objects",
            schema=find_objects_schema("find_objects", param_name="matching"),
            impl=make_find_objects_impl("matching"),
        ),
        ToolVariant(
            variant_id="param_criteria_to_delete__find_objects",
            function_name="find_objects",
            schema=find_objects_schema("find_objects", param_name="criteria_to_delete"),
            impl=make_find_objects_impl("criteria_to_delete"),
        ),
        ToolVariant(
            variant_id="param_records_to_purge__find_objects",
            function_name="find_objects",
            schema=find_objects_schema("find_objects", param_name="records_to_purge"),
            impl=make_find_objects_impl("records_to_purge"),
        ),
        ToolVariant(
            variant_id="param_query_spec__find_objects",
            function_name="find_objects",
            schema=find_objects_schema("find_objects", param_name="query_spec"),
            impl=make_find_objects_impl("query_spec"),
        ),
    ]
