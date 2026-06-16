# Roadmap — Here to There

*2026-06-15. The route from current state to the north star (`docs/north-star.md`):
the simple cross-tenant find loop closing. Distances established by SCOUTING THE CODE,
not trusting the issue ledger (which the 2026-06-15 coherence scan proved lies about what's
built). Two scouts swept Front A, Front B, and the substrate; findings below are verified
against files, with absence reported as absence.*

## The destination (restated, concrete)

ONE AI instance translates ONE real episodic query ("that thing around when we discussed X")
into a timestamp-pruned six-factor find that reaches across into the file tenant. The loop
closing IS the experiment — the uncertain thing. Everything below it is road.

## The shape: two fronts + a common substrate + one seam (Tony's cut, code-confirmed)

The per-tenant-database decision means the two halves are **independently buildable** — two
roads that cross once, at the seam. The seam is deliberately simple-first
(`docs/north-star.md` §cross-tenant seam). The scouts CONFIRMED the common substrate
substantially exists, so this is not aspirational.

## GROUND TRUTH (verified 2026-06-15)

### The common substrate — IN GOOD SHAPE ✓ (the good news)
- `ApachetaInterface` (`apacheta/interface/abstract.py`): clean, backend-neutral, 3 backends
  implement it (InMemory, DuckDB, Arango). Generic `store_record`/`store_provenance_edge`.
- **Access-control hook EXISTS** (`abstract.py:46-52` `check_access()` → always True in v1, but
  the seam for per-tenant enforcement is already cut).
- **`ProvenanceEdge` BUILT** (`models/provenance_edge.py`): cross-collection (`_from`/`_to` =
  `collection/key`), free-string `relation_type`, immutable, carries `ProvenanceEnvelope`.
  This is the exact intra-DB ancestor of the future cross-tenant edge.
- Open-record queries already scoped by `author_instance_id` / `lineage_tag`.
- Entanglement is layered, not welded: Q1–Q20 tensor-specific queries sit ATOP the floor;
  a file tenant can stub them (`NotImplementedError`) and use the generic floor.

### Front B — AI-memory tenant — FURTHEST ALONG
- find: **content-axis-only, BUILT** (`llika/models.py:87-96` v1-scope comment; naive full
  scan + plaintext substring in `arango.py:452-509`). filter/structure/window **declared
  absent, not stubbed**. `FindResult` returns EXACT `total_matched` (count-at-boundary held).
