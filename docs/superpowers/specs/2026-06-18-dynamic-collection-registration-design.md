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

## Vocabulary (the frame — read first)

Adversarial review (Codex, 2026-06-18) found this spec colliding with three prior decisions. The root cause was **one English word, "registration," flattening three distinct operations the code keeps separate** (Tony: *"any 'insert this entry into a table' is a registration, so the words entangle"*). The boundary erodes when the language doesn't mark it. So: three operations, three non-overlapping names.

| # | Operation | Question it answers | Home | Contract |
|---|---|---|---|---|
| 1 | **Mapping** | *which collection does this provider-hierarchy feed?* | recorder base class (06-17 spec) | `Objects` mapped at the base storage class; everything below writes into the one shared collection. Overridable in theory; no use case now. **Unchanged by this spec.** |
| 2 | **Provider registration** | *this collector/recorder exists; its identity* | `core/registration.py:Registrar.register` | provenance, IMMUTABLE — returns `RegistrantRecord`, **raises on duplicate id**. **Unchanged by this spec.** |
| 3 | **Collection binding** | *bind a collection name to its (schema, indices, views); ensure it exists* | **`Khipu`** (NEW, this spec) | idempotent create-if-absent. The subject of this document. |

Operation 3 is named in Quechua deliberately, to escape the "register" overload: the service is **`Khipu`** (the knotted-cord registry — a record made *of* bindings), the verb is **`watay`** ("to tie/bind"). `khipu.watay(name, definition) -> handle`. It **cannot** collide with `Registrar.register`.

### Reconciliation with prior specs

- **06-17 recorder-collection-mapping** (`docs/superpowers/specs/2026-06-17-recorder-collection-mapping-design.md`): NOT reversed. Its "no registrar change" was about *mapping* (op 1). Collection *binding* (op 3) is a different operation. Orthogonal; both stand.
- **C0 obfuscation invariant** (`registration.py:89` "names through the obfuscator from the first pour", + test `test_owned_collection_is_created_under_obfuscated_name`): HONORED, not superseded. `watay` maps name→obfuscated before create (see Naming). An earlier draft of this spec proposed clear names — withdrawn as a reversal of a defended, tested invariant.
- **Existing `Registrar`**: untouched. `Khipu` is an ADJACENT service. A recorder may both `Registrar.register` its identity (op 2) and `khipu.watay` its collection (op 3); they collaborate, they do not merge.

## The mechanism

`Khipu` is the **sole creator of collections — after migration.** It is the only creator *by design*; until the legacy static creators (tensor type-map, activity `_SEMANTIC_COLLECTIONS`) are migrated onto it (deferred — see below), they coexist as the temporary exception. The end state is one creator; the migration path has two. One verb:

```
khipu.watay(name, definition) -> collection_handle
```

- `name`: the **semantic** collection name (see Naming — `watay` obfuscates it before create). For well-known collections it comes from the registry; for per-provider collections it is generated (`prefix + identifier`).
- `definition`: schema + indices + views for this collection.
- returns a **bound collection handle** — created, schema'd, knows its (obfuscated) physical name, writes through itself. The caller holds the handle, never a raw collection name.

### Init contract (per `[[project_collection_init_contract_schema_is_data_not_config.md]]`)

Idempotent, convergent-toward-the-definition, **never destructive**:

- **Collection:** create only if absent.
- **Indices:** create-if-absent, additive, **per-element**. To change one: edit the definition, DROP that index by hand, rerun → it recreates the missing one, skips the rest. The drop is the human's deliberate act.
- **Views:** same as indices.
- **Schema:** applied **only at collection creation**. On an existing collection, the verb **NEVER touches schema.** A schema change is a DATA MIGRATION (new collection + copy + repoint), because schema is a property of the data: (1) an enforcement boundary — tightening it breaks the next update to an existing non-conforming record; (2) a published interface — read back to tell an LLM the shape so it can build AQL. **NEGATIVE REQUIREMENT, red-bar it:** the verb must never apply or alter schema on a collection that already exists.

