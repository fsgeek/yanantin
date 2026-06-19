# Dynamic Collection Registration

**Date:** 2026-06-18
**Status:** Designed, awaiting review
**Supersedes:** `2026-06-18-storage-recorder-tier-spine-design.md` (which had the wrong center — storage — and is kept only for its ownership-rule reasoning and index-shape census).
**Issues:** #1 (the center — replace static collection lists with dynamic registration), and as downstream customers/beneficiaries: #17, #31, #3, #14, Hamut'ay ArangoSearch view.

## Why (the finding that produced this spec)

Every recorder performs ONE operation: record observed data into the collection that holds that *kind* of data. The data kind determines *which* collection; it never determines *how you bind to it*. Yet yanantin has **three** binding styles for that one operation:

- **tensor path** — central type→collection map in the backend (`apacheta/backends/arango.py`); recorder names a type, backend routes. Schema-less.
- **activity path** — central static tuple `_SEMANTIC_COLLECTIONS = ("activity_facts","activity_anchors")` + `_ensure_collections()` (`activity/backends/arango.py`). Schema-less. (This is the exact static list gh #1 exists to kill.)
- **storage `Objects` path** — the collection name is a **leaf constant** (`recorder/storage/local/linux/registration.py:16` `STORAGE_OBJECTS="Objects"`); collection existence owned by **nobody** (caller passes `owned_collection=`, leaf only checks-and-raises).

Two of three already centralize collection ownership (the leaf binds to nothing); the storage path is the lone deviation that strands a shared fact in a leaf. The root cause is that the **dynamic collection-registration primitive (gh #1) was never built**, so each subsystem hand-rolled a partial static creator. Indaleko lived this exact evolution: it started static, Tony added dynamic registration in the activity work (`indaleko/utils/registration_service.py`), but tolerated the static table (`db_collections.py`) under dissertation time-pressure — leaving "two systems that don't mesh properly." Yanantin reproduced the un-meshed split *before* even having schema.

**Ordering constraint (Tony, load-bearing):** *"I can layer a static system on top of a dynamic one, but not vice versa."* Dynamic is the floor; static (a names registry) is optional sugar on top. Build dynamic-first or the two-creators split returns.

## The mechanism

One creation verb is the **sole** creator of collections:

```
register(name, definition) -> collection_handle
```

- `name`: a clear string (see Naming). For well-known collections it comes from the names registry; for per-provider collections it is generated (`prefix + identifier`).
- `definition`: schema + indices + views for this collection.
- returns a **bound collection handle** — created, schema'd, knows its name, writes through itself. The caller never holds a raw collection name.

### Init contract (per `[[project_collection_init_contract_schema_is_data_not_config.md]]`)

Idempotent, convergent-toward-the-definition, **never destructive**:

- **Collection:** create only if absent.
- **Indices:** create-if-absent, additive, **per-element**. To change one: edit the definition, DROP that index by hand, rerun → it recreates the missing one, skips the rest. The drop is the human's deliberate act.
- **Views:** same as indices.
- **Schema:** applied **only at collection creation**. On an existing collection, the verb **NEVER touches schema.** A schema change is a DATA MIGRATION (new collection + copy + repoint), because schema is a property of the data: (1) an enforcement boundary — tightening it breaks the next update to an existing non-conforming record; (2) a published interface — read back to tell an LLM the shape so it can build AQL. **NEGATIVE REQUIREMENT, red-bar it:** the verb must never apply or alter schema on a collection that already exists.

`register` is safe to call anytime; double-registration is harmless (create-if-absent). The call site MAY also check-first (the Indaleko `mime_extractor_example.py` pattern: `lookup_provider_by_identifier` → register only if absent) — belt and suspenders.

### Schema generation

Schema is generated from the Pydantic model via Indaleko's envelope, ported verbatim (`indaleko/data_models/base.py:93`): `{"message": ..., "level": "strict", "type": "json", "rule": Model.model_json_schema()}`. `level: "strict"` = validate on every write; it does **NOT** mean "no extra fields" (that is `additionalProperties`, governed by the model's `extra=` config). Models that must keep an open lane (e.g. `ContributedRecord`, already `extra="allow"`) therefore do not emit `additionalProperties: false`. Required-and-conformant core + open extras.

## Naming (unified, clear)

**One naming scheme, clear names.** Obfuscated collection names buy nothing: the SchemaMap obfuscates *labels* not *values*, the breach adversary reads values regardless (`[[project_categorical_substitution_theater.md]]`, `[[project_pukara_rosetta_stone_map_is_the_asset.md]]`), and Pukara is the trust boundary. So the registration verb's naming path does not use the obfuscator. (Value-handling layers are unaffected; this is about collection *names* only — verify no naming-path consumer is load-bearing before removing the map call.)

**Two SOURCES of a name, ONE verb** — the (a)/(b) "shared vs per-provider" seam dissolves:
- **well-known / shared** (storage `Objects`): name is a constant from the registry; many registrants naming the same string get the **same** handle back (first creates, rest find-and-return — the community-write model, provider identity carried as a *field*). No coordination problem because the name lives in one file.
- **per-provider / minted** (activity, semantic): name is generated `prefix + identifier`; collision-free by construction.

The verb takes a name and a definition; it does not care which source produced the name.

## The three structures (Tony's `IndalekoDBCollections`/`IndalekoCollection`/`IndalekoCollections` split, jobs separated, names deliberately NOT one-letter-apart)

| Job | Indaleko origin | Here |
|---|---|---|
| **Names + definitions registry** (pure data: name → schema/indices/views) | `IndalekoDBCollections` (`db_collections.py`) | `well_known_collections.py` — pure data structure, one place to look (collision-avoidance) and to add a view. **One registry, name→definition** (not names-only — matches Tony's actual practice: the constant sits beside its definition). |
| **Bound collection handle** (created, schema'd, returned) | `IndalekoCollection` (`collection.py`) | the handle `register` returns |
| **Creator** | `IndalekoCollections` (`i_collections.py`) — eagerly walks the table at startup | the `register` verb — **pulls** a well-known definition from the registry **on registration**, NOT an eager startup walk. This is the one thing changed from Indaleko: creation is on-demand, never a static walk. |

`well_known_collections.py` keeps the `IndalekoDBCollections` *shape* (name→definition registry — the ergonomic Tony valued). What is deleted is the eager static *creator* (`IndalekoCollections.__init__`'s walk). Nothing statically walks-to-create.

### Base / subclass split (proven by `indaleko/semantic/examples/mime_extractor_example.py`)

A generic registration base owns the verb + the registry/collection-minting + identity fields `(Identifier, Name, Description, Version, provenance Record)`. Per-type subclasses own:
- the **domain payload** validated in `_process_registration_data` (e.g. semantic's `SupportedMimeTypes`, `ResourceIntensity`, `ProcessingPriority`, `ExtractedAttributes`),
- a **domain-named verb** (`register_semantic_extractor` / `register_activity_provider` / `register_storage_recorder`),
- **domain queries** (`get_supported_mime_types`, `find_extractors_for_mime_type`, `get_activity_providers_by_type`, ...).

The yanantin `core/registration.py:Registrar` is the existing dynamic-catalog layer this grows from — it gains schema-bearing collection creation and the handle return. It is NOT a new parallel system.

## Three pressure-test use-cases (DESIGNED here, BUILT later)

The mechanism is designed against all three before any is built, so the interface is not over-fit to one. Each instantiates the same skeleton, differing only in name-source + domain payload + queries.

1. **Storage** (the messiest — well-known, shared, community-write, retrofit-onto-live). `register_storage_recorder` registers well-known `Objects`/`Relationships` (names from the registry) with the storage-object definition. `StorageRecorderBase` owns the *definition* at the tier where the storage shape is constant; the leaf keeps its own recorder identity (provenance) and writes through the returned handle, naming no collection (`[[project_ownership_at_the_tier_where_the_fact_stops_varying.md]]`). The storage-object definition is where #31's `URI`/`ObjectIdentifier` unique indices, #3's timestamp persistent+inverted indices, and the Hamut'ay arangosearch view land (index *shape* per `indaleko/db/db_collections.py:140-330`; Pukara owns label-stability, do not port UUID index keys).
2. **Activity** (the most dynamic — per-provider minted collections). `register_activity_provider`; name generated `prefix + identifier`. Replaces the static `_SEMANTIC_COLLECTIONS` tuple with registry entries + dynamic registration.
3. **Semantic** (the muddle in the middle — Indaleko's never-fully-converted path). `register_semantic_extractor`, per the worked example: domain payload `SupportedMimeTypes`/`ResourceIntensity`/`ProcessingPriority`/`ExtractedAttributes`; returns `(record, collection)`; mime-type queries.

If one verb + the base/subclass split serves all three on paper (hypothesis: yes — the split falls exactly where the mime example shows), the interface is validated.

## Testing

- **Red bar:** the verb must NOT apply/alter schema on a pre-existing collection (the negative requirement). Construct a schema-less collection, register a now-schema-bearing definition for that name, assert the existing collection's schema is untouched (change is a migration, not an init side-effect).
- **Red bar:** write a record missing a required field to a NEWLY-created schema-bearing collection, assert the DB refuses it (`[[feedback_stronger_tests_never_an_error.md]]`).
- **Green:** create-if-absent collection/index/view; idempotent re-register is a no-op; dropped index is recreated on rerun.
- **Green:** a record with extra undeclared fields IS accepted on an `extra="allow"`-derived schema (open lane intact).
- **Green:** two registrants naming the same well-known string get the same handle (community write); two per-provider registrants get distinct collections.
- All against live `apacheta_test` (`[[feedback_no_mock_databases.md]]`).

## Explicitly deferred (named, not silently dropped)

- **Build** of the three use-cases — one instance each (parallel or serial, decided at plan time). This spec DESIGNS; it does not build.
- **Migration of the existing static creators** (activity `_SEMANTIC_COLLECTIONS`, tensor type-map) onto the verb — follow-on; closing this is what finishes #1.
- **Schema-retrofit migration** of the live schema-less `Objects`/`activity_facts` collections — its OWN later pour (new schema-bearing collection + copy + repoint), with a data-surfacing step that discovers the non-conforming rows that were being silently accepted (ROOT: that discovery is product, not cleanup). NOT part of the mechanism pour.
- **Names-registry as the only collision detector** (chosen over schema-compare: a shared *schema* is correct stacking, not a collision; the real collision is name-reuse, caught at declaration as a one-file merge conflict).

## Open items to resolve during implementation (flagged)

- Exact relationship between the new `register` verb and the existing `Registrar` methods (`register`, `_ensure_collection`, `contribute`) — grow vs wrap. Driven by the real `Registrar` code.
- Whether `ContributedRecord` needs promoted declared core fields (identity, canonical timestamps) for the storage definition's `required` set / unique indices to be meaningful — touches #17/#31. The schema is only as strong as the model's declared core.
- Verifying no naming-path consumer depends on the obfuscated collection name before removing the map call from the naming path.
