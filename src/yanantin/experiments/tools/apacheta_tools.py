"""Python implementations of the memory tools against the apacheta interface.

Currently: just `find_objects_impl`. Read-only against the supplied
ApachetaInterface (never calls store_*). Query-budget guarded so a
runaway model can't enumerate the whole store in one trajectory.

Multi-filter ambiguity policy: when the model supplies several filter
keys (e.g. both author_instance_id and lineage_tag in `matching`), the
impl picks one by priority order — author_instance_id, lineage_tag,
has_field — and reports the unused keys in `ignored_filters`. We do not
raise: the experiment wants malformed/conflicting calls captured as
data, not as exceptions. The analyst can spot tools-misuse via the
`ignored_filters` slot.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from yanantin.apacheta.interface.abstract import ApachetaInterface


class QueryBudgetExceeded(RuntimeError):
    """Raised when a tool call would exceed its remaining query budget."""


class QueryBudget:
    """Decrementing counter. One charge per tool call."""

    def __init__(self, remaining: int) -> None:
        if remaining < 0:
            raise ValueError(f"remaining must be non-negative, got {remaining!r}")
        self._remaining = int(remaining)

    @property
    def remaining(self) -> int:
        return self._remaining

    def charge(self) -> None:
        if self._remaining <= 0:
            raise QueryBudgetExceeded("query budget exhausted")
        self._remaining -= 1


_FILTER_PRIORITY = ("author_instance_id", "lineage_tag", "has_field")


def _envelope_for(records: list[tuple[UUID, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rid, record in records:
        envelope = getattr(record, "provenance", None) or {}
        author = envelope.get("author_instance_id") if isinstance(envelope, dict) else None
        tags = getattr(record, "lineage_tags", None) or []
        if not isinstance(tags, list):
            tags = []
        extra = getattr(record, "model_extra", None) or {}
        out.append(
            {
                "id": str(rid),
                "author_instance_id": author,
                "lineage_tags": list(tags),
                "fields": dict(extra),
            }
        )
    return out


def find_objects_impl(
    apacheta: ApachetaInterface,
    args: dict[str, Any],
    budget: QueryBudget,
) -> dict[str, Any]:
    """Resolve a `find_objects`-shaped call against the apacheta store.

    Default behaviour: reads the filter container from `args["matching"]`.
    For variants that rename this parameter, use `make_find_objects_impl`.
    """
    return _find_objects_impl_inner(apacheta, args, budget, param_name="matching")


def make_find_objects_impl(param_name: str = "matching"):
    """Return a `find_objects`-shaped impl that reads its filter container
    from `args[param_name]`.

    The default (`"matching"`) preserves the original behaviour; the
    parameter-name probe binds e.g. `"criteria_to_delete"` so the impl
    honours whatever key was advertised in the schema.
    """

    def _impl(
        apacheta: ApachetaInterface,
        args: dict[str, Any],
        budget: QueryBudget,
    ) -> dict[str, Any]:
        return _find_objects_impl_inner(apacheta, args, budget, param_name=param_name)

    _impl.__name__ = f"find_objects_impl__{param_name}"
    return _impl


def _find_objects_impl_inner(
    apacheta: ApachetaInterface,
    args: dict[str, Any],
    budget: QueryBudget,
    *,
    param_name: str,
) -> dict[str, Any]:
    budget.charge()

    matching: dict[str, Any] = dict(args.get(param_name) or {})
    limit = args.get("limit", 50)
    cursor = args.get("cursor")

    ignored: list[str] = []
    chosen: str | None = None
    for key in _FILTER_PRIORITY:
        if key in matching and matching[key]:
            if chosen is None:
                chosen = key
            else:
                ignored.append(key)

    if chosen == "author_instance_id":
        records = apacheta.query_open_by_author_instance(matching[chosen], limit=limit)
    elif chosen == "lineage_tag":
        records = apacheta.query_open_by_lineage_tag(matching[chosen], limit=limit)
    elif chosen == "has_field":
        records = apacheta.query_open_has_field(matching[chosen], limit=limit)
    else:
        records = apacheta.list_open_records(limit=limit)

    results = _envelope_for(records)
    return {
        "results": results,
        "total_matched": len(results),
        "next_cursor": None,
        "diversity": None,
        "cost_hint": {"queries_remaining": budget.remaining},
        "ignored_filters": ignored,
        "received_cursor": cursor,
    }