`watay` is safe to call anytime; a double `watay` on the same name is harmless (create-if-absent). The call site MAY also check-first (the Indaleko `mime_extractor_example.py` pattern: `lookup_provider_by_identifier` → bind only if absent) — belt and suspenders. (Note: this idempotent-on-repeat contract is the OPPOSITE of `Registrar.register`, which raises on duplicate — op 3 ≠ op 2, hence the distinct verb.)

### Schema generation

Schema is generated from the Pydantic model via Indaleko's envelope, ported verbatim (`indaleko/data_models/base.py:93`): `{"message": ..., "level": "strict", "type": "json", "rule": Model.model_json_schema()}`. `level: "strict"` = validate on every write; it does **NOT** mean "no extra fields" (that is `additionalProperties`, governed by the model's `extra=` config). Models that must keep an open lane (e.g. `ContributedRecord`, already `extra="allow"`) therefore do not emit `additionalProperties: false`. Required-and-conformant core + open extras.

## Naming

**Names route through the obfuscator** — the C0 invariant stands. `registration.py:89` defends this deliberately ("names through the obfuscator from the first pour; 'literal now, obfuscate later' is an illusion of choice"), with a passing test (`test_owned_collection_is_created_under_obfuscated_name`). `watay` maps `name → obfuscated` before create; the physical collection the DB sees is the obfuscated name, the semantic name stays in the registry. The default obfuscator is transparent (dev/test); the fortress supplies the keyed one. (An earlier draft proposed clear names on the reasoning that obfuscated *names* buy little against a breach adversary that reads *values* — true, but that is a reason obfuscating names is *cheap*, not a reason to *drop* a defended, tested invariant. Reversal withdrawn.)

**Two SOURCES of a name, ONE verb** — the (a)/(b) "shared vs per-provider" seam dissolves:
- **well-known / shared** (storage `Objects`, **and** activity `activity_facts`/`activity_anchors`): the semantic name is a constant from the registry; many registrants naming the same string get the **same** handle back (first creates, rest find-and-return — the community-write model, provider identity carried as a *field*). No coordination problem because the name lives in one file.
- **per-provider / minted** (semantic extractors): name generated `prefix + identifier`; collision-free by construction.

`watay` takes a (semantic) name and a definition; it does not care which source produced the name. Both sources feed the same obfuscation-then-create path.

## The three structures (Tony's `IndalekoDBCollections`/`IndalekoCollection`/`IndalekoCollections` split, jobs separated, names deliberately NOT one-letter-apart)

