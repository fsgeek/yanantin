"""Khipu — the dynamic collection-binding service (the knotted-cord registry).

Verb `watay` ("to tie/bind"): bind a collection name to its definition and
ensure the collection exists. The SOLE creator of collections (after the legacy
static creators are migrated). Adjacent to core/registration.py:Registrar — NOT
merged: Khipu owns name->definition->handle, Registrar owns provider identity.

Init contract (NEVER destructive):
  - collection: create only if absent
  - schema: applied ONLY at creation; never touched on an existing collection
    (schema is data — an enforcement boundary + published interface; a change
    is a migration, not an init side-effect)
  - indices/views: create-if-absent, additive (Task 3)
"""

from __future__ import annotations

from arango.collection import StandardCollection
from arango.database import StandardDatabase

from yanantin.core.collection_definition import CollectionDefinition
from yanantin.core.storage_obfuscator import StorageObfuscator, TransparentObfuscator


class Khipu:
    """Binds collection names to their definitions; ensures they exist."""

    def __init__(
        self,
        db: StandardDatabase,
        obfuscator: StorageObfuscator | None = None,
    ) -> None:
        self._db = db
        self._obfuscator = obfuscator or TransparentObfuscator()

    def watay(
        self, name: str, definition: CollectionDefinition
    ) -> StandardCollection:
        """Bind semantic `name` to `definition`; ensure the collection exists.

        Returns the live (physical/obfuscated) collection handle. Schema is
        applied ONLY when the collection is newly created.
        """
        physical = self._obfuscator.collection_name(name)
        if not self._db.has_collection(physical):
            collection = self._db.create_collection(physical, edge=definition.edge)
            if definition.schema is not None:
                collection.configure(schema=definition.schema)
        else:
            collection = self._db.collection(physical)
        return collection
