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

### Front A — file tenant — COLLECTORS REAL; the batch pipeline's BACK HALF is MISSING (not anti-built — HALF-built)
*(Tony's correction 2026-06-15, then a second correction: this is NOT "the recorder writes the
wrong final shape." It is "Indaleko's batch model was never fully ported." Indaleko's path is
collector→file → recorder→file → **`arangoimport` fans out into one queryable doc per file**.
One-at-a-time DB writes are fatally slow at millions of entries — the batch/bulk model exists
precisely to make the OOBE FAST. yanantin ported the FRONT half, not the back half.)*
- **Collectors real; wranglers real.** `collector/wranglers.py` = the collector→recorder
  decouple (Direct/Batch/Queued). This is the build-path simplifier that keeps new tools cheap
  — the dynamic-extensibility requirement. SOUND, matches intent.
- **The MISSING STAGE:** there is NO recorder→DB fan-out. `grep arangoimport` → nothing.
  `recorder/storage/local/linux/recorder.py:57-66` `record()` `json.dumps` ALL entries into ONE
  terminal `TensorRecord` — NOT because blob-per-snapshot is the intended shape, but because the
  bulk-import back half doesn't exist, so `record()` had to terminate *somewhere*. The blob is a
  SYMPTOM of the missing stage, not a wrong design choice. **DO NOT "fix" it by writing
  one-document-per-file in a loop — that rebuilds the one-at-a-time slowness Indaleko's batch
  model exists to avoid.**
- **Three regimes (Tony) need different write-paths, same build surface (wranglers):**
  (1) COLD-START / full load → recorder→file→`arangoimport` (throughput-first; the OOBE-fast
  path that does NOT exist yet). (2) INCREMENTAL (the steady-state baseline; deltas, lighter
  path may be per-record). (3) LIVE/MONITORED (a monitoring service feeds changed files into
  the incremental path).
- **No Indaleko corpus is loaded.** The file tenant is NOT a queryable database yet.
- **Uniform storage object (#17): ABSENT** — `collector/storage_object.py` does not exist
  (orphan `.pyc`); `tests/red_bar/test_uniform_storage_object.py` HONESTLY RED. **#17 is the
  PER-DOCUMENT ROW SHAPE that `arangoimport` fans out INTO** — not "what record() emits one at a
  time." Same stone, correctly placed in a BATCH pipeline, not a streaming one. Without it,
  cross-silo temporal join is STRUCTURALLY IMPOSSIBLE (filesystem `modified` and Dropbox
  `modified_time` never join).
- Collectors: 4/6 have synthetic twins; **openrouter and machine_config MISSING twins** (#25).
- Temporal: facts carry UTC timestamps; DuckDB has `(provider_id, timestamp)` index +
  `query_range`/`query_latest`. **Pruning is DESIGNED (comments) but not runtime.** And it's
  per-silo — no cross-silo `when` until the storage object exists.

## THE MAP (route, with the two fronts NOT gating each other)

**Substrate (mostly done — verify, don't rebuild):**
- S1. Confirm the access hook + `ProvenanceEdge` + open-record scoping are the floor both
  tenants stand on. (Largely a verification + small-gap task, not a build.)

**Front A — file tenant (collectors+wranglers real; batch back-half + DB + pruning unbuilt):**
- A1. **Port the uniform storage object (#17)** — the per-document row shape (4 named-UUID
  timestamps, open `semantic_attributes` lane, raw blob retained). Turns the red bar green.
  This is the shape the bulk import fans out INTO. GATING ARTIFACT for cross-silo `when`.
- A2. **Build the batch back-half: recorder→file→`arangoimport` fan-out** into one #17 document
  per file. This is the OOBE-fast cold-start path. The blob-tensor `record()` is RETIRED here,
  but NOT by per-record loops — by bulk import. (Then the incremental + live paths as regimes 2/3.)
- A3. Stand up the file tenant as an actual database (the `arangoimport` target = its own DB).
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