| Job | Indaleko origin | Here |
|---|---|---|
| **Names + definitions registry** (pure data: name → schema/indices/views) | `IndalekoDBCollections` (`db_collections.py`) | `well_known_collections.py` — pure data structure, one place to look (collision-avoidance) and to add a view. **One registry, name→definition** (not names-only — matches Tony's actual practice: the constant sits beside its definition). |
| **Bound collection handle** (created, schema'd, returned) | `IndalekoCollection` (`collection.py`) | the handle `watay` returns |
| **Creator** | `IndalekoCollections` (`i_collections.py`) — eagerly walks the table at startup | `Khipu` / the `watay` verb — **pulls** a well-known definition from the registry **on binding**, NOT an eager startup walk. This is the one thing changed from Indaleko: creation is on-demand, never a static walk. |

`well_known_collections.py` keeps the `IndalekoDBCollections` *shape* (name→definition registry — the ergonomic Tony valued). What is deleted is the eager static *creator* (`IndalekoCollections.__init__`'s walk). Nothing statically walks-to-create.

### Base / subclass split (proven by `indaleko/semantic/examples/mime_extractor_example.py`)

`Khipu`'s generic base owns `watay` + the registry + collection-minting — **and nothing about provider identity.** (Indaleko's `register_provider` FUSES provider-identity and collection-minting into one call; yanantin already split these — provider identity is op 2, `Registrar`'s job. Do NOT re-fuse them. `watay` owns name→definition→handle only.)

Per-type **binding** subclasses (the `Khipu` side) own only:
- a **domain-named entry point** (`bind_semantic_extractor` / `bind_activity_collections` / `bind_storage_collections`) that assembles the collection *definition* (schema/indices/views) and calls `watay`.

The op-2 fields Indaleko folded into `register_provider` — `(Identifier, Name, Description, Version, Record)` and the domain payload (`SupportedMimeTypes`, `ResourceIntensity`, `ProcessingPriority`, `ExtractedAttributes`, validated by `_process_registration_data`) and the **domain queries** (`get_supported_mime_types`, `find_extractors_for_mime_type`, ...) — are **provider-registration** concerns and stay on the `Registrar` (op 2) side, NOT on the `Khipu` binding subclass. A per-type recorder/coordinator drives BOTH: it `Registrar.register`s its identity+payload AND calls its `bind_*` entry point. The split mirrors the vocabulary table; it does not blur it.

`Khipu` is a NEW service, ADJACENT to the existing `core/registration.py:Registrar` — NOT a method grafted onto it (op 3 ≠ op 2; see Vocabulary). A recorder may call `Registrar.register` (its identity) AND `khipu.watay` (its collection); they collaborate, they do not merge. Open item: whether `Khipu` wraps the obfuscator+DB handle directly or reuses `Registrar`'s `_ensure_collection` plumbing — resolve against the real code without conflating the two services.

## Three pressure-test use-cases (DESIGNED here, BUILT later)

The mechanism is designed against all three before any is built, so the interface is not over-fit to one. Each `bind_*` entry point differs only in **name-source** (well-known vs minted) and the **definition** it assembles; the per-type provider identity/payload/queries live on the `Registrar` (op 2) side per the base/subclass split above.

1. **Storage** (the messiest — well-known/shared, community-write, retrofit-onto-live). `bind_storage_collections` `watay`-s well-known `Objects`/`Relationships` (names from the registry) with the storage-object definition. `StorageRecorderBase` owns the *definition* at the tier where the storage shape is constant; the leaf keeps its own recorder identity (provenance) and writes through the returned handle, naming no collection (`[[project_ownership_at_the_tier_where_the_fact_stops_varying.md]]`).
   **BLOCKING DEPENDENCY:** the storage-object *definition* is **placeholder until #17's uniform storage object exists.** Today `core/contribution.py:ContributedRecord` is intentionally THIN (`source` + `raw` + open tail) and is NOT the uniform object; `tests/red_bar/test_uniform_storage_object.py` is honestly red. So #31's `URI`/`ObjectIdentifier` unique indices, #3's timestamp persistent+inverted indices, and the Hamut'ay arangosearch view (index *shape* per `indaleko/db/db_collections.py:140-330`; Pukara owns label-stability, do NOT port UUID index keys) are the storage definition's *eventual* contents — they cannot be finalized until the model with declared `URI`/`ObjectIdentifier`/timestamp fields lands. The storage use-case validates the `watay` INTERFACE against a well-known/shared customer; its concrete definition waits on #17. (`[[project_31_17_temporal_are_one_missing_object.md]]`)
2. **Activity** (a SECOND well-known/shared case — NOT per-provider). CORRECTED from an earlier draft that wrongly imported Indaleko's per-provider minting: yanantin activity is **two shared collections**, `activity_facts` + `activity_anchors`, indexed by `(provider_id, timestamp)`, with facts as schema-agnostic shared observations (`activity/backends/arango.py:30,81`, `activity/models.py:36`). So activity is the SAME shared-collection shape as storage, not the minted shape — it `watay`-s two well-known names from the registry, provider identity carried as a field. This replaces the static `_SEMANTIC_COLLECTIONS` tuple with registry entries + `watay`. Anchors and the `(provider_id, timestamp)` index are part of the activity definition; nothing about temporal queries or `ActivityStreamStore` changes — the collections stay shared, they just get *bound* through `Khipu` instead of created by a static tuple. (Activity being shared, not minted, *strengthens* the design: TWO shared customers prove the well-known path; semantic alone proves the minted path.)
3. **Semantic** (the muddle in the middle — Indaleko's never-fully-converted path; the per-provider/MINTED case). `bind_semantic_extractor` mints a `prefix + identifier` name and assembles the extractor-collection definition (the op-3 binding part). The op-2 side — the extractor's provider-registration with payload `SupportedMimeTypes`/`ResourceIntensity`/`ProcessingPriority`/`ExtractedAttributes` and the mime-type queries (`get_supported_mime_types`, `find_extractors_for_mime_type`) — stays on `Registrar`. The worked example (`indaleko/semantic/examples/mime_extractor_example.py`) shows them FUSED in one `register_semantic_extractor(...) -> (record, collection)` call; yanantin keeps them split (Registrar + Khipu), the coordinator drives both. This is the use-case where the op-2/op-3 split is easiest to accidentally re-fuse — the example itself fuses it.

If `watay` + the base/subclass split serves all three on paper — two shared (storage, activity) + one minted (semantic) — the interface is validated across both name-sources.

## Testing

- **Red bar:** `watay` must NOT apply/alter schema on a pre-existing collection (the negative requirement). Construct a schema-less collection, `watay` a now-schema-bearing definition for that name, assert the existing collection's schema is untouched (change is a migration, not an init side-effect).
- **Red bar:** write a record missing a required field to a NEWLY-created schema-bearing collection, assert the DB refuses it (`[[feedback_stronger_tests_never_an_error.md]]`).
- **Green:** create-if-absent collection/index/view; a repeated `watay` on the same name is a no-op; dropped index is recreated on rerun.
- **Green:** a record with extra undeclared fields IS accepted on an `extra="allow"`-derived schema (open lane intact).
- **Green:** two callers `watay`-ing the same well-known name get the same handle (community write); two minted (`prefix+identifier`) callers get distinct collections.
- **Green:** the name `watay` receives is obfuscated before create — the physical collection is the obfuscated name, the semantic name does not exist as a collection (honors the C0 invariant; mirrors `test_owned_collection_is_created_under_obfuscated_name`).
- All against live `apacheta_test` (`[[feedback_no_mock_databases.md]]`).

## Explicitly deferred (named, not silently dropped)

- **Build** of the three use-cases — one instance each (parallel or serial, decided at plan time). This spec DESIGNS; it does not build.
- **Migration of the existing static creators** (activity `_SEMANTIC_COLLECTIONS`, tensor type-map) onto `watay` — follow-on; closing this is what finishes #1.
- **Schema-retrofit migration** of the live schema-less `Objects`/`activity_facts` collections — its OWN later pour (new schema-bearing collection + copy + repoint), with a data-surfacing step that discovers the non-conforming rows that were being silently accepted (ROOT: that discovery is product, not cleanup). NOT part of the mechanism pour.
- **Names-registry as the only collision detector** (chosen over schema-compare: a shared *schema* is correct stacking, not a collision; the real collision is name-reuse, caught at declaration as a one-file merge conflict).

## Open items to resolve during implementation (flagged)

- Whether `Khipu` wraps the obfuscator + DB handle directly or reuses `Registrar`'s `_ensure_collection` plumbing — without conflating the two services (op 3 ≠ op 2). Driven by the real `Registrar`/obfuscator code.
- The storage use-case is BLOCKED on #17 (uniform storage object). Decide at plan time whether to design `Khipu` against a placeholder storage definition now, or sequence #17 first so storage validates against its real definition. Activity + semantic do not have this block.
- (Resolved, was an open item: collection names route THROUGH the obfuscator — C0 invariant honored, not reversed. See Naming.)
