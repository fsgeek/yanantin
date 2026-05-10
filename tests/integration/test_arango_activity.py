"""Integration tests for ArangoDB activity stream backend against REAL ArangoDB.

These tests connect to a live ArangoDB server using the dedicated test
database (apacheta_test). No mocks. No fakes.

If ArangoDB is unavailable, all tests skip gracefully.

The activity store uses collections activity_facts and activity_anchors,
which don't collide with the Apacheta collections in the same database.

Connection details:
- Host: from YANANTIN_ARANGO_HOST environment variable
- Database: apacheta_test (test database, NOT production)
- Test user credentials from YANANTIN_ARANGO_USER / YANANTIN_ARANGO_PASSWORD

Design:
- Session-scoped fixture verifies test database is reachable
- Function-scoped fixture connects with least-privilege test user
- Collections truncated between tests for isolation
- Tests mirror the unit test_activity_store.py parametrized matrix
- Database and user setup handled by: uv run python -m yanantin.infra setup
"""

from __future__ import annotations

import os
import threading
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.activity.models import AnchorCursor, FactRecord, MemoryAnchor
from yanantin.apacheta.interface.errors import ImmutabilityError, NotFoundError

# Connection parameters — from .env via root conftest.py
ARANGO_HOST = os.environ.get("YANANTIN_ARANGO_HOST", "http://localhost:8529")
ARANGO_DB = os.environ.get("YANANTIN_ARANGO_DB", "apacheta_test")
ARANGO_USER = os.environ.get("YANANTIN_ARANGO_USER", "apacheta_test")
ARANGO_PASSWORD = os.environ.get("YANANTIN_ARANGO_PASSWORD", "")


def check_arango_available() -> bool:
    """Check if ArangoDB test database is reachable with test credentials."""
    try:
        from arango import ArangoClient
        client = ArangoClient(hosts=ARANGO_HOST)
        db = client.db(ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASSWORD)
        db.collections()
        client.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def arango_session():
    """Session-scoped fixture: verify test database is reachable.

    Precondition: database and user created by infra setup tool.
    Run `uv run python -m yanantin.infra setup` before running
    integration tests. This fixture only checks connectivity —
    no admin operations, no database creation, no user management.
    """
    if not check_arango_available():
        pytest.skip(
            f"ArangoDB test database not available at {ARANGO_HOST}. "
            "Run: uv run python -m yanantin.infra setup"
        )
    yield


@pytest.fixture
def store(arango_session) -> ArangoDBActivityStreamStore:
    """Function-scoped: fresh store with clean collections."""
    s = ArangoDBActivityStreamStore(
        host=ARANGO_HOST,
        db_name=ARANGO_DB,
        username=ARANGO_USER,
        password=ARANGO_PASSWORD,
    )

    # Truncate activity collections for test isolation
    for name in ("activity_facts", "activity_anchors"):
        if s._db.has_collection(name):
            s._db.collection(name).truncate()

    yield s
    s.close()


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
        assert retrieved.data["value"] == 42
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


# -- Temporal queries --------------------------------------------------


