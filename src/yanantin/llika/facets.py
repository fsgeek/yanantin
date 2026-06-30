"""Per-query facet discrimination — the Archivist navigator (gh #34).

Read-side intelligence ABOVE the fixed filter axes. Given a too-big result set,
do not offer a menu of axes to filter by; instead measure which facet actually
DISCRIMINATES *this* result set (normalized Shannon entropy over the facet's
values) and surface the highest-information one as a QUESTION. The discriminating
facet is query-dependent — it cannot be a fixed menu, so the facet set is
discovered from the result set's own keys, never enumerated here (open-schema,
the anti-extra=forbid posture this substrate is built on).

Normalized entropy: 1.0 = values evenly split = maximum discrimination (a great
question); ~0 = one value dominates = useless cut for this query. The mechanism
is one pass over the result set in Python — cheap exactly when you need it, the
same philosophy as FindResult.total_matched.

SHAPE, not values, at the boundary: a Facet reports the field name, how many
distinct values, and the discrimination score — not the records. The caller asks
the question; the answer drives a follow-up filter.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# A facet whose normalized entropy is at or above this splits the set usefully;
# below it, one value dominates and the question is not worth asking. Not a
# frozen truth — a starting threshold, tunable, surfaced so the caller sees it.
DISCRIMINATION_FLOOR = 0.5


@dataclass(frozen=True)
class Facet:
    """One candidate navigation axis over a result set. SHAPE, not values:
    `name` + how many distinct values + the discrimination score. `top` carries
    the most common (value, count) pairs so the caller can phrase the question
    ("which session — A, B, or C?") without re-scanning, but it is bounded and
    is distribution-shape, not the records themselves."""

    name: str
    distinct: int
    entropy: float                       # normalized [0, 1]; 1 = max discrimination
    discriminating: bool                 # entropy >= DISCRIMINATION_FLOOR and distinct > 1
    top: tuple[tuple[str, int], ...]     # (value, count), most-common first, bounded


@dataclass(frozen=True)
class FacetDiscrimination:
    """The ranked navigation questions for a result set, most-discriminating
    first. `result_size` is the set these were measured over. Facets with one
    value (or none) rank last — they cannot ask anything. A caller surfaces the
    leading discriminating facet(s) as the question; if none discriminate, there
    is no useful cut and the set must be narrowed another way (named, not hidden)."""

    result_size: int
    facets: tuple[Facet, ...]            # ranked by entropy desc

    @property
    def best(self) -> Facet | None:
        """The single highest-information question, or None if nothing splits
        the set (every facet dominated by one value)."""
        for facet in self.facets:
            if facet.discriminating:
                return facet
        return None


def _normalized_entropy(values: Sequence[Any]) -> tuple[float, int, tuple[tuple[str, int], ...]]:
    """Normalized Shannon entropy over non-null values, the distinct count, and
    the bounded most-common (value, count) pairs.

    None is "this record has no value for this facet" — excluded, not its own
    bucket (an absent field is not an answer to a question). Normalization is by
    log2(distinct) so the score is comparable across facets with different
    cardinalities: a 2-value even split and a 20-value even split both score 1.0
    (both perfectly discriminate, at their own granularity). With one distinct
    value entropy is 0 (nothing to ask)."""
    counts = Counter(str(v) for v in values if v is not None)
    total = sum(counts.values())
    if total == 0:
        return 0.0, 0, ()
    distinct = len(counts)
    if distinct == 1:
        ((value, count),) = counts.items()
        return 0.0, 1, ((value, count),)
    raw = -sum((n / total) * math.log2(n / total) for n in counts.values())
    norm = raw / math.log2(distinct)
    top = tuple(counts.most_common(5))
    return norm, distinct, top


def discriminate(
    records: Sequence[Mapping[str, Any]],
    *,
    facet_fields: Sequence[str] | None = None,
    floor: float = DISCRIMINATION_FLOOR,
) -> FacetDiscrimination:
    """Rank the facets of a result set by how well each discriminates it.

    `facet_fields` defaults to the UNION of keys present across the records —
    discovered, not enumerated (open-schema). Pass an explicit list only to
    restrict to known-meaningful axes; passing one is a narrowing choice the
    caller owns, never a default this function imposes. Private/underscore keys
    (e.g. ArangoDB `_id`/`_rev`) are excluded — they are storage plumbing, not
    navigation axes.

    Returns facets ranked by normalized entropy, most-discriminating first.
    """
    if facet_fields is None:
        discovered: dict[str, None] = {}
        for record in records:
            for key in record:
                if not key.startswith("_"):
                    discovered.setdefault(key, None)
        facet_fields = list(discovered)

    facets: list[Facet] = []
    for field in facet_fields:
        entropy, distinct, top = _normalized_entropy(
            [record.get(field) for record in records]
        )
        facets.append(
            Facet(
                name=field,
                distinct=distinct,
                entropy=entropy,
                discriminating=entropy >= floor and distinct > 1,
                top=top,
            )
        )

    facets.sort(key=lambda f: (f.entropy, f.distinct), reverse=True)
    return FacetDiscrimination(result_size=len(records), facets=tuple(facets))
