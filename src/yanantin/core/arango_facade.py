"""The obfuscating Database→Collection façade — wrap only the slice we call.

Callers write and read SEMANTIC names and never know the boundary exists. The
façade routes every collection name through ``collection_name``, every written
doc through ``obfuscate_document``, and every returned row through
``deobfuscate_document`` — Pukara becomes what the wrapper is MADE OF, not a
thing callers touch.

**unimplemented-is-absent** (the feature, not the gap): an op we have not wrapped
is ABSENT — reaching for it raises ``AttributeError`` at author-time, loud and in
your face, instead of silently passing plaintext through an obfuscated collection.
The façade grows by demand; the shorter bypass path does not typecheck.

The one raw-Arango home is ``infra.config.get_database`` (the connection factory,
the sole allowlisted importer of python-arango). This façade wraps the handle
that factory hands out — it imports ``StandardDatabase`` only as a TYPE, never to
construct a client. The no-raw-import red bar enforces that boundary.
"""

from __future__ import annotations

from arango.database import StandardDatabase

from yanantin.core.storage_obfuscator import StorageObfuscator


class Collection:
    """One collection, semantic-in / semantic-out. Only the ops we call exist."""

    def __init__(self, raw, obfuscator: StorageObfuscator):
        self._raw = raw
        self._obf = obfuscator

    def insert(self, doc: dict):
        """Insert a document — obfuscated on the way in."""
        return self._raw.insert(self._obf.obfuscate_document(doc))

    def get(self, key: str) -> dict | None:
        """Fetch one document by key — deobfuscated on the way out."""
        row = self._raw.get(key)
        return None if row is None else self._obf.deobfuscate_document(row)

    def all(self) -> list[dict]:
        """All documents — each deobfuscated on the way out."""
        return [self._obf.deobfuscate_document(row) for row in self._raw.all()]

    def count(self) -> int:
        """Count documents. Name-only obfuscation (already applied at open)."""
        return self._raw.count()

    def has(self, key: str) -> bool:
        """Whether a document with this _key exists. The _key is an ArangoDB
        internal, not obfuscated — the immutability guard's primitive."""
        return self._raw.has(key)


class Database:
    """Wraps a StandardDatabase handle + a StorageObfuscator.

    ``collection(semantic)`` opens the collection under its PHYSICAL name, so the
    semantic name never reaches the wire, and returns a Collection that carries
    the obfuscator forward.
    """

    def __init__(self, raw: StandardDatabase, obfuscator: StorageObfuscator):
        self._raw = raw
        self._obf = obfuscator

    def collection(self, semantic: str) -> Collection:
        physical = self._obf.collection_name(semantic)
        return Collection(self._raw.collection(physical), self._obf)
