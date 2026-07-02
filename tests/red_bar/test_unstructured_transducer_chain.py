"""Red bar: the Unstructured transducer chain, end to end, on a real file.

Proves the full goal chain when docker is reachable:
  real file -> transduce() (Unstructured in the stock container via docker SDK)
            -> ContentFact -> stored in the `records` lane
            -> content BM25 view returns it, ranked.

Docker gating is NARROW and LOUD: if the daemon is unreachable the live-run test
skips with an explicit reason (green-from-inside a broken docker env is not
authoritative — cf. the sandbox-silent-skip lesson). The docker-INDEPENDENT
folding logic is guarded separately and always runs.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.content_view import (
    CONTENT_FIELD,
    CONTENT_VIEW_NAME,
    ensure_content_view,
    search_content_bm25,
)
from yanantin.collector.semantic.unstructured.transducer import (
    ContentFact,
    _elements_to_content_fact,
    docker_available,
    transduce,
    transduce_in_process,
    unstructured_available,
)
from yanantin.infra.config import ApachetaDBConfig

pytestmark = pytest.mark.integration


def test_elements_fold_to_content_fact_retaining_structure():
    """Docker-independent: element dicts -> ContentFact. content is the joined
    text; every element is retained (don't-throw-anything-away)."""
    elements = [
        {"type": "Title", "text": "Yanantin"},
        {"type": "NarrativeText", "text": "ayllu substrate"},
        {"type": "Image", "text": None},
    ]
    cf = _elements_to_content_fact("file:///tmp/x.txt", elements)
    assert cf.content == "Yanantin\nayllu substrate"
    assert len(cf.elements) == 3  # None-text element kept, not dropped


def _backend():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return ArangoDBBackend(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )


def _prove_chain(fact, be):
    """Given a transduced ContentFact, store it and prove the BM25 view finds it."""
    assert isinstance(fact, ContentFact)
    assert "ayllu" in fact.content.lower()
    db = be._db
    obf = be._map
    recs = db.collection(obf.collection_name("records"))
    recs.truncate()
    if CONTENT_VIEW_NAME in {v["name"] for v in db.views()}:
        db.delete_view(CONTENT_VIEW_NAME)
    key = str(uuid4())
    recs.insert({"_key": key, obf.field_name(CONTENT_FIELD): fact.content})
    ensure_content_view(db, obf)
    hits = []
    for _ in range(20):
        hits = search_content_bm25(db, "ayllu", obf, limit=5)
        if hits:
            break
        list(db.aql.execute("RETURN 1"))
    try:
        assert any(k == key for k, _ in hits), (
            "transduced content did not surface through the BM25 view — chain broken"
        )
    finally:
        recs.truncate()
        if CONTENT_VIEW_NAME in {v["name"] for v in db.views()}:
            db.delete_view(CONTENT_VIEW_NAME)
        be.close()


@pytest.mark.skipif(
    not unstructured_available(),
    reason="`unstructured` package not installed (pip install unstructured)",
)
def test_transduce_in_process_real_file_lands_and_is_bm25_findable(tmp_path):
    """Full chain, IN-PROCESS (no docker): Unstructured partitions a real file,
    the content lands in records, the BM25 view finds it. This is the sixth
    criterion SHOWN — transducer runs on a real file, structured content emitted,
    surfaced through native BM25 — with no daemon dependency."""
    doc = tmp_path / "note.txt"
    doc.write_text("Quechua naming convention for the ayllu substrate.\n")
    fact = transduce_in_process(doc)
    _prove_chain(fact, _backend())


@pytest.mark.skipif(
    not docker_available(),
    reason="docker daemon unreachable — the docker TRANSPORT is gated NARROWLY "
    "(DOCKER_HOST / Docker Desktop WSL integration). The in-process path above "
    "already shows the chain; this proves the container transport too.",
)
def test_transduce_docker_real_file_lands_in_records_and_is_bm25_findable(tmp_path):
    """Same chain via the docker transport (dependency-isolation path)."""
    doc = tmp_path / "note.txt"
    doc.write_text("Quechua naming convention for the ayllu substrate.\n")

    fact = transduce(doc)
    assert isinstance(fact, ContentFact)
    assert "ayllu" in fact.content.lower()

    be = _backend()
    db = be._db
    obf = be._map
    recs = db.collection(obf.collection_name("records"))
    recs.truncate()
    if CONTENT_VIEW_NAME in {v["name"] for v in db.views()}:
        db.delete_view(CONTENT_VIEW_NAME)

    key = str(uuid4())
    recs.insert({"_key": key, obf.field_name(CONTENT_FIELD): fact.content})
    ensure_content_view(db, obf)

    hits = []
    for _ in range(20):
        hits = search_content_bm25(db, "ayllu", obf, limit=5)
        if hits:
            break
        list(db.aql.execute("RETURN 1"))

    try:
        assert any(k == key for k, _ in hits), (
            "transduced content did not surface through the BM25 view — chain broken"
        )
    finally:
        recs.truncate()
        if CONTENT_VIEW_NAME in {v["name"] for v in db.views()}:
            db.delete_view(CONTENT_VIEW_NAME)
        be.close()
