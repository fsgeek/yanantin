"""Unit tests for the query engine.

Parametrized across InMemory and DuckDB backends, following the
same fixture pattern as test_activity_store.py.

Tests verify:
- Basic execution (empty store, single provider, multiple providers)
- Content filter operators (eq, contains, glob, gt, lt, gte, lte, exists)
- Dotpath resolution for nested data
- AND logic across multiple filters
- Pagination (limit, offset)
- Summarize mode
- Content hash filtering
- Stats and list_providers
- Reflexive recording via QueryFactRecorder
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from yanantin.activity.backends.duckdb import DuckDBActivityStreamStore
from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.query.engine import QueryEngine, _resolve_dotpath
from yanantin.query.models import ContentFilter, QuerySpec
from yanantin.query.recorder import QUERY_PROVIDER_ID, QueryFactRecorder


# -- Fixtures --------------------------------------------------------------


@pytest.fixture(params=["memory", "duckdb"])
def store(request) -> ActivityStreamStore:
    if request.param == "memory":
        return InMemoryActivityStreamStore()
    elif request.param == "duckdb":
        s = DuckDBActivityStreamStore(":memory:")
        request.addfinalizer(s.close)
        return s
    raise ValueError(f"Unknown backend: {request.param}")


@pytest.fixture
def engine(store) -> QueryEngine:
    return QueryEngine(store)


@pytest.fixture
def provider_a():
    return uuid4()


@pytest.fixture
def provider_b():
    return uuid4()


@pytest.fixture
def base_time():
    return datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc)


def _make_fact(provider_id, timestamp, data=None, content_hash=""):
    return FactRecord(
        provider_id=provider_id,
        timestamp=timestamp,
        data=data or {},
        content_hash=content_hash,
    )


def _populate(store, provider_id, base_time, count=5):
    """Store several facts with distinct data for filtering tests."""
    facts = []
    for i in range(count):
        f = _make_fact(
            provider_id,
            base_time + timedelta(hours=i),
            data={
                "path": f"src/file_{i}.py",
                "size": 100 * (i + 1),
                "nested": {"level": i, "name": f"item-{i}"},
            },
            content_hash=f"hash-{i}",
        )
        store.store_fact(f)
        facts.append(f)
    return facts


# -- Basic execution -------------------------------------------------------


class TestBasicExecution:
    def test_empty_store(self, engine):
        spec = QuerySpec()
        result = engine.execute(spec)
        assert result.total_matched == 0
        assert result.returned_count == 0
        assert result.facts == ()
        assert result.execution_time_ms >= 0

    def test_single_provider(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=3)
        spec = QuerySpec(provider_id=provider_a)
        result = engine.execute(spec)
        assert result.total_matched == 3
        assert result.returned_count == 3

    def test_all_providers(self, store, engine, provider_a, provider_b, base_time):
        _populate(store, provider_a, base_time, count=3)
        _populate(store, provider_b, base_time + timedelta(hours=10), count=2)
        spec = QuerySpec()
        result = engine.execute(spec)
        assert result.total_matched == 5

    def test_time_range_filter(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        # Only hours 1-3 (3 facts: h1, h2, h3)
        spec = QuerySpec(
            provider_id=provider_a,
            start=base_time + timedelta(hours=1),
            end=base_time + timedelta(hours=3),
        )
        result = engine.execute(spec)
        assert result.total_matched == 3

    def test_query_id_in_result(self, engine):
        spec = QuerySpec()
        result = engine.execute(spec)
        assert result.query_id == spec.id

    def test_spec_in_result(self, engine):
        spec = QuerySpec(limit=42)
        result = engine.execute(spec)
        assert result.spec.limit == 42


# -- Content filters -------------------------------------------------------


class TestContentFilters:
    def test_eq(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="path", op="eq", value="src/file_2.py"),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 1
        assert result.facts[0]["data"]["path"] == "src/file_2.py"

    def test_contains(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="path", op="contains", value="file_3"),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 1

    def test_glob(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="path", op="glob", value="*.py"),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 5

    def test_gt(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        # size > 300 means items with size 400, 500
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="size", op="gt", value=300),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 2

    def test_lt(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        # size < 300 means items with size 100, 200
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="size", op="lt", value=300),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 2

    def test_gte(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="size", op="gte", value=300),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 3

    def test_lte(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="size", op="lte", value=300),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 3

    def test_exists(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=3)
        # All facts have "path"
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="path", op="exists"),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 3

    def test_exists_missing_field(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=3)
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="nonexistent", op="exists"),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 0

    def test_and_logic(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        # path contains "file" AND size > 300
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(
                ContentFilter(field="path", op="contains", value="file"),
                ContentFilter(field="size", op="gt", value=300),
            ),
        )
        result = engine.execute(spec)
        assert result.total_matched == 2

    def test_filter_on_missing_field_excludes(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=3)
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="missing", op="eq", value="anything"),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 0


# -- Dotpath resolution ----------------------------------------------------


class TestDotpathResolution:
    def test_nested_field(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="nested.level", op="eq", value=2),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 1

    def test_nested_contains(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(
            provider_id=provider_a,
            content_filters=(ContentFilter(field="nested.name", op="contains", value="item-3"),),
        )
        result = engine.execute(spec)
        assert result.total_matched == 1

    def test_resolve_missing_intermediate(self):
        data = {"a": {"b": 1}}
        assert _resolve_dotpath(data, "a.c") is not None or _resolve_dotpath(data, "a.c") is _resolve_dotpath({}, "x")
        # More directly:
        from yanantin.query.engine import _MISSING
        assert _resolve_dotpath(data, "a.c") is _MISSING

    def test_resolve_top_level(self):
        data = {"key": "value"}
        assert _resolve_dotpath(data, "key") == "value"

    def test_resolve_deep(self):
        data = {"a": {"b": {"c": 42}}}
        assert _resolve_dotpath(data, "a.b.c") == 42


# -- Content hash filter ---------------------------------------------------


class TestContentHashFilter:
    def test_content_hash_match(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(provider_id=provider_a, content_hash="hash-2")
        result = engine.execute(spec)
        assert result.total_matched == 1
        assert result.facts[0]["content_hash"] == "hash-2"

    def test_content_hash_no_match(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(provider_id=provider_a, content_hash="nonexistent")
        result = engine.execute(spec)
        assert result.total_matched == 0


# -- Pagination ------------------------------------------------------------


class TestPagination:
    def test_limit(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=10)
        spec = QuerySpec(provider_id=provider_a, limit=3)
        result = engine.execute(spec)
        assert result.total_matched == 10
        assert result.returned_count == 3

    def test_offset(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=10)
        spec = QuerySpec(provider_id=provider_a, limit=3, offset=8)
        result = engine.execute(spec)
        assert result.total_matched == 10
        assert result.returned_count == 2  # only 2 left after offset 8

    def test_offset_beyond_results(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(provider_id=provider_a, offset=100)
        result = engine.execute(spec)
        assert result.total_matched == 5
        assert result.returned_count == 0


# -- Summarize mode --------------------------------------------------------


class TestSummarize:
    def test_summary_returned(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(provider_id=provider_a, summarize=True)
        result = engine.execute(spec)
        assert result.summary is not None
        assert result.summary.total_count == 5

    def test_summary_providers(self, store, engine, provider_a, provider_b, base_time):
        _populate(store, provider_a, base_time, count=3)
        _populate(store, provider_b, base_time + timedelta(hours=10), count=2)
        spec = QuerySpec(summarize=True)
        result = engine.execute(spec)
        assert result.summary is not None
        assert len(result.summary.providers) == 2

    def test_summary_time_range(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(provider_id=provider_a, summarize=True)
        result = engine.execute(spec)
        assert result.summary.time_range is not None
        assert result.summary.time_range[0] <= result.summary.time_range[1]

    def test_summary_data_keys(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=3)
        spec = QuerySpec(provider_id=provider_a, summarize=True)
        result = engine.execute(spec)
        assert "path" in result.summary.sample_data_keys
        assert "size" in result.summary.sample_data_keys

    def test_summary_content_hashes(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        spec = QuerySpec(provider_id=provider_a, summarize=True)
        result = engine.execute(spec)
        assert len(result.summary.top_content_hashes) == 5

    def test_no_summary_by_default(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=3)
        spec = QuerySpec(provider_id=provider_a)
        result = engine.execute(spec)
        assert result.summary is None


# -- Stats and providers ---------------------------------------------------


class TestStatsAndProviders:
    def test_stats_empty(self, engine):
        stats = engine.get_stats()
        assert stats["total_facts"] == 0
        assert stats["provider_count"] == 0

    def test_stats_with_data(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=5)
        stats = engine.get_stats()
        assert stats["total_facts"] == 5
        assert stats["provider_count"] == 1

    def test_list_providers_empty(self, engine):
        assert engine.list_providers() == []

    def test_list_providers_with_data(self, store, engine, provider_a, provider_b, base_time):
        _populate(store, provider_a, base_time, count=3)
        _populate(store, provider_b, base_time + timedelta(hours=10), count=2)
        providers = engine.list_providers()
        assert len(providers) == 2
        ids = {p["provider_id"] for p in providers}
        assert str(provider_a) in ids
        assert str(provider_b) in ids


# -- Reflexive recording --------------------------------------------------


class TestReflexiveRecording:
    def test_record_query(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=3)
        spec = QuerySpec(provider_id=provider_a)
        result = engine.execute(spec)

        recorder = QueryFactRecorder(store)
        fact_id = recorder.record_query(result)

        # The fact should be retrievable
        fact = store.get_fact(fact_id)
        assert fact.provider_id == QUERY_PROVIDER_ID
        assert "execution_time_ms" in fact.data
        assert "total_matched" in fact.data
        assert fact.data["total_matched"] == 3

    def test_recorded_query_appears_in_providers(self, store, engine, provider_a, base_time):
        _populate(store, provider_a, base_time, count=3)
        spec = QuerySpec(provider_id=provider_a)
        result = engine.execute(spec)

        recorder = QueryFactRecorder(store)
        recorder.record_query(result)

        providers = store.list_providers()
        assert QUERY_PROVIDER_ID in providers

    def test_query_provider_id_deterministic(self):
        from uuid import uuid5, NAMESPACE_DNS
        expected = uuid5(NAMESPACE_DNS, "yanantin.query.service")
        assert QUERY_PROVIDER_ID == expected
