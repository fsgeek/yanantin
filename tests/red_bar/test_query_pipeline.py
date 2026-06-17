"""Red-bar tests for the query pipeline.

Structural invariants, not functional tests. These enforce
architectural decisions that should never regress.
"""

from __future__ import annotations

import ast
import inspect
from uuid import NAMESPACE_DNS, uuid5

from yanantin.query.models import ContentFilter, QueryResult, QuerySpec, QuerySummary
from yanantin.query.recorder import QUERY_PROVIDER_ID, QueryFactRecorder


class TestFrozenModels:
    """All query models must be frozen."""

    def test_content_filter_frozen(self):
        assert ContentFilter.model_config.get("frozen") is True

    def test_query_spec_frozen(self):
        assert QuerySpec.model_config.get("frozen") is True

    def test_query_summary_frozen(self):
        assert QuerySummary.model_config.get("frozen") is True

    def test_query_result_frozen(self):
        assert QueryResult.model_config.get("frozen") is True


class TestSchemaPolicy:
    """ContentFilter is strict. Everything else allows extension."""

    def test_content_filter_forbids_extra(self):
        assert ContentFilter.model_config.get("extra") == "forbid"

    def test_query_spec_allows_extra(self):
        assert QuerySpec.model_config.get("extra") == "allow"

    def test_query_summary_allows_extra(self):
        assert QuerySummary.model_config.get("extra") == "allow"

    def test_query_result_allows_extra(self):
        assert QueryResult.model_config.get("extra") == "allow"


class TestEngineContainsNoDatabaseLanguage:
    """Engine must not contain SQL or AQL — filtering is Python-side."""

    def test_no_sql_or_aql_in_engine(self):
        import yanantin.query.engine as engine_mod

        source = inspect.getsource(engine_mod)
        tree = ast.parse(source)

        # Walk string literals looking for SQL/AQL keywords
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value.upper()
                assert "SELECT " not in val, f"SQL found in engine: {node.value!r}"
                assert "FOR " not in val or "RETURN" not in val, (
                    f"AQL found in engine: {node.value!r}"
                )


class TestRecorderIsNotFactRecorderBase:
    """QueryFactRecorder must NOT subclass FactRecorderBase."""

    def test_not_a_fact_recorder_base(self):
        from yanantin.recorder.base import FactRecorderBase

        assert not issubclass(QueryFactRecorder, FactRecorderBase)


class TestQueryProviderIdDeterministic:
    """QUERY_PROVIDER_ID must always be the same value."""

    def test_deterministic(self):
        expected = uuid5(NAMESPACE_DNS, "yanantin.query.service")
        assert QUERY_PROVIDER_ID == expected

    def test_not_random(self):
        # Import twice — must be identical
        from yanantin.query.recorder import QUERY_PROVIDER_ID as pid2

        assert QUERY_PROVIDER_ID == pid2


class TestQueryFactDataContainsExecutionTime:
    """Recorded query facts must contain execution_time_ms."""

    def test_execution_time_in_fact_data(self):
        from yanantin.activity.backends.memory import InMemoryActivityStreamStore
        from yanantin.query.engine import QueryEngine
        from yanantin.query.models import QuerySpec

        store = InMemoryActivityStreamStore()
        engine = QueryEngine(store)
        result = engine.execute(QuerySpec())

        recorder = QueryFactRecorder(store)
        fact_id = recorder.record_query(result)

        fact = store.get_fact(fact_id)
        assert "execution_time_ms" in fact.data
