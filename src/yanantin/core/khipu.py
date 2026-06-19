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
            # Schema is applied IN the create call (atomic), not via a separate
            # configure() — a two-step create-then-configure leaves a window in
            # which the collection exists schema-less, so a concurrent caller on
            # the same well-known name (the community-write path) could write a
            # record before the enforcement boundary lands. create_collection
            # accepts schema= natively; schema=None is the no-schema default.
            collection = self._db.create_collection(
                physical, edge=definition.edge, schema=definition.schema
            )
        else:
            collection = self._db.collection(physical)

        existing_index_names = {i.get("name") for i in collection.indexes()}
        for index in definition.indices:
            if index.get("name") not in existing_index_names:
                collection.add_index(index)

        existing_view_names = {v["name"] for v in self._db.views()}
        for view in definition.views:
            if view["name"] not in existing_view_names:
                # KNOWN GAP (gh #32): view `links` keys are passed verbatim,
                # NOT routed through self._obfuscator.collection_name(). Under the
                # transparent obfuscator (dev/test) physical == semantic so this is
                # invisible; under the keyed obfuscator the view would link a
                # collection name the DB never created AND leak a semantic name into
                # a DB-visible view definition (a C0 break). No real view definition
                # exists yet (views are deferred to the use-case pours); when one
                # lands, obfuscate the link keys here before creating the view.
                self._db.create_arangosearch_view(
                    name=view["name"], properties={"links": view.get("links", {})}
                )

        return collection
