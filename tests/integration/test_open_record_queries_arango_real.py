"""Acceptance tests: open-record query methods on ArangoDBBackend (real ArangoDB).

These tests are guarded by:
- `APACHETA_SKIP_ARANGO` env var (explicit opt-out)
- live ArangoDB availability check (skips if unreachable)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.provenance import ProvenanceEnvelope


ARANGO_HOST = os.environ.get("YANANTIN_ARANGO_HOST", "http://localhost:8529")
ARANGO_DB = os.environ.get("YANANTIN_ARANGO_DB", "apacheta_test")
ARANGO_USER = os.environ.get("YANANTIN_ARANGO_USER", "apacheta_test")
ARANGO_PASSWORD = os.environ.get("YANANTIN_ARANGO_PASSWORD", "")


def check_arango_available() -> bool:
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
    if os.environ.get("APACHETA_SKIP_ARANGO"):
        pytest.skip("APACHETA_SKIP_ARANGO is set")
    if not check_arango_available():
        pytest.skip(
            f"ArangoDB test database not available at {ARANGO_HOST}. "
            "Run: uv run python -m yanantin.infra setup"
        )
    yield


@pytest.fixture
def backend(arango_session):
    db = ArangoDBBackend(
        host=ARANGO_HOST,
        db_name=ARANGO_DB,
        username=ARANGO_USER,
        password=ARANGO_PASSWORD,
    )

    for collection_name in (
        "tensors",
        "composition_edges",
        "corrections",
        "dissents",
        "negations",
        "bootstraps",
        "evolutions",
        "entities",
        "records",
    ):
        db._db.collection(collection_name).truncate()

    yield db
    db.close()


def _make_record(session_id: str, tags: tuple[str, ...], *, ts: datetime, **extras) -> ApachetaBaseModel:
    prov = ProvenanceEnvelope(
        author_model_family="haiku",
        author_instance_id=session_id,
        predecessors_in_scope=(),
        timestamp=ts,
    )
    return ApachetaBaseModel(provenance=prov, lineage_tags=tags, **extras)


def test_list_open_records_returns_all(backend):
    id_with, id_without = uuid4(), uuid4()
    backend.store_record(
        id_with,
        _make_record("s1", ("hamutay",), ts=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)),
    )
    backend.store_record(id_without, ApachetaBaseModel(lineage_tags=()))
    results = backend.list_open_records()
    assert {rid for (rid, _) in results} == {id_with, id_without}


def test_list_open_records_respects_limit(backend):
    for i in range(5):
        backend.store_record(
            uuid4(),
            _make_record(
                "s1",
                (),
                ts=datetime(2026, 4, 19, 12, i, tzinfo=timezone.utc),
            ),
        )
    assert len(backend.list_open_records(limit=2)) == 2


def test_query_open_by_author_instance_filters(backend):
    id_s1_a, id_s1_b, id_s2 = uuid4(), uuid4(), uuid4()
    backend.store_record(
        id_s1_a,
        _make_record("s1", (), ts=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)),
    )
    backend.store_record(
        id_s1_b,
        _make_record("s1", (), ts=datetime(2026, 4, 19, 12, 1, tzinfo=timezone.utc)),
    )
    backend.store_record(
        id_s2,
        _make_record("s2", (), ts=datetime(2026, 4, 19, 12, 2, tzinfo=timezone.utc)),
    )
    results = backend.query_open_by_author_instance("s1")
    assert {rid for (rid, _) in results} == {id_s1_a, id_s1_b}


def test_query_open_by_author_instance_skips_records_without_provenance(backend):
    id_with, id_without = uuid4(), uuid4()
    backend.store_record(
        id_with,
        _make_record("s1", (), ts=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)),
    )
    backend.store_record(id_without, ApachetaBaseModel(lineage_tags=()))
    results = backend.query_open_by_author_instance("s1")
    assert {rid for (rid, _) in results} == {id_with}


def test_query_open_by_lineage_tag(backend):
    id_a, id_b = uuid4(), uuid4()
    backend.store_record(
        id_a,
        _make_record("s1", ("hamutay", "cycle-5"), ts=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)),
    )
    backend.store_record(
        id_b,
        _make_record("s1", ("hamutay", "cycle-6"), ts=datetime(2026, 4, 19, 12, 1, tzinfo=timezone.utc)),
    )
    results = backend.query_open_by_lineage_tag("cycle-5")
    assert {rid for (rid, _) in results} == {id_a}


def test_query_open_has_field(backend):
    id_a, id_b = uuid4(), uuid4()
    backend.store_record(
        id_a,
        _make_record("s1", (), ts=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc), theme="opening"),
    )
    backend.store_record(
        id_b,
        _make_record("s1", (), ts=datetime(2026, 4, 19, 12, 1, tzinfo=timezone.utc)),
    )
    results = backend.query_open_has_field("theme")
    assert {rid for (rid, _) in results} == {id_a}


def test_list_author_instances_distinct(backend):
    backend.store_record(
        uuid4(),
        _make_record("s1", (), ts=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)),
    )
    backend.store_record(
        uuid4(),
        _make_record("s1", (), ts=datetime(2026, 4, 19, 12, 1, tzinfo=timezone.utc)),
    )
    backend.store_record(
        uuid4(),
        _make_record("s2", (), ts=datetime(2026, 4, 19, 12, 2, tzinfo=timezone.utc)),
    )
    assert set(backend.list_author_instances()) == {"s1", "s2"}

