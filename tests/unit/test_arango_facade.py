"""The obfuscating Database→Collection façade: only the slice we call, each op
routing names/docs/rows through an injected StorageObfuscator.

Tested against a NON-IDENTITY fake obfuscator, never transparent-only. A
transparent obfuscator maps everything to itself, so a façade that FORGOT to call
the obfuscator would still pass a transparent test — the exact silent-default
trap the boundary exists to kill. The fake proves routing actually happens by
making the mapped form observably different from the semantic form.

No DB: a fake StandardDatabase records what collection name it was asked for and
what doc reached the wire, so we assert the façade obfuscated on the way in and
deobfuscated on the way out.
"""

from __future__ import annotations

from yanantin.core.arango_facade import Database


class PrefixObfuscator:
    """Non-identity StorageObfuscator: prefixes names, tags docs. Reversible."""

    def collection_name(self, semantic: str) -> str:
        return f"c_{semantic}"

    def field_name(self, semantic: str) -> str:
        return f"f_{semantic}"

    def field_path(self, parts: tuple[str, ...]) -> str:
        return ".".join(f"f_{p}" for p in parts)

    def reverse_field(self, opaque: str) -> str:
        return opaque[2:] if opaque.startswith("f_") else opaque

    def obfuscate_document(self, doc: dict) -> dict:
        return {self.field_name(k): v for k, v in doc.items()}

    def deobfuscate_document(self, doc: dict) -> dict:
        return {self.reverse_field(k): v for k, v in doc.items()}

    @property
    def is_transparent(self) -> bool:
        return False


class FakeCollection:
    """Records the physical name it was created under and what reached it."""

    def __init__(self, name: str):
        self.name = name
        self.inserted: list[dict] = []
        self._rows: list[dict] = []

    def insert(self, doc: dict):
        self.inserted.append(doc)
        return {"_key": "k"}

    def get(self, key: str):
        return dict(self._rows[0]) if self._rows else None

    def all(self):
        return [dict(r) for r in self._rows]

    def count(self) -> int:
        return len(self._rows)


class FakeDatabase:
    """A stand-in StandardDatabase: hands out FakeCollections by physical name."""

    def __init__(self):
        self.requested: list[str] = []
        self.collections_by_name: dict[str, FakeCollection] = {}

    def collection(self, name: str) -> FakeCollection:
        self.requested.append(name)
        return self.collections_by_name.setdefault(name, FakeCollection(name))


def test_collection_name_is_obfuscated_before_touching_the_handle():
    raw = FakeDatabase()
    db = Database(raw, PrefixObfuscator())

    db.collection("Objects")

    # the handle was asked for the PHYSICAL name, never the semantic one
    assert raw.requested == ["c_Objects"]


def test_insert_obfuscates_the_document_on_the_way_in():
    raw = FakeDatabase()
    db = Database(raw, PrefixObfuscator())

    db.collection("Objects").insert({"CreationTime": 123, "size": 9})

    wire = raw.collections_by_name["c_Objects"].inserted[0]
    assert wire == {"f_CreationTime": 123, "f_size": 9}  # semantic names never hit the wire


def test_get_deobfuscates_rows_on_the_way_out():
    raw = FakeDatabase()
    raw.collections_by_name["c_Objects"] = FakeCollection("c_Objects")
    raw.collections_by_name["c_Objects"]._rows = [{"f_CreationTime": 123}]
    db = Database(raw, PrefixObfuscator())

    row = db.collection("Objects").get("k")

    assert row == {"CreationTime": 123}  # caller sees SEMANTIC names, never physical


def test_all_deobfuscates_every_row():
    raw = FakeDatabase()
    raw.collections_by_name["c_Objects"] = FakeCollection("c_Objects")
    raw.collections_by_name["c_Objects"]._rows = [{"f_a": 1}, {"f_b": 2}]
    db = Database(raw, PrefixObfuscator())

    rows = db.collection("Objects").all()

    assert rows == [{"a": 1}, {"b": 2}]


def test_count_maps_collection_name_only():
    raw = FakeDatabase()
    raw.collections_by_name["c_Objects"] = FakeCollection("c_Objects")
    raw.collections_by_name["c_Objects"]._rows = [{}, {}, {}]
    db = Database(raw, PrefixObfuscator())

    assert db.collection("Objects").count() == 3
    assert raw.requested == ["c_Objects"]
