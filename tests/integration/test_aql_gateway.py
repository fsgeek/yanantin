"""Live tests for the AQL gateway (yanantin.core.aql) against apacheta_test.

No mocks: the observation's counts come from ArangoDB's own statistics, so
only a real server can say whether they are right.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

ARANGO_HOST = os.environ.get("YANANTIN_ARANGO_HOST", "http://localhost:8529")
ARANGO_DB = os.environ.get("YANANTIN_ARANGO_DB", "apacheta_test")
ARANGO_USER = os.environ.get("YANANTIN_ARANGO_USER", "apacheta_test")
ARANGO_PASSWORD = os.environ.get("YANANTIN_ARANGO_PASSWORD", "")

N = 40


@pytest.fixture
def db():
    from arango import ArangoClient

    try:
        handle = ArangoClient(hosts=ARANGO_HOST).db(
            ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASSWORD)
        handle.version()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"ArangoDB test database not available: {e}")
    return handle


@pytest.fixture
def coll(db):
    name = f"aql_gateway_{uuid4().hex[:8]}"
    c = db.create_collection(name)
    c.add_persistent_index(fields=["k"])
    c.insert_many([{"_key": str(i), "k": i, "secret": f"s{i}"} for i in range(N)])
    yield name
    db.delete_collection(name)


@pytest.fixture
def seen():
    from yanantin.core import aql

    got = []
    stop = aql.observe(got.append)
    yield got
    stop()


def test_rows_stream_unchanged_across_batches(db, coll, seen):
    from yanantin.core import aql

    q = "FOR d IN @@c SORT d.k RETURN d.k"
    rows = list(aql.run(db, q, bind_vars={"@c": coll}, batch_size=3))
    assert rows == list(range(N))


def test_one_observation_on_exhaustion(db, coll, seen):
    from yanantin.core import aql

    cur = aql.run(db, "FOR d IN @@c RETURN d", bind_vars={"@c": coll}, batch_size=7)
    next(iter(cur))
    assert seen == []  # not yet exhausted
    rest = list(cur)
    assert len(rest) == N - 1
    [obs] = seen
    assert obs.returned == N and obs.exhausted
    assert obs.database == ARANGO_DB
    assert obs.collections == (coll,)
    assert obs.scanned_full == N and obs.scanned_index == 0
    list(cur)  # iterating an exhausted cursor again records nothing new
    assert len(seen) == 1


def test_index_scan_and_filter_counts(db, coll, seen):
    from yanantin.core import aql

    rows = list(aql.run(
        db, "FOR d IN @@c FILTER d.k >= @lo FILTER d.secret != @x RETURN d.k",
        bind_vars={"@c": coll, "lo": 30, "x": "s35"}))
    assert sorted(rows) == [k for k in range(30, N) if k != 35]
    [obs] = seen
    assert obs.scanned_full == 0 and obs.scanned_index == N - 30
    assert obs.filtered == 1
    assert obs.returned == N - 31


def test_bind_values_are_not_recorded(db, coll, seen):
    from yanantin.core import aql

    list(aql.run(db, "FOR d IN @@c FILTER d.secret == @needle RETURN d",
                 bind_vars={"@c": coll, "needle": "s17"}))
    [obs] = seen
    assert obs.bind_names == ("needle",)
    assert "s17" not in obs.model_dump_json()


def test_statistics_and_full_count_pass_through(db, coll, seen):
    from yanantin.core import aql

    cur = aql.run(db, "FOR d IN @@c LIMIT 5 RETURN d", bind_vars={"@c": coll}, full_count=True)
    assert len(list(cur)) == 5
    assert cur.statistics()["fullCount"] == N
    assert seen[0].full_count == N


def test_closed_early_is_recorded_not_exhausted(db, coll, seen):
    from yanantin.core import aql

    cur = aql.run(db, "FOR d IN @@c RETURN d", bind_vars={"@c": coll}, batch_size=5)
    next(cur)
    cur.close()
    [obs] = seen
    assert obs.returned == 1 and not obs.exhausted


def test_a_failing_observer_does_not_break_the_query(db, coll, seen):
    from yanantin.core import aql

    def broken(_obs):
        raise RuntimeError("sink down")

    stop = aql.observe(broken)
    try:
        assert len(list(aql.run(db, "FOR d IN @@c RETURN 1", bind_vars={"@c": coll}))) == N
    finally:
        stop()
    assert len(seen) == 1  # the other observer still heard it


def test_unsubscribed_observer_hears_nothing(db, coll):
    from yanantin.core import aql

    got = []
    aql.observe(got.append)()
    list(aql.run(db, "FOR d IN @@c RETURN 1", bind_vars={"@c": coll}))
    assert got == []


def test_recorder_writes_observations_as_facts(db, coll):
    from yanantin.activity.backends.memory import InMemoryActivityStreamStore
    from yanantin.core import aql

    store = InMemoryActivityStreamStore()
    stop = aql.observe(aql.ActivityStreamRecorder(store))
    try:
        list(aql.run(db, "FOR d IN @@c RETURN 1", bind_vars={"@c": coll}))
    finally:
        stop()
    [fact] = store.query_range(aql.AQL_PROVIDER_ID)
    assert fact.data["returned"] == N
    assert fact.data["collections"] == [coll]
    assert fact.timestamp.tzinfo is not None
