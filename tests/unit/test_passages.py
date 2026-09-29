"""Executable passage derivation spec; production module intentionally absent."""

from copy import deepcopy
from hashlib import sha256

import pytest

from yanantin.eval.find_quality import build_passages, text_a2


@pytest.fixture
def passage_api():
    # Import here so an absent feature fails tests without hiding DB test collection.
    from yanantin.apacheta.passages import derive_passages, passage_text

    return derive_passages, passage_text


def test_derive_passages_leaf_rules(passage_api):
    derive_passages, _ = passage_api
    doc = {
        "_key": "record-a", "_id": "records/record-a", "_rev": "revision",
        "_private": {"leak": "hidden"},
        "provenance": {"author_instance_id": "session-a", "note": "hidden"},
        "lineage_tags": ["hidden"],
        "title": "visible", "empty": "", "count": 7, "flag": True,
        "nothing": None, "decimal": 1.5,
        "nested": {
            "_secret": ["hidden"], "provenance": "nested provenance is content",
            "lineage_tags": ["nested tags are content"],
            "items": ["first", {"body": "second", "_internal": "hidden"}, 3, None],
        },
    }
    before = deepcopy(doc)
    passages = derive_passages(doc, "record-a")
    expected = {
        "title": "visible", "empty": "",
        "nested.provenance": "nested provenance is content",
        "nested.lineage_tags.0": "nested tags are content",
        "nested.items.0": "first", "nested.items.1.body": "second",
    }
    assert isinstance(passages, list)
    assert len(passages) == len(expected)
    assert {p["path"]: p["value"] for p in passages} == expected
    for p in passages:
        assert set(p) == {"_key", "session", "path", "value", "record_key", "text"}
        assert p["session"] == "session-a"
        assert p["record_key"] == "record-a"
        assert p["_key"] == sha256(
            f"session-a\0{p['path']}\0{p['value']}".encode()
        ).hexdigest()[:16]
        assert p["text"] == text_a2(p["path"], p["value"])
    assert doc == before


@pytest.mark.parametrize(("path", "value", "expected"), [
    ("reward_function", "reward_function", "reward function: reward function"),
    ("outer.inner_name.0", "some_value.with.dots", "outer inner name 0: some value.with.dots"),
    ("a__b.c", "", "a  b c: "),
    ("café.name", "naïve_value", "café name: naïve value"),
])
def test_passage_text_underscore_and_humanize_rules(passage_api, path, value, expected):
    _, passage_text = passage_api
    assert passage_text(path, value) == expected


def test_derive_passages_parity_with_frozen_build_passages_including_no_provenance(passage_api):
    derive_passages, _ = passage_api
    stamp = "2026-09-29T00:00:00+00:00"
    corpus = [
        {"_key": "later", "provenance": {"author_instance_id": "s1", "timestamp": stamp},
         "lineage_tags": ["cycle-2"], "body": {"reward_function": ["shared_value", "new"]}},
        {"_key": "first", "provenance": {"author_instance_id": "s1", "timestamp": stamp},
         "lineage_tags": ["cycle-1"], "body": {"reward_function": ["shared_value"]}},
        {"_key": "other", "provenance": {"author_instance_id": "s2", "timestamp": stamp},
         "body": {"reward_function": ["shared_value"]}, "_hidden": "excluded"},
        {"_key": "orphan-a", "body": {"reward_function": ["shared_value"]}},
        {"_key": "orphan-b", "body": {"reward_function": ["shared_value"]}},
    ]
    # The frozen instrument requires provenance. Adapt ONLY its input to express
    # the new key-as-session rule; the production call sees the untouched docs.
    reference = deepcopy(corpus)
    for doc in reference:
        doc.setdefault("provenance", {"author_instance_id": doc["_key"], "timestamp": stamp})
    expected = build_passages(reference)
    actual = {}
    by_key = {doc["_key"]: doc for doc in corpus}
    for key in ("first", "later", "orphan-a", "orphan-b", "other"):
        for passage in derive_passages(by_key[key], key):
            actual.setdefault(passage["_key"], passage)
    assert actual == {
        pid: {"_key": pid, **{field: p[field] for field in (
            "session", "path", "value", "record_key"
        )}, "text": text_a2(p["path"], p["value"])}
        for pid, p in expected.items()
    }
    assert {p["session"] for p in actual.values()} == {"s1", "s2", "orphan-a", "orphan-b"}
