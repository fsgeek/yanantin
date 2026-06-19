# Storage-Recorder Tier Spine with Base-Owned Collection Definitions

**Date:** 2026-06-18
**Status:** SUPERSEDED by `2026-06-18-dynamic-collection-registration-design.md`.
**Why superseded:** This spec centered the design on the *storage* recorder tier — wrong center. Walking the code with Tony revealed the storage `Objects` mess is one instance of a project-wide gap: the dynamic collection-registration primitive (gh #1) was never built, so three subsystems (storage, activity, semantic) each hand-rolled partial static creators. The correct center is the dynamic-registration mechanism, with storage/activity/semantic as three pressure-test customers. The ownership-rule reasoning and the index-shape census below remain valid INPUT to the successor spec; the "storage is the spine" framing is the false thing, cut here per declared-loss-is-debt.

**Issues subsumed (by the successor):** #1 (dynamic registration — the CENTER, not partial), #17, #31, #3, Hamut'ay ArangoSearch view.

## Problem

The storage-recorder tier has no spine. Concretely, verified against live code 2026-06-18:

- `recorder/storage/local/linux/registration.py:18-19` holds `STORAGE_OBJECTS = "Objects"` and `STORAGE_RELATIONSHIPS = "Relationships"` as **leaf-level module constants** — a shared-shape fact stranded in a leaf.
- There is **no** `recorder/storage/base.py`, **no** `recorder/storage/local/base.py`, **no** `recorder/storage/cloud/base.py`. The directories are packaging only.
- `LinuxStorageRegistration` is a **free-standing class** that does not inherit the existing `recorder/base.py:RecorderBase`.
- The `Objects`/`Relationships` collections are **created by the caller** (whoever constructs the `Registrar` with `owned_collection="Objects"`). The leaf only *checks* existence and raises (`contribute_snapshot`, the `well_known never mints` guard). **No component owns collection existence.**
- Collections carry **no schema** (live: all `schema: none`), so the partition rule (shared-schema sources share a collection) is asserted in prose and enforced by nothing. See `[[project_no_arango_schema_validation_on_any_collection.md]]`.

When a Windows or Mac local recorder arrives, the shared `Objects`/`Relationships` facts either duplicate, force an absurd Mac→Linux import, or finally get lifted to the tier base — the third being where they belonged from the first recorder.

## Design rule (load-bearing)

**A fact is owned at the tier where it stops varying.** (Tony, 2026-06-18 — `[[project_ownership_at_the_tier_where_the_fact_stops_varying.md]]`.) The inheritance chain exists so each fact lives at the height where it's constant.

- **Recorder identity + registration** varies per-leaf (Linux is a unique data source; Mac gets its own ID). → owned at the **leaf**. This is a provenance data-source guide; it belongs in the leaf. Registration **folds into the recorder**; the separate `LinuxStorageRegistration` collaborator collapses into the leaf recorder.
- **`Objects`/`Relationships` collection definition + creation** is invariant across all storage recorders. → owned at the **top of the storage stack** (`StorageRecorderBase`).
- **Objects *within* the collection** are a **community effort** — different recorders write into one shared collection, provider identity carried as a *field*, not the collection name. The registrar already encodes this (`core/registration.py:97-102`). What was missing is that nobody owned *creating* that shared collection at the height where it's common. The base closes the loop the registrar opened.

## Structure

```
StorageRecorderBase                  (recorder/storage/base.py)
  owns: Objects/Relationships identity + schema + indices + views;
        ensure-exists-or-create-collection; collection_definitions() seam
  │
  ├─ LocalStorageRecorderBase        (recorder/storage/local/base.py)
  │     local-storage source behavior shared by linux/mac
  │     └─ LinuxStorageRecorder      (recorder/storage/local/linux/recorder.py)
  │        normalizer + its OWN recorder identity/registration (provenance guide);
  │        references base-owned collection identity, declares no name constant
  │        (MacStorageRecorder slots in beside it later)
  │
  └─ CloudStorageRecorderBase        (recorder/storage/cloud/base.py)
        cloud-storage source behavior shared by dropbox/etc.
        └─ DropboxStorageRecorder    (recorder/storage/cloud/dropbox/recorder.py)
           normalizer + own identity/registration
```

Definition lives at the shape-tier (top); source behavior at the source-tier (local/cloud); normalizer + identity at the leaf.

**Relationship to existing `recorder/base.py` (corrected after walking the code 2026-06-18):** `recorder/base.py` holds **two** bases that are NOT alternatives — they are two write *targets* for the same source data, distinguished by the store binding:

- `RecorderBase` → `ApachetaInterface` (`apacheta/interface/abstract.py:29`) → the **tensor/composition** database (`store_tensor`, `store_composition_edge`, `store_record`).
- `FactRecorderBase` → `ActivityStreamStore` (`activity/store.py:19`) → the **temporal fact stream** (`store_fact`, append-only).

The same source subclasses BOTH in parallel (e.g. `FilesystemRecorder` + `FilesystemFactRecorder`, `DropboxRecorder` + `DropboxFactRecorder`). Identical method *signatures*, different *sinks*. (The docstrings call both "generic data→storage," which flattens this real distinction — do not trust that phrasing.)

**Crucially, the storage spine this spec builds is a THIRD path, not a subtype of either base.** The thing that writes `Objects`/`Relationships` today is neither `RecorderBase` nor `FactRecorderBase` — it is `LinuxStorageRegistration` → `Registrar.contribute()`, writing thin provenance docs into `Objects`. So `StorageRecorderBase` is **orthogonal** to `RecorderBase`/`FactRecorderBase`: it owns the collection-definition + registration/provenance-contribution path. A storage leaf may *also* drive a `RecorderBase` (tensors) and/or `FactRecorderBase` (facts) for the same source — those are separate concerns on separate sinks. Do NOT shoehorn `StorageRecorderBase` under `RecorderBase`; it governs a different write path (the registrar/Objects path), and forcing inheritance would conflate the tensor sink with the provenance-collection sink.

## Collection ownership

On register (or first contribution), `StorageRecorderBase` ensures `Objects`/`Relationships` exist. **If absent, it creates the collection and installs schema, indices, and views** — so whichever leaf runs first, the collection is correctly shaped. This replaces both the leaf's check-and-raise and the caller's construct-with-`owned_collection`. Idempotent: existing collection ⇒ no-op (do not drop/recreate live data).

## Schema

Generated from the Pydantic model via Indaleko's envelope mechanism, ported **verbatim** (`../indaleko/data_models/base.py:93`):

```python
{"message": "...", "level": "strict", "type": "json", "rule": Model.model_json_schema()}
```

- `level: "strict"` governs **when** the rule applies (validate on every insert/update) — it does **NOT** mean "no extra fields" (Tony, 2026-06-18). Extra fields are governed solely by `additionalProperties` inside the rule.
- The model whose `model_json_schema()` becomes the `Objects` rule is **`ContributedRecord`** (`core/contribution.py:29`), which is **already `extra="allow"`** → `model_json_schema()` does **not** emit `additionalProperties: false` → the open semantic-attribute lane stays open. The open-lane guarantee lives in the **model config**, not the schema mechanism.
- Result: declared core fields (identity, ISO-TZ timestamps) are **enforced to conform** at the DB boundary (Tony's one hard rule — `[[project_no_arango_schema_validation_on_any_collection.md]]`), while undeclared fields pass through. Required-and-conformant core + open extras, at once.
- `FileEntryData` (collector-side, `extra="forbid"`) is NOT the `Objects` model — it lives inside `raw`. Do not derive the `Objects` schema from it.

## Indices / views

Port the index **shape** from Indaleko's `db_collections.py` (`../indaleko/db/db_collections.py:140-330`) — NOT its per-field UUID index keys (Pukara owns label-stability now; `[[project_indaleko_posix_semantic_attribute_normalizer.md]]`). Collection/field names go through the obfuscator. Shape to port:

- `URI` unique persistent — #31's (machine,URI) detection index.
- `ObjectIdentifier` unique persistent ("file identity") — #17's stable identity.
- timestamp fields: persistent (range → #3 temporal axis) + inverted + `sparse: True`.
- arangosearch `view` with analyzers — Hamut'ay's honest-BM25 need, ranking swappable via search-alias.

These land here, subsumed — not built as four separate issue-patches.

## Definition seam (future DB-served definitions)

The base exposes collection definitions behind a method (`collection_definitions()` or equivalent) it calls internally. Today the definitions are **code**. Tony's stated future direction: pull them from the database. The seam makes that a substitution, not a rewrite. **We do NOT** port Indaleko's centralized `db_collections.py` table, and **we do NOT** build the DB-served version now (YAGNI). We place the seam only.

## Testing

- **Red bar (must be honestly red before the fix):** construct the base, write a record missing a required field (e.g. no timestamp) to `Objects`, assert the DB **refuses** it. Fails today (schema-less collection accepts anything). `[[feedback_stronger_tests_never_an_error.md]]`.
- **Green:** base creates `Objects`/`Relationships` with schema+indices+views when absent; idempotent when present.
- **Green:** a record with extra (undeclared) fields IS accepted (open lane stays open) — guards against accidentally re-imposing `additionalProperties: false`.
- **Green:** Linux leaf, reparented, contributes through base-owned collection identity (no leaf name constant); existing `contribute_snapshot` behavior preserved.
- **Green:** existing collection-stacking / two-DB isolation red bars still pass (no regression in the registrar contract).
- All tests run against live `apacheta_test` (`[[feedback_no_mock_databases.md]]`).

## Build sequencing (resolved at plan time)

One spec, whole shape committed. Implementation plan sequences into independently-green lifts:

1. **Local spine:** `StorageRecorderBase` + `LocalStorageRecorderBase` + reparent `LinuxStorageRecorder` + base-owned collection/schema/index/view creation + the red bar. Lift the `Objects`/`Relationships` constants out of the linux leaf.
2. **Cloud mirror:** `CloudStorageRecorderBase` + reparent `DropboxStorageRecorder` against the now-proven base. (Dropbox does not currently hardcode `Objects`/`Relationships` — verified 2026-06-18 — so this lift is additive, not a rip-out. Dropbox stays untouched until this step.)

## Open items to resolve during implementation (flagged, not hand-waved)

- (a) Exact placement of `StorageRecorderBase` relative to `RecorderBase` (under vs beside) — driven by the real write-path contract.
- (b) Whether `ContributedRecord` needs additional declared core fields (promoted identity / canonical timestamps) for the schema's `required` set to be meaningful — touches #17/#31. The schema is only as strong as the model's declared core. Resolve which fields are `required` when porting the index shape (URI, ObjectIdentifier must be present to index uniquely).
