"""Mechanism-invariance guard: the convergence claim's load-bearing defense
("salience ≠ mechanism") must be EXECUTABLE, not hand-waved.

Four out-of-harness adversarial reviews (DeepSeek, ChatGPT, Gemini, Kimi, round
4, 2026-06-13) INDEPENDENTLY converged on one finding: refutation-condition #4
of the convergence spec — that a human episodic query and an LLM artifact query
use the SAME band-resolution mechanism (anchor → stream → factor-constraint →
intersect), differing only in WHICH factor is salient — is the load-bearing
claim AND has no executable test. Kimi: "so general it risks being descriptive
but not constraining — like saying all transportation is 'just move from A to
B'." ChatGPT: "same API surface is not sufficient; require trace-level sameness,
not interface-level sameness."

The factor-shape red bar tests that each silo can EMIT factor values. It does
NOT test that two different queries RESOLVE THROUGH THE SAME PATH. Different
problems. This guard tests the second: that one resolver compiles BOTH a
human-anchored query and an LLM-anchored query into the SAME intermediate
representation, with NO branch on consumer type below the head boundary.

Pass condition (when built): both queries compile, via ONE resolver entry point,
to a `CompiledQuery` of the same schema, differing only in which factors are
populated / which transducers are named — NOT in structure, NOT in core join
algorithm, NOT via a consumer-type conditional.

Fail conditions (the FORK this guard exists to trap):
  - a separate resolver entry point per consumer type;
  - the two queries produce structurally different intermediate representations;
  - the resolver branches on consumer/identity below the head to produce them;
  - either query bypasses the factor-constraint representation entirely.

There is no resolver and no `CompiledQuery` type in `src/` today (verified
2026-06-13). So this guard is HONESTLY RED. It is the executable form of the one
thing four independent reviewers said was unfalsifiable-as-stated. It goes green
only when a single resolver demonstrably serves both query types through one
intermediate representation — i.e. when the convergence claim becomes TESTABLE.

Tracked: the convergence spec, refutation #4. Depends conceptually on the factor
shape (test_factor_shape.py) and the CompiledQuery interface debt.
"""

from __future__ import annotations

import importlib

import pytest

SIX_FACTORS = ("who", "what", "when", "where", "why", "how")


def _load_resolver():
    """Import the single intent resolver, or None if unbuilt.

    Named structurally: the resolver may land as resolve / compile_intent /
    Resolver.compile in yanantin.resolver. The KEY property this guard enforces
    is that there is ONE entry point taking (intent, consumer_context) — not one
    per consumer type. A module exposing `resolve_human` and `resolve_llm` as the
    only entry points is itself the fork and must fail import here.
    """
    try:
        module = importlib.import_module("yanantin.resolver")
    except ModuleNotFoundError:
        return None
    # The single shared entry point. Per-consumer entry points are the fork.
    for name in ("resolve", "compile_intent", "Resolver"):
        obj = getattr(module, name, None)
        if obj is not None:
            return module, obj
    return module, None


def _require_resolver():
    loaded = _load_resolver()
    if loaded is None:
        pytest.fail(
            "No yanantin.resolver module. The intent compiler that would let the "
            "convergence claim be TESTED does not exist. This guard is the "
            "executable form of refutation #4 (four reviewers: 'salience ≠ "
            "mechanism' is hand-waved). Honestly red until a single resolver "
            "compiles both query types to one intermediate representation."
        )
    module, entry = loaded
    if entry is None:
        pytest.fail(
            "yanantin.resolver exists but exposes no single shared entry point "
            "(resolve / compile_intent / Resolver). If it exposes per-consumer "
            "entry points instead, that IS the fork this guard traps."
        )
    # Trap the obvious fork: per-consumer entry points must NOT be the surface.
    if hasattr(module, "resolve_human") or hasattr(module, "resolve_llm"):
        pytest.fail(
            "yanantin.resolver exposes per-consumer entry points "
            "(resolve_human/resolve_llm). A separate resolver per consumer type "
            "is refutation #4's fork. The claim requires ONE resolver."
        )
    return module, entry


# A human-anchored query and an LLM-anchored query — the two examples the spec
# and the reviewers use. The claim is that these compile the SAME way.
HUMAN_QUERY = "the doc I wrote about Siddhartha six weeks after the big fire in Cedarville"
LLM_QUERY = "where is cross-silo uniformity enforced in this repo"


def _compile(entry, intent, consumer):
    """Call the single entry point in whatever shape it exposes."""
    if isinstance(entry, type):  # Resolver class
        return entry().compile(intent, consumer=consumer)
    return entry(intent, consumer=consumer)