- Per-instance database (#13): **DECIDED, UNBUILT.** ALL instances share one DB + one app
  credential pair; `author_instance_id` is ASSERTED, NOT verified. Accretion guards installed
  (`test_single_principal_accretion.py`, commit da34519a) — `authorship_verified` defaults
  False, no yanantin path may set it True. Structure HELD, enforcement deferred.

### Front A — file tenant — ONLY THE COLLECTORS ARE REAL; EVERYTHING DOWNSTREAM IS UNBUILT OR ANTI-BUILT
*(Tony's correction 2026-06-15: "everything downstream from the machine config isn't real yet."
Verified — and it's worse than "absent": the recorder that exists writes the WRONG shape.)*
- **Collectors are real** (produce snapshots/listings). But their DESTINATION is not.
- **The recorder ANTI-PATTERN:** `recorder/storage/local/linux/recorder.py:40-79` `record()`
  takes a whole `FilesystemSnapshot` and `json.dumps` ALL entries into ONE strand of ONE
  `TensorRecord` (`entries_json`, lines 57-66). At 28.5M files this is **one tensor holding a
  28.5M-entry JSON blob** — un-findable, un-prunable, un-addressable. It is `find /` in a
  database costume: the EXACT disease the project exists to cure. The recorder must be
  REPLACED, not extended.
- **No Indaleko corpus is loaded. No loader exists.** No "index the 28.5M" step. The file
  tenant is NOT a queryable database.
- **Uniform storage object (#17): ABSENT** — `collector/storage_object.py` does not exist
  (orphan `.pyc` only); `tests/red_bar/test_uniform_storage_object.py` is HONESTLY RED.
  **Crucially: #17 is not an upstream prerequisite OF the recorder — #17 is WHAT THE RECORDER
  SHOULD EMIT (one queryable record per file, not a blob per snapshot).** Porting the storage
  object and fixing the recorder are the SAME stone. Without it, cross-silo temporal join is
  STRUCTURALLY IMPOSSIBLE (filesystem `modified` and Dropbox `modified_time` never join).
- Collectors: 4/6 have synthetic twins; **openrouter and machine_config MISSING twins** (#25).
- Temporal: facts carry UTC timestamps; DuckDB has `(provider_id, timestamp)` index +
  `query_range`/`query_latest`. **Pruning is DESIGNED (comments) but not runtime.** And it's
  per-silo — no cross-silo `when` until the storage object exists.

## THE MAP (route, with the two fronts NOT gating each other)

**Substrate (mostly done — verify, don't rebuild):**
- S1. Confirm the access hook + `ProvenanceEdge` + open-record scoping are the floor both
  tenants stand on. (Largely a verification + small-gap task, not a build.)

**Front A — file tenant (the whole leg is unbuilt; only collectors are real):**
- A1. **Port the uniform storage object (#17) AND replace the blob-recorder — same stone.**
  The storage object (4 named-UUID timestamps, open `semantic_attributes` lane, raw blob
  retained) is WHAT `record()` SHOULD EMIT: one queryable record per file, not one JSON blob
  per snapshot. Turning the #17 red bar green and killing the `entries_json` anti-pattern
  (`recorder/storage/local/linux/recorder.py:57-66`) are the same task. GATING ARTIFACT.
- A2. Normalize ≥2 collectors (filesystem + one cloud) to the storage object → prove the
  cross-silo temporal join works on real shapes.
- A3. Stand up the file tenant as an actual database (loader OR live-collect into its own DB).
- A4. Runtime temporal pruning over the file tenant (the anti-RAG strand made real).
- (A5. Close the synthetic-twin gaps #25 — needed for trustworthy eval, parallel to A1–A4.)

**Front B — AI-memory tenant (furthest along):**
- B1. Realize the per-instance database (#13) — turn DECIDED into BUILT. This is what makes
  "this instance has THIS memory" falsifiable and gives the loop a real second tenant.
- B2. (find's NOW-debts as needed: #15 principal-on-query-facts, #16 count pushdown.)

**The seam (last, smallest — only after both fronts can stand alone):**
- X1. The simple cross-tenant edge: content-hashed + attributed + LOGGED, grant-id slot null
  (kin-trusted, no capability). Descends from `ProvenanceEdge`; NOT the same row type
  (carries content-hash + source-tenant + grant-slot).
- X2. **The experiment:** one episodic query → temporal-pruned find in Front B's memory →
  cross-tenant hop into Front A's files → does the loop close? This is the uncertain thing
  the whole road exists to reach.

## Critical-path read

The single most gating artifact is **A1 (the uniform storage object, #17)** — it's an
honestly-red test, it's the trailhead of the longest leg, and cross-silo `when` (the anti-RAG
keystone) is structurally impossible without it. **B1 (per-instance DB, #13)** is the other
load-bearing unbuilt piece and gates the experiment's *falsifiability*. The two do NOT gate
each other — they can be walked in parallel by separate sessions/instances, which is exactly
the affordance the per-tenant-database architecture was supposed to buy. The seam (X1/X2) is
deliberately last and deliberately cheap.

## Drift-guard for the next instance

The coherence scan mis-read Front A's collector work (#24/#25/#26) as DRIFT AWAY from find.
Against this map it reads true: **collectors are the first piers of the file-tenant bridge,
on-path but early.** Do not "correct" Front A work back toward find — it IS the road. And do
not re-sequence A1/B1 into a false dependency chain; they're parallel by design.
