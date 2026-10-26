"""Live tests for find over Objects: a path segment anywhere, plus name and time.

Tony's target (2026-10-16): filter for ".ssh" in the directory part of the URI and
"config" as the name, across machines, within 50 ms. Exact segments: ".ssh" must
not match "ssh" or "openssh". Runs against apacheta_test, with a plain and an
obfuscating Khipu, because the view and the query must name physical fields.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest

from tests.integration._obfuscators import PrefixObfuscator

ARANGO_HOST = os.environ.get("YANANTIN_ARANGO_HOST", "http://localhost:8529")
ARANGO_DB = os.environ.get("YANANTIN_ARANGO_DB", "apacheta_test")
ARANGO_USER = os.environ.get("YANANTIN_ARANGO_USER", "apacheta_test")
ARANGO_PASSWORD = os.environ.get("YANANTIN_ARANGO_PASSWORD", "")

DOCS = [
    ("file:///srv/a/.ssh/config", "config", "2026-10-01T00:00:00Z"),
    ("file:///srv/b/projects/x/.ssh/known_hosts", "known_hosts", "2026-09-01T00:00:00Z"),
    ("file:///srv/c/openssh/config", "config", "2026-10-01T00:00:00Z"),
    ("file:///srv/d/ssh/config", "config", "2026-10-01T00:00:00Z"),
    ("file:///srv/e/.config/app/config", "config", "2026-08-01T00:00:00Z"),
]


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


@pytest.fixture(params=["plain", "obfuscated"])
def objects(request, db):
    from yanantin.core.khipu import Khipu
    from yanantin.core.storage_obfuscator import TransparentObfuscator
    from yanantin.recorder.storage.objects_definition import OBJECTS_DEFINITION, ensure_objects_find_view

    tag = uuid4().hex[:8]
    obf = PrefixObfuscator(f"o{tag}_") if request.param == "obfuscated" else TransparentObfuscator()
    name, view = f"objects_t_{tag}", f"objects_find_t_{tag}"
    coll = Khipu(db, obf).watay(name, OBJECTS_DEFINITION)
    ensure_objects_find_view(db, obf, collection=name, view=view)
    coll.insert_many([obf.obfuscate_document({"uri": u, "label": label, "modified": m})
                      for u, label, m in DOCS])
    yield db, obf, view
    db.delete_view(view, ignore_missing=True)  # view names are not obfuscated
    db.delete_collection(obf.collection_name(name), ignore_missing=True)


def _find(objects, **kw):
    from yanantin.recorder.storage.objects_find import find_objects

    db, obf, view = objects
    return sorted(find_objects(db, obf, view=view, wait_for_sync=True, **kw))


def test_segment_anywhere_in_the_path_is_exact(objects):
    assert _find(objects, segments=(".ssh",)) == [
        "file:///srv/a/.ssh/config", "file:///srv/b/projects/x/.ssh/known_hosts"]


def test_segment_and_name(objects):
    assert _find(objects, segments=(".ssh",), label="config") == ["file:///srv/a/.ssh/config"]


def test_name_alone(objects):
    assert len(_find(objects, label="config")) == 4


def test_modified_window(objects):
    assert _find(objects, label="config", modified_from="2026-09-15T00:00:00Z") == [
        "file:///srv/a/.ssh/config", "file:///srv/c/openssh/config", "file:///srv/d/ssh/config"]


def test_two_segments_must_both_appear(objects):
    assert _find(objects, segments=("srv", ".config")) == ["file:///srv/e/.config/app/config"]


def test_nothing_asked_is_refused(objects):
    with pytest.raises(ValueError):
        _find(objects)


def test_watay_is_idempotent_with_analyzer_and_view(db):
    from yanantin.core.khipu import Khipu
    from yanantin.recorder.storage.objects_definition import (
        OBJECTS_DEFINITION, PATH_SEGMENTS_ANALYZER, ensure_objects_find_view)

    tag = uuid4().hex[:8]
    name, view = f"objects_t_{tag}", f"objects_find_t_{tag}"
    try:
        Khipu(db).watay(name, OBJECTS_DEFINITION)
        for _ in range(2):
            ensure_objects_find_view(db, collection=name, view=view)
        assert any(a["name"].split("::")[-1] == PATH_SEGMENTS_ANALYZER for a in db.analyzers())
        assert view in {v["name"] for v in db.views()}
    finally:
        db.delete_view(view, ignore_missing=True)
        db.delete_collection(name, ignore_missing=True)
