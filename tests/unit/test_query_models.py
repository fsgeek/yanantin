"""Unit tests for query pipeline data models.

Verifies frozen semantics, extra="forbid", default values,
content filter operators, and QuerySpec construction.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from yanantin.query.models import ContentFilter, QueryResult, QuerySpec, QuerySummary


# -- ContentFilter ---------------------------------------------------------


class TestContentFilter:
    def test_frozen(self):
        f = ContentFilter(field="path", op="eq", value="test")
        with pytest.raises(Exception):
            f.field = "other"  # type: ignore[misc]

    def test_extra_forbid(self):
        with pytest.raises(Exception):
            ContentFilter(field="path", op="eq", value="x", bogus="nope")  # type: ignore[call-arg]

    def test_all_ops_accepted(self):
        ops = ["contains", "eq", "gt", "lt", "gte", "lte", "exists", "glob"]
        for op in ops:
            f = ContentFilter(field="x", op=op)
            assert f.op == op

    def test_invalid_op_rejected(self):
        with pytest.raises(Exception):
            ContentFilter(field="x", op="regex")  # type: ignore[arg-type]


# -- QuerySpec -------------------------------------------------------------


class TestQuerySpec:
    def test_frozen(self):
        spec = QuerySpec()
        with pytest.raises(Exception):
            spec.limit = 50  # type: ignore[misc]

    def test_extra_allowed(self):
        spec = QuerySpec(source="natural_language", confidence=0.8)  # type: ignore[call-arg]
        assert spec.source == "natural_language"  # type: ignore[attr-defined]

    def test_defaults(self):
        spec = QuerySpec()
        assert spec.provider_id is None
        assert spec.start is None
        assert spec.end is None
        assert spec.content_filters == ()
        assert spec.content_hash is None
        assert spec.limit == 100
        assert spec.offset == 0
        assert spec.summarize is False
        assert isinstance(spec.id, UUID)

    def test_with_filters(self):
        f = ContentFilter(field="path", op="contains", value="src")
        spec = QuerySpec(content_filters=(f,))
        assert len(spec.content_filters) == 1
        assert spec.content_filters[0].field == "path"

    def test_with_provider_and_time(self):
        pid = uuid4()
        t = datetime(2026, 2, 20, tzinfo=timezone.utc)
        spec = QuerySpec(provider_id=pid, start=t, limit=50)
        assert spec.provider_id == pid
        assert spec.start == t
        assert spec.limit == 50


# -- QuerySummary ----------------------------------------------------------


class TestQuerySummary:
    def test_frozen(self):
        s = QuerySummary(total_count=10, providers={"a": 5, "b": 5})
        with pytest.raises(Exception):
            s.total_count = 20  # type: ignore[misc]

    def test_extra_allowed(self):
        s = QuerySummary(total_count=0, providers={}, histogram={"a": 1})  # type: ignore[call-arg]
        assert s.histogram == {"a": 1}  # type: ignore[attr-defined]

    def test_defaults(self):
        s = QuerySummary(total_count=0, providers={})
        assert s.time_range is None
        assert s.top_content_hashes == {}
        assert s.sample_data_keys == ()


# -- QueryResult -----------------------------------------------------------


class TestQueryResult:
    def test_frozen(self):
        spec = QuerySpec()
        r = QueryResult(query_id=spec.id, spec=spec)
        with pytest.raises(Exception):
            r.total_matched = 99  # type: ignore[misc]

    def test_extra_allowed(self):
        spec = QuerySpec()
        r = QueryResult(query_id=spec.id, spec=spec, cache_hit=True)  # type: ignore[call-arg]
        assert r.cache_hit is True  # type: ignore[attr-defined]

    def test_defaults(self):
        spec = QuerySpec()
        r = QueryResult(query_id=spec.id, spec=spec)
        assert r.facts == ()
        assert r.summary is None
        assert r.total_matched == 0
        assert r.returned_count == 0
        assert r.execution_time_ms == 0.0
        assert r.timestamp.tzinfo is not None

    def test_with_facts(self):
        spec = QuerySpec()
        facts = ({"id": "abc", "data": {}},)
        r = QueryResult(
            query_id=spec.id,
            spec=spec,
            facts=facts,
            total_matched=1,
            returned_count=1,
        )
        assert r.returned_count == 1
        assert r.facts[0]["id"] == "abc"
