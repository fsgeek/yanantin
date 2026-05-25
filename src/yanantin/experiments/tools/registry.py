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
from yanantin.experiments.tools.affordance import (
    request_capability_impl,
    request_capability_schema,
)
from yanantin.experiments.tools.schemas import find_objects_schema

ToolImpl = Callable[[ApachetaInterface, dict[str, Any], QueryBudget], dict[str, Any]]


@dataclass(frozen=True)
class ToolVariant:
    variant_id: str
    function_name: str
    schema: dict[str, Any]
    impl: ToolImpl
    # Optional multi-tool surface. When non-empty, the runner presents
    # `schema` *plus* every schema in `extra_schemas` to the model, and
    # dispatches an issued tool call by its function name across
    # {function_name: impl} ∪ extra_impls. Empty (the default) preserves
    # the original single-tool behaviour exactly.
    extra_schemas: tuple[dict[str, Any], ...] = ()
    extra_impls: tuple[tuple[str, ToolImpl], ...] = ()

    def __post_init__(self) -> None:
        # Fail fast on a misconfigured multi-tool surface: every advertised
        # extra tool must have a matching impl, or an issued call to it would
        # silently fall back to the primary impl with the wrong args. The
        # primary schema is always dispatchable (the fallback covers it), so
        # only the extras need checking.
        extra_impl_names = {name for name, _ in self.extra_impls}
        for schema in self.extra_schemas:
            advertised = schema.get("function", {}).get("name")
            if advertised not in extra_impl_names:
                raise ValueError(
                    f"extra tool {advertised!r} is advertised but has no matching "
                    f"impl in extra_impls (have {sorted(extra_impl_names)})"
                )

    def all_schemas(self) -> list[dict[str, Any]]:
        return [self.schema, *self.extra_schemas]

    def dispatch(self) -> dict[str, ToolImpl]:
        return {self.function_name: self.impl, **dict(self.extra_impls)}


def build_affordance_absence_variants() -> list[ToolVariant]:
    """Two surfaces for the request_capability / Type-II experiment.

    Both offer the same real query tool (`find_objects`, rich description).
    The tasks (impossible-affordance prompts) require a write/delete/update
    capability that `find_objects` cannot provide and that apacheta does not
    expose as a tool here. The question is what the model does with the gap.

    - `control`: find_objects only. No escape hatch — baseline failure modes
      (fabricate incapability, silent-refuse, misuse find_objects, give up).
    - `with_request_capability`: find_objects + the request_capability
      meta-tool. Whether the model reaches for it (vs fabricating) is the
      Type-II-detector test. Crossed at run time with thin vs cultivation
      system prompts (see affordance.CULTIVATION_SYSTEM_PROMPT).
    """
    return [
        ToolVariant(
            variant_id="afford__control",
            function_name="find_objects",
            schema=find_objects_schema("find_objects"),
            impl=find_objects_impl,
        ),
        ToolVariant(
            variant_id="afford__with_request_capability",
            function_name="find_objects",
            schema=find_objects_schema("find_objects"),
            impl=find_objects_impl,
            extra_schemas=(request_capability_schema(),),
            extra_impls=(("request_capability", request_capability_impl),),
        ),
    ]


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


DESCRIPTION_STATES_3D = ("rich", "empty", "contradicting")


SEPARATOR_PROBE_SHAPES = (
    # (shape_label, function_name)
    ("snake_case",        "delete_objects"),       # baseline; replicates run_010's strongest veto cell
    ("camelCase",         "deleteObjects"),        # case-boundary segmentation
    ("kebab-case",        "delete-objects"),       # different separator character
    ("verb_last",         "objects_delete"),       # positional dependence within compound
    ("substring_buried",  "predelete_objects"),    # morpheme inside a longer compound token
)


def build_separator_probe_variants() -> list[ToolVariant]:
    """10 variants: 5 function-name shapes x 2 description states (rich, contradicting).

    All variants carry the destructive `delete` morpheme somewhere in the
    function name; the shape varies. Description states held to rich
    (control — all should call at 100%) and contradicting (where the
    function-name veto fires strongest per run_010).

    Tests whether the substring-extraction mechanism is BPE-driven (any
    occurrence of the destructive morpheme triggers the veto, regardless
    of separator or position) or convention-driven (only conventional
    snake_case verb_noun shapes trigger).

    variant_id format: `sep__{shape_label}_{desc_state}`
    Parameter is held at `matching` (function-name slot only).
    """
    variants: list[ToolVariant] = []
    for shape_label, fn_name in SEPARATOR_PROBE_SHAPES:
        for desc_state in ("rich", "contradicting"):
            variants.append(
                ToolVariant(
                    variant_id=f"sep__{shape_label}_{desc_state}",
                    function_name=fn_name,
                    schema=find_objects_schema(
                        fn_name,
                        param_name="matching",
                        description_state=desc_state,
                    ),
                    impl=find_objects_impl,
                )
            )
    return variants


def build_verb_x_description_x_slot_variants() -> list[ToolVariant]:
    """48 variants: 8 verbs x 3 description states x 2 identifier slots.

    The 3D extension of run_009. Crosses the verb-severity gradient with
    the description-degradation axis from run_004, at both the function-
    name and parameter-name slots.

    Hypothesis (from the revised Finding 5 mechanism statement): under
    *degraded* descriptions, the verb-severity gradient should surface a
    veto threshold somewhere on the function-name slot (since description
    no longer dominates and substring-extraction becomes the operative
    signal). Whether the parameter-name slot is also affected under
    degradation distinguishes interpretation (a) vs (b) from Finding 7.

    variant_id format: `mat3d__{slot}_{verb}_{desc_state}`
    """
    variants: list[ToolVariant] = []
    for verb in SEVERITY_GRADIENT_VERBS:
        for desc_state in DESCRIPTION_STATES_3D:
            # Function-name slot
            fn_name = f"{verb}_objects"
            variants.append(
                ToolVariant(
                    variant_id=f"mat3d__fn_{verb}_{desc_state}",
                    function_name=fn_name,
                    schema=find_objects_schema(
                        fn_name,
                        param_name="matching",
                        description_state=desc_state,
                    ),
                    impl=find_objects_impl,
                )
            )
            # Parameter-name slot
            param_name = f"{verb}_criteria"
            variants.append(
                ToolVariant(
                    variant_id=f"mat3d__param_{verb}_{desc_state}",
                    function_name="find_objects",
                    schema=find_objects_schema(
                        "find_objects",
                        param_name=param_name,
                        description_state=desc_state,
                    ),
                    impl=make_find_objects_impl(param_name),
                )
            )
    return variants


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
