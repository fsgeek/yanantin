"""Fail-stop, atomicity, and metadata boundaries for the passage index."""

import json
from uuid import uuid4

import pytest
from arango.exceptions import ArangoServerError

from tests.integration._obfuscators import HashingObfuscator
from tests.integration.test_find_passage_index import (
    backend_factory,  # noqa: F401 -- shared live fixture, with failure-safe cleanup
    collection,
    passage_backend,  # noqa: F401
    store,
)

pytestmark = pytest.mark.integration


def test_opaque_map_writes_no_passages_and_find_raises(backend_factory):
    mapping = HashingObfuscator(uuid4().hex)
    backend = backend_factory(mapping)
    key = store(backend, body="opaque quartz")
    assert collection(backend, "records").has(key)
    physical_passages = mapping.collection_name("passages")
    assert not backend._db.has_collection(physical_passages)
    assert mapping.collection_name("passages_bm25") not in {
        v["name"] for v in backend._db.views()
    }
    with pytest.raises(RuntimeError):
        backend.find("quartz")
    assert not backend._db.has_collection(physical_passages)


def test_missing_passage_view_makes_find_raise(passage_backend):
    store(passage_backend, body="quartz fallback tripwire")
    view_name = passage_backend._map.collection_name("passages_bm25")
    # ignore_missing allows the old scan implementation to reach the decisive
    # raises assertion even though it never created a view in the first place.
    passage_backend._db.delete_view(view_name, ignore_missing=True)
    with pytest.raises(ArangoServerError):
        passage_backend.find("quartz")


def test_failed_passage_insert_rolls_back_record_atomically(passage_backend):
    db = passage_backend._db
    name = passage_backend._map.collection_name("passages")
    assert db.has_collection(name), "passage collection must be created at initialization"
    passages = db.collection(name)
    # A real server-side insert failure, not a fake database or mocked write.
    passages.configure(schema={
        "level": "strict",
        "rule": {"type": "object", "required": ["test_required_missing"]},
        "message": "deliberate passage-insert failure",
    })
    key = uuid4()
    before = passages.count()
    with pytest.raises(ArangoServerError):
        store(passage_backend, record_id=key, body="quartz atomicity")
    assert not collection(passage_backend, "records").has(str(key))
    assert passages.count() == before


class HashingMapWithIndexEnabled(HashingObfuscator):
    """Force the transparent-only creation branch to test physical metadata.

    This deliberately adversarial flag is test-only: real opaque maps must not
    create an index (tested above). Every name still goes through actual hashing,
    exposing accidental raw semantic names in the backend/Khipu handoff.
    """

    @property
    def is_transparent(self):
        return True


def test_passage_view_name_and_links_have_no_semantic_names_under_hashing(backend_factory):
    mapping = HashingMapWithIndexEnabled(uuid4().hex)
    backend = backend_factory(mapping)
    physical_view = mapping.collection_name("passages_bm25")
    physical_collection = mapping.collection_name("passages")
    physical_text = mapping.field_name("text")
    assert physical_view in {v["name"] for v in backend._db.views()}
    view = backend._db.view(physical_view)
    links = view["links"]
    assert set(links) == {physical_collection}
    assert set(links[physical_collection]["fields"]) == {physical_text}
    assert links[physical_collection]["fields"][physical_text]["analyzers"] == ["text_en"]
    assert links[physical_collection].get("includeAllFields", False) is False
    # Structural Arango properties and analyzer identifiers are not semantic
    # application names. Check all collection/field keys, including nested ones.
    def field_names(fields):
        for name, properties in fields.items():
            yield name
            yield from field_names(properties.get("fields", {}))

    names = [physical_view, *links, *field_names(links[physical_collection]["fields"])]
    encoded_names = json.dumps(names)
    for semantic in ("passages", "passages_bm25", "text", "session", "record_key", "path", "value"):
        assert semantic not in encoded_names
