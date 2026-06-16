# Three Spaces and the Common Core

*2026-06-16. Tony's decomposition of the path forward: identify the common core, find
here→need, then bifurcate into three directions. VERIFIED against code — the bifurcation has
ALREADY happened in the codebase, drawn at the right altitude; nobody had read the three stacks
TOGETHER to see it (same unread-coherence as the issue ledger). Supersedes the looser "two
fronts" framing in `docs/roadmap-here-to-there.md` (which conflated joint-space into "the seam"
and called the human side "files" when it is really ACTIVITY).*

## The three directions (Tony)

1. **AI-memory space** — the Hamut'ay instances' queryable self. Low-volume, AUTHORED,
   immutable, high-value. Write-hot/revise-shed at the working-set; immutable once stored.
2. **Joint storage working space** — the SHARED place where human and AI meet over the same
   artifacts; where the find LOOP closes. Not merely an edge — a *space*.
3. **Human-activity space** — human memory AS DEFINED BY ACTIVITY (Vianna: who/what/WHEN/
   where/why/how). NOT "the file tenant" (static index) — the ACTIVITY STREAM (what the human
   DID, when, in order). Files are the ARTIFACTS activity leaves behind, not the thing itself.
   High-volume, temporal, append-only, machine-generated. The *when* dominates (anti-RAG pruner).

## The common core — VERIFIED, drawn at the CONTRACT level (not the interface)

The architecture already cut this correctly. NOT "everything shares `ApachetaInterface`"
(too high — that's an AI-memory-specific surface). NOT "separate stacks" (too low). The shared
floor is the **contract primitives**:
- `apacheta.interface.errors` — `ImmutabilityError`, `NotFoundError` (the append-only/immutable
  contract). Activity's `ActivityStreamStore` explicitly reuses these (`activity/store.py:6`).
- `apacheta.storage_obfuscator` — the label-obfuscation boundary (activity's arango backend
  imports it, `activity/backends/arango.py:27`).
- `ProvenanceEnvelope` / `ProvenanceEdge` — authorship + cross-collection edges.
- The find mechanism + temporal pruning (the *when*-as-search-space-reducer is shared by all
  three; AI-memory keys on cycle-time, activity on wall-clock, joint on both).
- #17 uniform storage object — the one addressable per-document shape all three must be findable
  by, or the loop can't cross between them.

Above that thin floor, the three spaces use DIFFERENT STORES tuned to their regime — correctly,
because the regimes genuinely differ (low-vol-authored vs high-vol-temporal).

## How the code already bifurcated (read all three stacks together)

- **(1) AI-memory** → `ApachetaInterface` + `TensorRecord` (`apacheta/`). Its `__init__` says
  "authored tensor storage. Low volume, immutable." FURTHEST ALONG. Needs: per-instance DB
  (#13 / map's B1).
- **(3) Human-activity** → `ActivityStreamStore` + `FactRecord` + 3 backends (`activity/`). A
  PARALLEL stack that reuses the core contract primitives, NOT routed through ApachetaInterface
  (correct — different regime). Has temporal queries (`query_range`/`query_latest`). Fed by the
  BROKEN path (blob-recorder, not batch-import→#17). Needs: map's A1 (#17 as the Arango-resident
  per-file doc) + A2 (port Indaleko's recorder→ephemeral-staging→`arangoimport` fan-out).
- **(2) Joint working space** → ALREADY SEEDED: `activity/anchor.py:136` `freeze(handle,
  interface)` takes a transient activity handle and freezes it into AUTHORED Apacheta storage —
  a first bridge from activity-space into memory-space. Needs: generalize from anchor-specific to
  the simple cross-tenant edge (content-hashed + attributed + LOGGED, grant-slot null;
  `docs/north-star.md` §cross-tenant seam). The experiment (does the episodic-query loop close?)
  lives here.

## Path forward (the bifurcation is done; FINISH each branch from where it is)

The three branches do NOT gate each other (the dynamic-extensibility affordance the per-tenant-DB
+ parallel-stack architecture was built to buy). Critical-path unbuilt pieces:
- **Branch 3 (activity):** A1 (#17 doc shape) → A2 (batch back-half) → A3 (tenant DB) →
  A4 (runtime temporal pruning). Longest leg.
- **Branch 1 (AI-memory):** B1 (#13 per-instance DB). Makes "this instance has THIS memory"
  falsifiable.
- **Branch 2 (joint):** generalize `anchor.freeze` → the simple cross-tenant edge → X2 the
  loop-closing experiment. Last, smallest, only after 1 & 3 can stand alone.

## Drift-guard

The common core is the CONTRACT (errors + obfuscator + provenance + #17 + find), NOT
`ApachetaInterface` (that's branch-1's surface). Do not "unify" the three stores onto one
interface — the parallel stacks are CORRECT; their regimes differ. The human side is ACTIVITY,
not files. The bifurcation is a feature the code already has; the work is finishing branches,
not re-architecting.
