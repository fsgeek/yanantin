"""Unit tests for the activity stream store.

Tests are parametrized across InMemory and DuckDB backends. ArangoDB
tests require a live database and live in tests/integration/.

Tests verify:
- Fact store and retrieve
- Immutability enforcement on duplicate UUID
- Temporal query: latest fact before timestamp
- Temporal query: range query sorted ascending
- Anchor store and retrieve
- Latest anchor query
- Provider discovery
- Fact count with and without provider filter
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from yanantin.activity.models import AnchorCursor, FactRecord, MemoryAnchor
from yanantin.activity.store import ActivityStreamStore
from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.activity.backends.duckdb import DuckDBActivityStreamStore
from yanantin.apacheta.interface.errors import ImmutabilityError, NotFoundError


# -- Fixtures ----------------------------------------------------------

@pytest.fixture(params=["memory", "duckdb"])
def store(request) -> ActivityStreamStore:
    """Parametrized fixture: runs every test against both backends."""
    if request.param == "memory":
        return InMemoryActivityStreamStore()
    elif request.param == "duckdb":
        s = DuckDBActivityStreamStore(":memory:")
        request.addfinalizer(s.close)
        return s
    raise ValueError(f"Unknown backend: {request.param}")


@pytest.fixture
def provider_a() -> UUID:
    return uuid4()


@pytest.fixture
def provider_b() -> UUID:
    return uuid4()


@pytest.fixture
def base_time() -> datetime:
    return datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_fact(
    provider_id: UUID,
    timestamp: datetime,
    value: int = 0,
    fact_id: UUID | None = None,
) -> FactRecord:
    return FactRecord(
        id=fact_id or uuid4(),
        provider_id=provider_id,
        timestamp=timestamp,
        data={"value": value},
        content_hash=f"hash-{value}",
    )


# -- Fact operations ---------------------------------------------------

class TestStoreFact:
    def test_store_fact_and_retrieve(self, store, provider_a, base_time):
        fact = _make_fact(provider_a, base_time, value=42)
        store.store_fact(fact)

        retrieved = store.get_fact(fact.id)
        assert retrieved.id == fact.id
        assert retrieved.provider_id == provider_a
        assert retrieved.data == {"value": 42}
        assert retrieved.content_hash == "hash-42"

    def test_store_fact_immutability_error_on_duplicate(self, store, provider_a, base_time):
        fact_id = uuid4()
        fact = _make_fact(provider_a, base_time, value=1, fact_id=fact_id)
        store.store_fact(fact)

        duplicate = _make_fact(provider_a, base_time, value=2, fact_id=fact_id)
        with pytest.raises(ImmutabilityError):
            store.store_fact(duplicate)

    def test_get_fact_not_found(self, store):
        with pytest.raises(NotFoundError):
            store.get_fact(uuid4())


class TestQueryLatest:
    def test_returns_most_recent_before_timestamp(self, store, provider_a, base_time):
        t1 = base_time
        t2 = base_time + timedelta(hours=1)
        t3 = base_time + timedelta(hours=2)

        store.store_fact(_make_fact(provider_a, t1, value=1))
        store.store_fact(_make_fact(provider_a, t2, value=2))
        store.store_fact(_make_fact(provider_a, t3, value=3))

        # Query before t3 — should get t2's fact
        result = store.query_latest(provider_a, before=t2 + timedelta(minutes=30))
        assert result is not None
        assert result.data["value"] == 2

    def test_returns_none_when_no_facts(self, store, provider_a, base_time):
        result = store.query_latest(provider_a, before=base_time)
        assert result is None

    def test_returns_none_when_all_facts_after_timestamp(self, store, provider_a, base_time):
        future = base_time + timedelta(hours=1)
        store.store_fact(_make_fact(provider_a, future, value=1))

        result = store.query_latest(provider_a, before=base_time)
        assert result is None

    def test_returns_latest_overall_when_no_before(self, store, provider_a, base_time):
        t1 = base_time
        t2 = base_time + timedelta(hours=1)

        store.store_fact(_make_fact(provider_a, t1, value=1))
        store.store_fact(_make_fact(provider_a, t2, value=2))

        result = store.query_latest(provider_a)
        assert result is not None
        assert result.data["value"] == 2


class TestQueryRange:
    def test_returns_sorted_facts(self, store, provider_a, base_time):
        t1 = base_time
        t2 = base_time + timedelta(hours=1)
        t3 = base_time + timedelta(hours=2)

        # Store out of order
        store.store_fact(_make_fact(provider_a, t3, value=3))
        store.store_fact(_make_fact(provider_a, t1, value=1))
        store.store_fact(_make_fact(provider_a, t2, value=2))

        results = store.query_range(provider_a, start=t1, end=t3)
        assert len(results) == 3
        assert [r.data["value"] for r in results] == [1, 2, 3]

    def test_returns_empty_when_no_match(self, store, provider_a, base_time):
        # No facts stored for this provider
        results = store.query_range(provider_a, start=base_time)
        assert results == []

    def test_filters_by_start_and_end(self, store, provider_a, base_time):
        t1 = base_time
        t2 = base_time + timedelta(hours=1)
        t3 = base_time + timedelta(hours=2)

        store.store_fact(_make_fact(provider_a, t1, value=1))
        store.store_fact(_make_fact(provider_a, t2, value=2))
        store.store_fact(_make_fact(provider_a, t3, value=3))

        # Only t2
        results = store.query_range(
            provider_a,
            start=t1 + timedelta(minutes=30),
            end=t2 + timedelta(minutes=30),
        )
        assert len(results) == 1
        assert results[0].data["value"] == 2


# -- Anchor operations -------------------------------------------------

class TestStoreAnchor:
    def test_store_anchor_and_retrieve(self, store, provider_a, base_time):
        cursor = AnchorCursor(
            provider=provider_a,
            reference=uuid4(),
        )
        anchor = MemoryAnchor(
            handle=uuid4(),
            timestamp=base_time,
            cursors=(cursor,),
        )
        store.store_anchor(anchor)

        retrieved = store.get_anchor(anchor.handle)
        assert retrieved.handle == anchor.handle
        assert len(retrieved.cursors) == 1
        assert retrieved.cursors[0].provider == provider_a

    def test_store_anchor_immutability_error_on_duplicate(self, store, base_time):
        handle = uuid4()
        anchor = MemoryAnchor(handle=handle, timestamp=base_time, cursors=())
        store.store_anchor(anchor)

        duplicate = MemoryAnchor(handle=handle, timestamp=base_time, cursors=())
        with pytest.raises(ImmutabilityError):
            store.store_anchor(duplicate)

    def test_get_anchor_not_found(self, store):
        with pytest.raises(NotFoundError):
            store.get_anchor(uuid4())


class TestGetLatestAnchor:
    def test_returns_most_recent(self, store, base_time):
        t1 = base_time
        t2 = base_time + timedelta(hours=1)

        store.store_anchor(MemoryAnchor(handle=uuid4(), timestamp=t1, cursors=()))
        handle2 = uuid4()
        store.store_anchor(MemoryAnchor(handle=handle2, timestamp=t2, cursors=()))

        latest = store.get_latest_anchor()
        assert latest is not None
        assert latest.handle == handle2

    def test_returns_none_when_empty(self, store):
        assert store.get_latest_anchor() is None


# -- Discovery ---------------------------------------------------------

class TestDiscovery:
    def test_list_providers_discovers_all(self, store, provider_a, provider_b, base_time):
        store.store_fact(_make_fact(provider_a, base_time, value=1))
        store.store_fact(_make_fact(provider_b, base_time, value=2))

        providers = store.list_providers()
        assert set(providers) == {provider_a, provider_b}

    def test_count_facts_total(self, store, provider_a, provider_b, base_time):
        store.store_fact(_make_fact(provider_a, base_time, value=1))
        store.store_fact(_make_fact(provider_a, base_time + timedelta(hours=1), value=2))
        store.store_fact(_make_fact(provider_b, base_time, value=3))

        assert store.count_facts() == 3

    def test_count_facts_by_provider(self, store, provider_a, provider_b, base_time):
        store.store_fact(_make_fact(provider_a, base_time, value=1))
        store.store_fact(_make_fact(provider_a, base_time + timedelta(hours=1), value=2))
        store.store_fact(_make_fact(provider_b, base_time, value=3))

        assert store.count_facts(provider_a) == 2
        assert store.count_facts(provider_b) == 1

    def test_count_facts_empty(self, store, provider_a):
        assert store.count_facts() == 0
        assert store.count_facts(provider_a) == 0


# -- UTC enforcement ---------------------------------------------------

class TestUTCEnforcement:
    """Verify that the model layer normalizes timestamps to UTC.

    ISO 8601 strings only sort correctly when the timezone offset is
    uniform. The _ensure_utc() validator rejects naive datetimes and
    converts non-UTC aware datetimes to UTC.
    """

    def test_naive_datetime_rejected_in_fact(self, provider_a):
        """FactRecord should reject naive datetimes."""
        naive = datetime(2025, 6, 1, 12, 0, 0)  # no tzinfo
        with pytest.raises(ValueError, match="Naive datetime"):
            FactRecord(
                provider_id=provider_a,
                timestamp=naive,
                data={"value": 1},
            )

    def test_naive_datetime_rejected_in_anchor(self):
        """MemoryAnchor should reject naive datetimes."""
        naive = datetime(2025, 6, 1, 12, 0, 0)
        with pytest.raises(ValueError, match="Naive datetime"):
            MemoryAnchor(handle=uuid4(), timestamp=naive, cursors=())

    def test_non_utc_converted_in_fact(self, provider_a):
        """FactRecord should convert non-UTC aware datetimes to UTC."""
        # US Eastern = UTC-5
        eastern = timezone(timedelta(hours=-5))
        t_eastern = datetime(2025, 6, 1, 12, 0, 0, tzinfo=eastern)

        fact = FactRecord(
            provider_id=provider_a,
            timestamp=t_eastern,
            data={"value": 1},
        )
        # Should be stored as UTC (17:00)
        assert fact.timestamp.tzinfo == timezone.utc
        assert fact.timestamp.hour == 17

    def test_non_utc_converted_in_anchor(self):
        """MemoryAnchor should convert non-UTC aware datetimes to UTC."""
        eastern = timezone(timedelta(hours=-5))
        t_eastern = datetime(2025, 6, 1, 12, 0, 0, tzinfo=eastern)

        anchor = MemoryAnchor(
            handle=uuid4(), timestamp=t_eastern, cursors=(),
        )
        assert anchor.timestamp.tzinfo == timezone.utc
        assert anchor.timestamp.hour == 17

    def test_utc_passthrough(self, provider_a):
        """UTC datetimes should pass through unchanged."""
        t_utc = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

        fact = FactRecord(
            provider_id=provider_a,
            timestamp=t_utc,
            data={"value": 1},
        )
        assert fact.timestamp == t_utc
        assert fact.timestamp.hour == 12

    def test_mixed_timezone_facts_sort_correctly(self, store, provider_a):
        """Facts created with different timezones should sort by actual instant."""
        eastern = timezone(timedelta(hours=-5))
        utc = timezone.utc

        # 12:00 Eastern = 17:00 UTC (later)
        t_eastern = datetime(2025, 6, 1, 12, 0, 0, tzinfo=eastern)
        # 14:00 UTC (earlier)
        t_utc = datetime(2025, 6, 1, 14, 0, 0, tzinfo=utc)

        store.store_fact(_make_fact(provider_a, t_eastern, value=1))
        store.store_fact(_make_fact(provider_a, t_utc, value=2))

        results = store.query_range(provider_a)
        assert len(results) == 2
        # 14:00 UTC comes before 17:00 UTC
        assert results[0].data["value"] == 2
        assert results[1].data["value"] == 1