class TestQueryLatest:
    def test_returns_most_recent_before_timestamp(self, store, provider_a, base_time):
        t1 = base_time
        t2 = base_time + timedelta(hours=1)
        t3 = base_time + timedelta(hours=2)

        store.store_fact(_make_fact(provider_a, t1, value=1))
        store.store_fact(_make_fact(provider_a, t2, value=2))
        store.store_fact(_make_fact(provider_a, t3, value=3))

        result = store.query_latest(provider_a, before=t2 + timedelta(minutes=30))
        assert result is not None
        assert result.data["value"] == 2

    def test_returns_fact_at_exact_timestamp(self, store, provider_a, base_time):
        """query_latest with before=t should include facts AT t."""
        store.store_fact(_make_fact(provider_a, base_time, value=1))

        result = store.query_latest(provider_a, before=base_time)
        assert result is not None
        assert result.data["value"] == 1

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
        results = store.query_range(provider_a, start=base_time)
        assert results == []

    def test_includes_boundary_timestamps(self, store, provider_a, base_time):
        """Range query should include facts at exactly start and end."""
        t1 = base_time
        t2 = base_time + timedelta(hours=1)
        t3 = base_time + timedelta(hours=2)

        store.store_fact(_make_fact(provider_a, t1, value=1))
        store.store_fact(_make_fact(provider_a, t2, value=2))
        store.store_fact(_make_fact(provider_a, t3, value=3))

        results = store.query_range(provider_a, start=t1, end=t3)
        assert len(results) == 3

    def test_filters_by_start_and_end(self, store, provider_a, base_time):
        t1 = base_time
        t2 = base_time + timedelta(hours=1)
        t3 = base_time + timedelta(hours=2)

        store.store_fact(_make_fact(provider_a, t1, value=1))
        store.store_fact(_make_fact(provider_a, t2, value=2))
        store.store_fact(_make_fact(provider_a, t3, value=3))

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
        cursor = AnchorCursor(provider=provider_a, reference=uuid4())
        anchor = MemoryAnchor(
            handle=uuid4(), timestamp=base_time, cursors=(cursor,),
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
    """Facts stored with different source timezones should all normalize to UTC."""

    def test_mixed_timezone_facts_sort_correctly(self, store, provider_a):
        """Facts from different timezones should sort by actual instant."""
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

    def test_stored_timestamp_is_utc(self, store, provider_a):
        """Retrieved timestamps should always be UTC."""
        eastern = timezone(timedelta(hours=-5))
        t_eastern = datetime(2025, 6, 1, 12, 0, 0, tzinfo=eastern)

        fact = _make_fact(provider_a, t_eastern, value=1)
        store.store_fact(fact)

        retrieved = store.get_fact(fact.id)
        assert retrieved.timestamp.tzinfo == timezone.utc
        assert retrieved.timestamp.hour == 17  # 12 Eastern = 17 UTC


# -- Index-driven query performance ------------------------------------


class TestIndexDrivenQueries:
    """Verify the persistent sorted index is being used.

    These are functional tests — they verify correct results, not EXPLAIN
    plans. The index assertion is structural: we verify the index exists.
    """

    def test_persistent_index_exists_on_facts(self, store):
        """The activity_facts collection must have a persistent index
        on (provider_id, timestamp) for O(log n) temporal queries."""
        col = store._db.collection("activity_facts")
        indexes = col.indexes()
        field_sets = [tuple(idx["fields"]) for idx in indexes if idx["type"] == "persistent"]
        assert ("provider_id", "timestamp") in field_sets

    def test_persistent_index_exists_on_anchors(self, store):
        """The activity_anchors collection must have a persistent index
        on (timestamp) for latest-anchor queries."""
        col = store._db.collection("activity_anchors")
        indexes = col.indexes()
        field_sets = [tuple(idx["fields"]) for idx in indexes if idx["type"] == "persistent"]
        assert ("timestamp",) in field_sets

    def test_query_latest_with_many_facts(self, store, provider_a, base_time):
        """Store 100 facts, query latest before a midpoint."""
        for i in range(100):
            store.store_fact(_make_fact(
                provider_a,
                base_time + timedelta(minutes=i),
                value=i,
            ))

        midpoint = base_time + timedelta(minutes=50)
        result = store.query_latest(provider_a, before=midpoint)
        assert result is not None
        assert result.data["value"] == 50  # inclusive

    def test_query_range_with_many_facts(self, store, provider_a, base_time):
        """Store 100 facts, query a narrow range."""
        for i in range(100):
            store.store_fact(_make_fact(
                provider_a,
                base_time + timedelta(minutes=i),
                value=i,
            ))

        start = base_time + timedelta(minutes=25)
        end = base_time + timedelta(minutes=35)
        results = store.query_range(provider_a, start=start, end=end)
        assert len(results) == 11  # 25 through 35 inclusive
        assert results[0].data["value"] == 25
        assert results[-1].data["value"] == 35


# -- Thread safety -----------------------------------------------------


class TestThreadSafety:
    def test_concurrent_fact_writes(self, store, provider_a, base_time):
        """Multiple threads storing different facts should not collide."""
        results = {}

        def write_fact(thread_id):
            fact = _make_fact(
                provider_a,
                base_time + timedelta(seconds=thread_id),
                value=thread_id,
            )
            store.store_fact(fact)
            results[thread_id] = fact.id

        threads = [
            threading.Thread(target=write_fact, args=(i,))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert all(not t.is_alive() for t in threads)
        assert len(results) == 10
        assert store.count_facts(provider_a) == 10

    def test_concurrent_reads(self, store, provider_a, base_time):
        """Multiple threads reading the same fact should all succeed."""
        fact = _make_fact(provider_a, base_time, value=42)
        store.store_fact(fact)

        results = {}

        def read_fact(thread_id):
            retrieved = store.get_fact(fact.id)
            results[thread_id] = retrieved.data["value"]

        threads = [
            threading.Thread(target=read_fact, args=(i,))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert all(not t.is_alive() for t in threads)
        assert all(v == 42 for v in results.values())


# -- Context manager ---------------------------------------------------


class TestContextManager:
    def test_context_manager_usage(self, arango_session):
        with ArangoDBActivityStreamStore(
            host=ARANGO_HOST,
            db_name=ARANGO_DB,
            username=ARANGO_USER,
            password=ARANGO_PASSWORD,
        ) as s:
            provider = uuid4()
            t = datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
            fact = _make_fact(provider, t, value=99)
            s.store_fact(fact)
            assert s.count_facts(provider) == 1


# -- Behavioral equivalence with InMemory -----------------------------


class TestBehavioralEquivalence:
    """Verify ArangoDB backend matches InMemory backend behavior."""

    def test_query_latest_inclusive_boundary(self, store, provider_a, base_time):
        """query_latest(before=t) should include facts at exactly t.

        This was a bug in the InMemory backend (bisect tuple prefix
        comparison). Verify ArangoDB handles it correctly with <= in AQL.
        """
        store.store_fact(_make_fact(provider_a, base_time, value=1))

        result = store.query_latest(provider_a, before=base_time)
        assert result is not None
        assert result.data["value"] == 1

    def test_query_range_inclusive_boundaries(self, store, provider_a, base_time):
        """query_range should include facts at exactly start and end."""
        t1 = base_time
        t2 = base_time + timedelta(hours=2)

        store.store_fact(_make_fact(provider_a, t1, value=1))
        store.store_fact(_make_fact(provider_a, t2, value=2))

        results = store.query_range(provider_a, start=t1, end=t2)
        assert len(results) == 2

    def test_anchor_roundtrip_preserves_cursors(self, store, base_time):
        """Anchors with multiple cursors should survive serialization."""
        p1, p2 = uuid4(), uuid4()
        cursors = (
            AnchorCursor(provider=p1, reference=uuid4(), data="ref-1"),
            AnchorCursor(
                provider=p2,
                reference=uuid4(),
                attributes={"key": "value"},
            ),
        )
        anchor = MemoryAnchor(
            handle=uuid4(), timestamp=base_time, cursors=cursors,
        )
        store.store_anchor(anchor)

        retrieved = store.get_anchor(anchor.handle)
        assert len(retrieved.cursors) == 2
        cursor_providers = {c.provider for c in retrieved.cursors}
        assert cursor_providers == {p1, p2}

        # Verify optional fields survived
        c1 = next(c for c in retrieved.cursors if c.provider == p1)
        c2 = next(c for c in retrieved.cursors if c.provider == p2)
        assert c1.data == "ref-1"
        assert c2.attributes == {"key": "value"}

    def test_fact_extra_fields_preserved(self, store, provider_a, base_time):
        """FactRecord uses extra='allow' — extra fields should survive roundtrip."""
        fact = FactRecord(
            provider_id=provider_a,
            timestamp=base_time,
            data={"value": 1},
            custom_field="extra-data",
        )
        store.store_fact(fact)

        retrieved = store.get_fact(fact.id)
        assert retrieved.custom_field == "extra-data"
