"""Query engine — executes QuerySpec against any ActivityStreamStore.

All content filtering happens in Python. The store interface is the
boundary; AQL/SQL pushdown is a future optimization. The engine
fetches via query_range (per provider or all), applies content
filters (AND logic), paginates or summarizes.
"""

from __future__ import annotations

import fnmatch
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.query.models import ContentFilter, QueryResult, QuerySpec, QuerySummary


def _resolve_dotpath(data: dict, path: str) -> Any:
    """Resolve a dot-separated path into nested dict values.

    Returns _MISSING sentinel if any key along the path is absent.
    """
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return _MISSING
        current = current[key]
    return current


_MISSING = object()


def _apply_filter(data: dict, filt: ContentFilter) -> bool:
    """Apply a single content filter to a fact's data dict."""
    resolved = _resolve_dotpath(data, filt.field)

    if filt.op == "exists":
        return resolved is not _MISSING

    if resolved is _MISSING:
        return False

    if filt.op == "eq":
        return resolved == filt.value
    if filt.op == "contains":
        return filt.value in str(resolved)
    if filt.op == "glob":
        return fnmatch.fnmatch(str(resolved), str(filt.value))
    if filt.op == "gt":
        return resolved > filt.value
    if filt.op == "lt":
        return resolved < filt.value
    if filt.op == "gte":
        return resolved >= filt.value
    if filt.op == "lte":
        return resolved <= filt.value

    return False


def _fact_to_dict(fact: FactRecord) -> dict:
    """Convert a FactRecord to a serializable dict."""
    return {
        "id": str(fact.id),
        "provider_id": str(fact.provider_id),
        "timestamp": fact.timestamp.isoformat(),
        "data": fact.data,
        "content_hash": fact.content_hash,
    }


class QueryEngine:
    """Executes structured queries against an ActivityStreamStore."""

    def __init__(self, store: ActivityStreamStore) -> None:
        self._store = store

    def execute(self, spec: QuerySpec) -> QueryResult:
        """Execute a QuerySpec and return results with provenance."""
        start_time = time.monotonic()

        # Fetch facts from the store
        raw_facts = self._fetch_facts(spec)

        # Apply content filters (AND logic)
        filtered = self._apply_content_filters(raw_facts, spec)

        # Apply content_hash filter
        if spec.content_hash is not None:
            filtered = [f for f in filtered if f.content_hash == spec.content_hash]

        total_matched = len(filtered)

        # Build summary if requested
        summary = self._build_summary(filtered) if spec.summarize else None

        # Paginate
        page = filtered[spec.offset : spec.offset + spec.limit]
        fact_dicts = tuple(_fact_to_dict(f) for f in page)

        elapsed_ms = (time.monotonic() - start_time) * 1000

        return QueryResult(
            query_id=spec.id,
            spec=spec,
            facts=fact_dicts,
            summary=summary,
            total_matched=total_matched,
            returned_count=len(fact_dicts),
            execution_time_ms=round(elapsed_ms, 2),
        )

    def get_stats(self) -> dict:
        """Total and per-provider fact counts."""
        providers = self._store.list_providers()
        total = self._store.count_facts()
        per_provider = {
            str(p): self._store.count_facts(p) for p in providers
        }
        return {
            "total_facts": total,
            "provider_count": len(providers),
            "providers": per_provider,
        }

    def list_providers(self) -> list[dict]:
        """Provider UUIDs with fact counts."""
        providers = self._store.list_providers()
        return [
            {"provider_id": str(p), "fact_count": self._store.count_facts(p)}
            for p in providers
        ]

    def _fetch_facts(self, spec: QuerySpec) -> list[FactRecord]:
        """Fetch facts from the store, across one or all providers."""
        if spec.provider_id is not None:
            return self._store.query_range(
                spec.provider_id, start=spec.start, end=spec.end,
            )

        # No provider specified — query all providers
        all_facts: list[FactRecord] = []
        for provider_id in self._store.list_providers():
            all_facts.extend(
                self._store.query_range(provider_id, start=spec.start, end=spec.end)
            )
        # Sort by timestamp ascending (each provider's results are sorted,
        # but the merge is not)
        all_facts.sort(key=lambda f: f.timestamp)
        return all_facts

    def _apply_content_filters(
        self, facts: list[FactRecord], spec: QuerySpec,
    ) -> list[FactRecord]:
        """Apply all content filters with AND logic."""
        if not spec.content_filters:
            return facts
        return [
            f for f in facts
            if all(_apply_filter(f.data, filt) for filt in spec.content_filters)
        ]

    def _build_summary(self, facts: list[FactRecord]) -> QuerySummary:
        """Build an aggregate summary of matched facts."""
        provider_counts: Counter[str] = Counter()
        hash_counts: Counter[str] = Counter()
        all_keys: set[str] = set()
        timestamps: list[datetime] = []

        for f in facts:
            provider_counts[str(f.provider_id)] += 1
            if f.content_hash:
                hash_counts[f.content_hash] += 1
            all_keys.update(f.data.keys())
            timestamps.append(f.timestamp)

        time_range = None
        if timestamps:
            time_range = (min(timestamps), max(timestamps))

        # Top 10 content hashes
        top_hashes = dict(hash_counts.most_common(10))

        return QuerySummary(
            total_count=len(facts),
            providers=dict(provider_counts),
            time_range=time_range,
            top_content_hashes=top_hashes,
            sample_data_keys=tuple(sorted(all_keys)),
        )
