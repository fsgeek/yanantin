from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.provenance import ProvenanceEnvelope


def _make_record(session_id: str, tags: tuple[str, ...], **extras) -> ApachetaBaseModel:
    prov = ProvenanceEnvelope(
        author_model_family="haiku",
        author_instance_id=session_id,
        predecessors_in_scope=(),
        timestamp=datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc),
    )
    return ApachetaBaseModel(provenance=prov, lineage_tags=tags, **extras)


def test_list_open_records_returns_all():
    backend = InMemoryBackend()
    id_a, id_b = uuid4(), uuid4()
    backend.store_record(id_a, _make_record("s1", ("hamutay",)))
    backend.store_record(id_b, _make_record("s2", ("hamutay",)))
    results = backend.list_open_records()
    assert {rid for (rid, _) in results} == {id_a, id_b}


def test_list_open_records_respects_limit():
    backend = InMemoryBackend()
    for _ in range(5):
        backend.store_record(uuid4(), _make_record("s1", ()))
    assert len(backend.list_open_records(limit=2)) == 2


def test_query_open_by_author_instance_filters():
    backend = InMemoryBackend()
    id_s1_a, id_s1_b, id_s2 = uuid4(), uuid4(), uuid4()
    backend.store_record(id_s1_a, _make_record("s1", ()))
    backend.store_record(id_s1_b, _make_record("s1", ()))
    backend.store_record(id_s2, _make_record("s2", ()))
    results = backend.query_open_by_author_instance("s1")
    assert {rid for (rid, _) in results} == {id_s1_a, id_s1_b}


def test_query_open_by_author_instance_skips_records_without_provenance():
    backend = InMemoryBackend()
    id_with, id_without = uuid4(), uuid4()
    backend.store_record(id_with, _make_record("s1", ()))
    backend.store_record(id_without, ApachetaBaseModel(lineage_tags=()))
    results = backend.query_open_by_author_instance("s1")
    assert {rid for (rid, _) in results} == {id_with}


def test_query_open_by_lineage_tag():
    backend = InMemoryBackend()
    id_a, id_b = uuid4(), uuid4()
    backend.store_record(id_a, _make_record("s1", ("hamutay", "cycle-5")))
    backend.store_record(id_b, _make_record("s1", ("hamutay", "cycle-6")))
    results = backend.query_open_by_lineage_tag("cycle-5")
    assert {rid for (rid, _) in results} == {id_a}


def test_query_open_has_field():
    backend = InMemoryBackend()
    id_a, id_b = uuid4(), uuid4()
    backend.store_record(id_a, _make_record("s1", (), theme="opening"))
    backend.store_record(id_b, _make_record("s1", ()))
    results = backend.query_open_has_field("theme")
    assert {rid for (rid, _) in results} == {id_a}


def test_list_author_instances_distinct():
    backend = InMemoryBackend()
    backend.store_record(uuid4(), _make_record("s1", ()))
    backend.store_record(uuid4(), _make_record("s1", ()))
    backend.store_record(uuid4(), _make_record("s2", ()))
    assert set(backend.list_author_instances()) == {"s1", "s2"}

