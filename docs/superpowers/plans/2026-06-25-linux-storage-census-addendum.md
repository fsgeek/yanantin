# Linux Storage Census — Addendum to the 2026-06-18 Recorder→Collection-Mapping Plan

> **Status:** Design addendum, written 2026-06-25 after a fresh design pass with Tony.
> **Supersedes specific decisions in** `2026-06-18-recorder-collection-mapping-linux-local.md` —
> does NOT replace it. That plan's Tasks 2 (registrar owns edge collection) and 3
> (opacity red-bar) stand unchanged. This addendum corrects three decisions that
> went stale because **#17 (the uniform StorageObject) landed since that plan was
> written**, and adds the census/reconciliation framing that the 06-18 plan predates.
>
> **For the build instance:** read the 06-18 plan first for the TDD/Codex structure
> and the registrar-edge mechanism. Then apply the corrections below. Codex authors
> all red-bar tests; builder makes them pass; live `apacheta_test`, no mocks.

## Why this addendum exists (the three drifts)

The 06-18 plan was written when #17 was still red. It is no longer.
Grounded tonight against the live tree:

- `src/yanantin/collector/storage_object.py` — **`StorageObject` is BUILT** (open lane
  `extra="allow"`, `raw` save-it-all, uniform `uri`, `source`=provider, flat POSIX
  timestamps `created/modified/accessed/changed`, `object_identifier`, `semantic_attributes`).
- `src/yanantin/core/well_known_collections.py` — **`Objects` is BOUND to the real
  `StorageObject` schema** with indices `obj_id_idx` (unique on `object_identifier`),
  `uri_idx`, and `modified_idx` (commented: "the temporal axis, the search-space reducer").
- `Relationships` edge: creation works (`watay edge=True`); schema **intentionally
  `schema=None`** — binding `ProvenanceEdge` (extra="forbid") to it BROKE live inserts
  in A1. Landmine already mapped: do NOT bind a forbid-edge schema to Relationships.

### Drift 1 — contribute `StorageObject`, NOT a parallel `ContributedRecord`

The 06-18 plan (Task 1, lines 7/16/28) builds `ContributedRecord` as a "thin
provenance doc, explicitly NOT the #17 StorageObject." **Reverse this.** #17 landed;
`Objects` validates `StorageObject`. Contributing a second, competing shape would
manufacture exactly the silo-fracture the whole storage chain exists to close.

- **DELETE** the `ContributedRecord` half of 06-18 Task 1. Keep `ContributionTarget`
  (the `{name, kind, naming}` mapping entry — still correct and still needed).
- The recorder contributes **`StorageObject`** instances into `Objects` via the
  registrar's owned-collection seam. `StorageObject.to_contribution_fields()` already
  exists (`model_dump(mode="json")`) — it is the `**fields` for `Registrar.contribute`.
