"""The intent resolver — compiles a query intent into factor-constraints.

One mechanism, not two. A human-anchored query and an LLM-anchored query compile
through the SAME entry point to the SAME intermediate shape (a CompiledQuery
carrying factor_constraints over the six factors) — they differ only in which
factor slots the intent populates, never in machinery. That is what makes
"storage-find is a projection of activity-find" a RESTRICTION of one mechanism
rather than a FORK into two. Spec: docs/superpowers/specs/2026-07-02-resolver.md.

The head boundary (refutation #4): consumer differences live ABOVE the head, as
disposition carried on the query — NOT below it, in the resolution that builds
the intermediate representation. This module never inspects `consumer` to decide
what to extract; `consumer` rides along as data only. (A red-bar AST guard,
test_resolver_does_not_branch_on_consumer_below_head, enforces this by parsing
this source — there must be no `consumer == "llm"/"human"` comparison here.)

It speaks the vocabulary of yanantin.factors: the constraint keys are exactly
the six factors, so a compiled query is addressable in the same coordinate space
an object normalizes into.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from yanantin.factors import FACTORS


class CompiledQuery(BaseModel):
    """The stable intermediate representation both query types compile to.

    Two compiled queries have the SAME structural signature (fields) regardless
    of consumer — the trace-level sameness the convergence claim requires. They
    differ only in which of the six factor slots `factor_constraints` populates.
    """

    model_config = ConfigDict(extra="allow")  # open lane; never forbid

    # The intermediate representation: constraints keyed ONLY by the six factors.
    # A factor absent from this dict is simply unconstrained by the query.
    factor_constraints: dict[str, Any] = Field(default_factory=dict)

    # Disposition, carried ABOVE the head — retained but NOT used to branch the
    # mechanism. A caller may dispose of results differently per consumer; the
    # resolution that produced this query did not.
    consumer: str = "human"

    # The original intent, retained (save-it-all, as factors retains raw).
    intent: str = ""


# Per-factor extraction signals. Each factor is scanned for uniformly — the same
# loop applies every extractor to every intent, so the mechanism cannot branch on
# who is asking. These are deliberately simple for v1 (the tests check SHAPE and
# factor-space membership, not extraction quality); richer extraction (temporal
# windows, entity recognition, the episodic `when` pivot) refines this dict later
# WITHOUT changing the mechanism.
_FACTOR_SIGNALS: dict[str, tuple[str, ...]] = {
    "who": ("who", "by", "author", "wrote", "model", "said"),
    "what": ("what", "doc", "file", "about", "content", "the"),
    "when": ("when", "after", "before", "ago", "weeks", "days", "on", "during"),
    "where": ("where", "in", "at", "repo", "path", "folder", "silo"),
    "why": ("why", "because", "reason", "intent", "purpose"),
    "how": ("how", "via", "using", "ran", "produced", "built"),
}


def _extract_constraint(intent: str, factor: str) -> Any:
    """Extract this factor's constraint from the intent, or None if unsignalled.

    Uniform across factors and across callers: the same tokenized scan runs for
    every factor. v1 records the intent's salient token for a factor when any of
    that factor's signal words appear — enough to produce well-formed, correctly
    keyed factor-constraints. It never consults consumer.
    """
    tokens = [t.strip(".,?\"'").lower() for t in intent.split()]
    token_set = set(tokens)
    signals = _FACTOR_SIGNALS[factor]
    if token_set.isdisjoint(signals):
        return None
    # Record which signals fired — a minimal, honest constraint payload. Richer
    # payloads (the actual entity/window) are a later refinement on this shape.
    return sorted(token_set.intersection(signals))


def resolve(intent: str, *, consumer: str = "human") -> CompiledQuery:
    """Compile a query intent into a CompiledQuery — the single entry point.

    Scans the intent against all six factors uniformly and populates the
    constraints for those that fire. Both a human-anchored and an LLM-anchored
    intent traverse this exact code path and land in the same shape; `consumer`
    is carried onto the result as disposition and never steers the extraction.
    """
    constraints: dict[str, Any] = {}
    for factor in FACTORS:
        found = _extract_constraint(intent, factor)
        if found is not None:
            constraints[factor] = found
    return CompiledQuery(
        factor_constraints=constraints,
        consumer=consumer,
        intent=intent,
    )


class Resolver:
    """Class form of the single entry point (the guards accept either shape).

    Exists so callers who prefer an object can hold a Resolver; it delegates to
    the module-level `resolve` — there is exactly ONE mechanism, not a
    per-consumer method.
    """

    def compile(self, intent: str, *, consumer: str = "human") -> CompiledQuery:
        return resolve(intent, consumer=consumer)