def _schema_of(compiled):
    """The structural signature of a CompiledQuery: the set of its field names.
    Two compiled queries have the 'same intermediate representation' iff their
    structural signature matches — they may differ in VALUES (which factors are
    populated) but not in SHAPE.
    """
    if hasattr(compiled, "model_fields"):  # pydantic
        return frozenset(compiled.model_fields)
    if hasattr(compiled, "__dataclass_fields__"):
        return frozenset(compiled.__dataclass_fields__)
    if isinstance(compiled, dict):
        return frozenset(compiled)
    return frozenset(vars(compiled))


# ── Guard 1: a single resolver compiles BOTH query types ──────────────

@pytest.mark.xfail(strict=True, reason="yanantin.resolver / CompiledQuery does not exist yet (P2 resolver pour): resolver gap")
def test_one_resolver_compiles_both_query_types():
    """One resolver entry point accepts both a human-anchored and an
    LLM-anchored intent and returns a CompiledQuery for each. Honestly red until
    the resolver exists."""
    module, entry = _require_resolver()
    human = _compile(entry, HUMAN_QUERY, consumer="human")
    llm = _compile(entry, LLM_QUERY, consumer="llm")
    assert human is not None and llm is not None, (
        "resolver returned None for one query type"
    )


# ── Guard 2: both compile to the SAME intermediate SCHEMA (trace-level) ─

@pytest.mark.xfail(strict=True, reason="yanantin.resolver / CompiledQuery does not exist yet (P2 resolver pour): resolver gap")
def test_both_queries_compile_to_same_intermediate_schema():
    """The convergence crux, made executable (reviewers' 'trace-level not
    interface-level sameness'). Both compiled queries must have the SAME
    structural signature — same intermediate representation — differing only in
    which factor slots are populated, NOT in shape. Honestly red until a
    resolver emits a stable CompiledQuery for both."""
    module, entry = _require_resolver()
    human = _compile(entry, HUMAN_QUERY, consumer="human")
    llm = _compile(entry, LLM_QUERY, consumer="llm")
    assert _schema_of(human) == _schema_of(llm), (
        "human and LLM queries compiled to DIFFERENT intermediate schemas — "
        "that is refutation #4's fork (different mechanism, not different "
        f"salience). human={_schema_of(human)} llm={_schema_of(llm)}"
    )


# ── Guard 3: the intermediate representation IS factor-constraints ─────

@pytest.mark.xfail(strict=True, reason="yanantin.resolver / CompiledQuery does not exist yet (P2 resolver pour): resolver gap")
def test_intermediate_representation_is_factor_constraints():
    """Both queries must compile to factor-constraints over the six factors —
    neither may bypass the factor-constraint representation (a bypass is a
    forbidden fork). Honestly red until CompiledQuery carries factor
    constraints."""
    module, entry = _require_resolver()
    for intent, consumer in ((HUMAN_QUERY, "human"), (LLM_QUERY, "llm")):
        compiled = _compile(entry, intent, consumer=consumer)
        constraints = getattr(compiled, "factor_constraints", None)
        if constraints is None and isinstance(compiled, dict):
            constraints = compiled.get("factor_constraints")
        assert constraints is not None, (
            f"{consumer} query compiled WITHOUT factor_constraints — it bypassed "
            "the factor representation, a forbidden fork (refutation #4)."
        )
        keys = set(constraints.keys()) if hasattr(constraints, "keys") else set()
        assert keys <= set(SIX_FACTORS), (
            f"{consumer} query constrained on non-factor axes {keys - set(SIX_FACTORS)} "
            "— the intermediate representation must live in the six-factor space."
        )


# ── Guard 4: the resolver does NOT branch on consumer type to build the IR ─

@pytest.mark.xfail(strict=True, reason="yanantin.resolver / CompiledQuery does not exist yet (P2 resolver pour): resolver gap")
def test_resolver_does_not_branch_on_consumer_below_head():
    """No `if consumer == 'llm'` / `if consumer == 'human'` in the resolver
    source: consumer-type branching below the head boundary to BUILD the
    intermediate representation is the fork (allowed consumer differences live
    ABOVE the head, as parameters/disposition — not in resolution). Honestly red
    until the resolver exists; then it bites if a consumer-branch is introduced.
    """
    module, _ = _require_resolver()
    import ast
    from pathlib import Path

    module_file = getattr(module, "__file__", None)
    if module_file is None:
        pytest.fail("cannot locate resolver source to check for consumer-branching.")
    src = Path(module_file).read_text()
    tree = ast.parse(src)
    offenders = []
    for node in ast.walk(tree):
        # crude but real: compare against a literal "human"/"llm" consumer value
        if isinstance(node, ast.Compare):
            consts = [c.value for c in ast.walk(node)
                      if isinstance(c, ast.Constant) and isinstance(c.value, str)]
            if any(v in ("llm", "human") for v in consts):
                offenders.append(node.lineno)
    assert not offenders, (
        "resolver branches on consumer type "
        f"(lines {offenders}) to build the intermediate representation — that is "
        "the fork refutation #4 traps. Consumer differences belong ABOVE the head "
        "(parameters/disposition), not in resolution."
    )