- **Identity (Tony's Q2 call, 2026-06-25):** mutable, `object_identifier =
  uuid5(source, uri)`. Re-observation of the same (source, uri) UPSERTS — the
  `obj_id_idx` unique index makes this an update, not a collision. NO immutability /
  versioning now: most storage has no versioning, so immutable-StorageObject is
  theater; versioned sources (the "accidental" providers — Discord/Slack/Outlook —
  re-presenting one attachment at many uris) are where identity gets hard, and that
  case is DEFERRED to where it actually bites. Keep the shape; defer the policy.

### Drift 2 — the load-bearing edge is directory→child CONTAINMENT, not recorder→object

The 06-18 plan's only edge is `recorder → object` (`relation_type="records"`). That
provenance edge is fine to keep, but it is NOT the edge that matters. The telos —
files-seen-via-relationships, not via path-walk — needs **directory → child
containment** edges, and Tony's program acceptance-test query
(see memory: cross-silo planning-notes with temporal→provenance inference) is built
on traversable containment + the temporal axis.

- Add **containment edges** into `Relationships`: each file/dir `StorageObject` gets
  an edge from its parent directory's `StorageObject`. Directories ARE `StorageObject`s.
- **Containment ≠ provenance** (Tony's lean, builder-confirmed): give containment its
  OWN `relation_type` (e.g. `"contains"`), distinct from the `"records"`/provenance
  relation. Reusing one relation-type for two relations is the "three-registrations-
  under-one-word" overload again. They may share the `Relationships` collection; they
  must not share semantics.
- Canonical `str(UUID)` endpoints are mandatory (06-18 plan's obfuscator landmine,
  line 18 / Task 5 traversal check) or OUTBOUND traversal dangles.

### Drift 3 — the collector is PURE CENSUS; reconciliation/activity is deferred exhaust

The 06-18 plan predates tonight's keystone. Capture it so the build doesn't re-fuse
what should stay separable:

- The **storage collector** walks (`os.walk`/`lstat`, ~a dozen lines) and emits a
  full-census of `StorageObject`s **every run** — timeless, no `since`, no diff, no
  state file. The walk is trivial; do not over-build it.
- **Reconciliation** (previous-state vs current-observation → change-events) is NOT
  this pour. Activity data is the BYPRODUCT of reconciliation, owned by the activity
  lane (where it varies per-source: USN journal on Windows, Hadi's Mac monitor, walk-
  diff on Linux). The census stops varying across platforms → owned by storage.
- **Do NOT copy** `collector/activity/linux/collector.py` (`FsIncrementalCollector`).
  Its `_scan_volumes` walk IS the storage walk, duplicated because the storage layer
  it should sit on did not exist yet — it is a fossil of this missing foundation, the
  same way `../llm-memory` is a fossil of the missing shared view. Build the census
  fresh and minimal; the consolidation of activity-onto-storage is a LATER pour.
- **Deliberately leave reconciliation un-extracted.** Per the memory
  "extract on the second instance, not the first": do not pre-factor a reconciler
  utility now. The SECOND source (USN reader / Mac monitor / synthetic twin) reveals
  the real seam. One clean piece extracted from one example is a guess with good
  posture. Hold the discomfort of un-factored code; it is discipline, not debt.

## What survives from the 06-18 plan UNCHANGED

- **Task 2** — `Registrar` owns an edge collection (`owned_edge_collection`,
  `contribute_edge`, `list_edge_contributions`, public `owned_collection_name` /
  `owns_edge_collection` seams). Correct as written.
- **Task 3** — registrar-opacity red-bar (round-trips `contributes_to` unchanged;
  source contains none of `contributes_to`/`well_known`/`dynamic`). Correct as written.
- **Task 4** — `LinuxStorageRegistration` registers recorder + collector-by-proxy,
  declares `contributes_to: [{Objects,doc,well_known},{Relationships,edge,well_known}]`.
  Correct — only the contributed SHAPE downstream changes (StorageObject, Drift 1).
- **Task 7** — fail-stop on a `well_known` target with no owning collection (never a
  silent mint; mint is the `dynamic` path only). Correct.
- **Task 8** — end-to-end visibility through `python -m yanantin.core`. Correct.
- TDD discipline, Codex test-authorship, Yanantin-signed commits, OTS sweep, red-bar
  floor intact (do NOT regress other gates — but #17's gate is now legitimately
  green-able by THIS pour, since we ARE contributing StorageObjects; confirm whether
  `tests/red_bar/test_uniform_storage_object.py` should flip and coordinate that
  deliberately, not as a side effect).

## Build order (revised, step 0 first)

0. **Find the contribute-StorageObject write seam.** Grep located `store_tensor` and
   `store_provenance_edge` on the arango backend but NO `contribute(StorageObject)→Objects`
   write yet; the 06-18 plan routes contribution through `Registrar.contribute` /
   `contribute_edge` (the owned-collection path). CONFIRM that path writes a full
   `StorageObject` doc (not just a thin doc) and that `_key`/`object_identifier`
   forwarding works, BEFORE writing the collector. This gates everything.
1. 06-18 Task 2 (edge ownership) + Task 3 (opacity) — unchanged.
2. Drift-1 shape: keep `ContributionTarget`; contribute `StorageObject` (built);
   identity `uuid5(source,uri)`, upsert.
3. Linux storage **census** collector (pure walk) + its synthetic twin (gh #27),
   **fixture-tree first** (ground-truth countable), then a real volume.
4. Recorder contributes `StorageObject`s into `Objects` + **containment** edges
   (`relation_type="contains"`, canonical endpoints) into `Relationships`,
   contemporaneously (Tony's Q3: cheap at construction, so do it now).
5. 06-18 Tasks 6/7/8 (attach-not-mint, fail-stop, CLI visibility) — driven by the
   StorageObject shape.
6. Reconciliation/activity-emit: **named and deferred** (Drift 3). Write the deferral
   into the issue so the next instance doesn't read un-factored code as a mess to fix.

## Lineage

Sequel to `2026-06-17-recorder-collection-mapping-design.md` (spec) and
`2026-06-18-recorder-collection-mapping-linux-local.md` (plan). Design pass
2026-06-25. Memories that ground the corrections:
`the-projectioncontainer-collapse-is-one-reflex-wearing-three-costumes`,
`extract-on-the-second-instance-not-the-first-premature-decomposition-wears-good-engineering-clothes`,
`the-programs-acceptance-test-in-tonys-voice-cross-silo-planning-notes-query-with-temporalprovenance-inference`,
`project_ownership_at_the_tier_where_the_fact_stops_varying`,
`project_31_17_temporal_are_one_missing_object`.
