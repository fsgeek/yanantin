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


SEVERITY_GRADIENT_VERBS = (
    "find",      # baseline / aligned with operation
    "retrieve",  # near-neutral read verb
    "fetch",     # near-neutral read verb
    "extract",   # extraction; mildly destructive connotation
    "remove",    # destructive
    "delete",    # destructive (Gemini veto observed at function-name slot)
    "purge",     # destructive, stronger
    "destroy",   # destructive, strongest
)


def build_severity_gradient_variants() -> list[ToolVariant]:
    """16 variants: 8 destructive-verb levels x 2 identifier slots.

    Function-name slot (8 variants): function name varies as `{verb}_objects`,
    parameter name held constant at `matching`.

    Parameter-name slot (8 variants): function name held constant at
    `find_objects` (aligned), top-level filter-container parameter name
    varies as `{verb}_criteria`.

    Both slots share the same rich aligned description template, which
    auto-references whatever parameter name the variant uses (mirroring
    real-world API conventions where docs cite their own parameter
    names).

    Tests two questions simultaneously:
    (1) Where in the verb-severity ordering does Gemini's name-affordance
        veto threshold actually sit at the function-name slot?
    (2) Does the positional-keying result from Finding 7 hold across
        the entire severity gradient at the parameter-name slot, or does
        a sufficiently strong destructive verb (e.g. `destroy_criteria`)
        eventually break it?
    """
    variants: list[ToolVariant] = []
    for verb in SEVERITY_GRADIENT_VERBS:
        # Function-name slot
        fn_name = f"{verb}_objects"
        variants.append(
            ToolVariant(
                variant_id=f"grad_fn__{fn_name}",
                function_name=fn_name,
                schema=find_objects_schema(fn_name, param_name="matching"),
                impl=find_objects_impl,
            )
        )
        # Parameter-name slot
        param_name = f"{verb}_criteria"
        variants.append(
            ToolVariant(
                variant_id=f"grad_param__{param_name}",
                function_name="find_objects",
                schema=find_objects_schema("find_objects", param_name=param_name),
                impl=make_find_objects_impl(param_name),
            )
        )
    return variants


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
