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
        # Transparent only as an explicit, greppable fallback — never via a
        # silent `or` default (see tests/red_bar/test_obfuscator_default_is_explicit).
        if obfuscator is None:
            obfuscator = TransparentObfuscator()
        self._obfuscator = obfuscator

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
                # gh #32 (one layer over): index `fields` name SEMANTIC fields;
                # route them through the obfuscator so the index is built on the
                # PHYSICAL field the stored docs actually use, and no semantic
                # field name leaks into queryable index metadata (a C0 break).
                collection.add_index(self._obfuscate_index(index))

        existing_view_names = {v["name"] for v in self._db.views()}
        for view in definition.views:
            if view["name"] not in existing_view_names:
                # gh #32: view `links` name the SEMANTIC collection/fields; route
                # both levels through the obfuscator so the DB-visible view def
                # links the PHYSICAL collection (the one we created) and never
                # leaks a semantic name into queryable metadata (a C0 break).
                self._db.create_arangosearch_view(
                    name=view["name"],
                    properties={"links": self._obfuscate_links(view.get("links", {}))},
                )

        return collection

    def _obfuscate_index(self, index: dict) -> dict:
        """Route an index definition's `fields` through the obfuscator so the
        index is built on the PHYSICAL field names the stored docs use. All other
        properties (type, name, sparse, unique, ...) pass through unchanged. The
        index `name` is our own opaque handle, not a semantic field — left as-is."""
        if "fields" not in index:
            return index
        obfuscated = dict(index)
        obfuscated["fields"] = [
            self._obfuscator.field_name(field) for field in index["fields"]
        ]
        return obfuscated

    def _obfuscate_links(self, links: dict) -> dict:
        """Route an ArangoSearch `links` dict through the obfuscator: outer keys
        are collection names, the nested `fields` keys are field names; all other
        properties (analyzers, etc.) pass through unchanged."""
        obfuscated: dict = {}
        for coll, link in links.items():
            new_link = dict(link)
            if "fields" in link:
                new_link["fields"] = {
                    self._obfuscator.field_name(field): props
                    for field, props in link["fields"].items()
                }
            obfuscated[self._obfuscator.collection_name(coll)] = new_link
        return obfuscated
