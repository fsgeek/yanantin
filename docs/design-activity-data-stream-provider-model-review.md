# Review: Activity Data Stream Provider Model

**Reviewer:** Yanantin AI (Claude Opus), 2026-07-03
**Reviewing:** `design-activity-data-stream-provider-model.md` (2026-07-04)
**Method:** doc read in full; every claim in §3 ("Relation to existing code") and every
model shape checked against `src/` as it stands on `main` today. Findings below are ranked
by how much they'd change the implementation, not by how easy they are to fix.
**Verdict:** strong, coherent, and correctly grounded in the fileaudit prototype. Ship the
§13 boundary — but resolve findings 1 and 2 *before* writing the first model, because both
are decisions the first line of code silently makes for you.

---

## What the design gets right (so Codex doesn't relitigate it)

- **The core inversion is correct and load-bearing:** raw events are evidence, episodes are
  memory (§2.3, §6). This is the fileaudit `LogCompactor` promoted to a memory-owned model —
  `FilesystemActivityEpisode` *is* `CompactRecord` with a window, a granularity, and an owner.
  The prior art in `indaleko/fileaudit/logcompator.py` should be cited by file, because it is
  the working proof that firehose→episode collapse is tractable, and its state-keying
  (`(procname-pid, fd)`) is a concrete answer to "what bounds an episode" that §6 leaves open.
- **Loss-aware normalization (§2.4) + the descriptor's evidence-quality vocabulary (§4)** are
  the right shape and match the project's standing position that fidelity must survive to the
  consumer. Keep them.
- **Synthetic-twin-per-collector (§9)** is already a settled project principle, not a proposal —
  it can be stated as a constraint the design inherits rather than argued for.

---

## Finding 1 — TWO open-observation layers, unreconciled (blocks the first model)

**Severity: high — the first `class` you write picks a side silently.**

`FactRecord` already exists and is *already* the open, append-only, schema-agnostic
observation (`src/yanantin/activity/models.py:36`): `data: dict`, `extra="allow"`,
provider_id + timestamp + content_hash. The design (§5) proposes `StorageActivityObservation`
as a *second* open model — but with **typed canonical fields** (path, object_ref, process_id,
source_sequence, confidence…).

The doc never says how these relate. Three incompatible readings, and the code can't defer the
choice:

1. `StorageActivityObservation` is the **shape of `FactRecord.data`** — i.e. it rides *inside*
   the existing envelope. Then the "required canonical fields" are a convention on a dict, not
   a model boundary, and `extra="allow"` is inherited from `FactRecord`, not declared anew.
2. `StorageActivityObservation` **replaces** `FactRecord` for storage activity — a parallel
   typed store alongside the schema-agnostic one. Then `ActivityStreamStore` needs to hold two
   record types, and the append-only guarantees must be restated for the typed one.
3. They **coexist** — `FactRecord` for raw, `StorageActivityObservation` as a first derived
   layer below episodes. Then there are *three* tiers (raw fact → typed observation → episode),
   which contradicts §2.3's clean two-tier "raw evidence vs episodic memory."

**Recommendation:** the design should state the tiering explicitly and, I'd argue, pick reading
(1): `StorageActivityObservation` is a *validated projection* over `FactRecord.data`, not a new
stored row. That keeps one append-only store, keeps the collector open, and makes the typed
canonical fields a *read/derive-time* contract — which is exactly where the project already
puts typing (open at collect, structure at derive). If Codex disagrees, the disagreement is the
useful output; but the doc must not leave it implicit.

## Finding 2 — `extra="forbid"` on the shipped Linux collector model vs §5's open principle

**Severity: high — it's the exact boundary the design exists to move, and the doc doesn't name it.**

§2.1/§5 make open observation schemas a *correctness property*. But the shipped Linux activity
collector models are closed: `FsChangeEvent` and `FsEventBatch` are both
`extra="forbid"` (`src/yanantin/collector/activity/linux/models.py:25,52`).

This is **not** a flat contradiction, and the review should be precise about why: `FsChangeEvent`
is a *fully-enumerated mtime-diff event* — `event_type` is a 3-value `Literal`, and a scan
genuinely yields nothing else (path, mtime, size, full stop). Closed is *correct* for that one
source. The problem is that the design's whole thesis is that this shape **will not survive the
second source** — `fs_usage` carries fd/errno/open_close_chain, NTFS carries usn/reason_flags,
fanotify carries mask/cookie. The moment those land, `extra="forbid"` becomes the
collector-drops-source-evidence bug the project has flagged repeatedly (and that Tony re-flagged
on 2026-07-03: *observation is total at the collector; policy lives at the recorder*).

**Recommendation:** the design should explicitly say (a) that the existing `FsChangeEvent`
forbid is correct-for-mtime-diff but is the exact boundary that opens when source #2 arrives, and
(b) whether `StorageActivityObservation` **wraps, replaces, or coexists with** `FsChangeEvent`.
§3 calls the existing path "useful as a low-level event source"; §5/§10 never close the loop on
what happens to it. This is the migration question, and it's answerable now.

## Finding 3 — episode boundary is asserted but never defined

**Severity: medium — it's the "hardest conceptual question" §13 claims to test, yet undefined.**

§6 defines the episode *model* (window, counts, roots) but never the episode *boundary rule* —
what closes one episode and starts the next. §13.2 says "emits one or more episodes for a
configured window," implying pure time-bucketing. But the fileaudit prototype already demonstrates
a *richer* boundary: `LogCompactor` closes a record on `close` of an `(proc, fd)` pair — a
**causal** boundary, not a clock boundary. The design should decide whether episodes are:

- pure **time windows** (simple, source-agnostic, but splits a coherent activity burst that
  straddles a window edge), or
- **activity-coherent** windows (burst detection / quiet-gap splitting — closer to how a memory
  owner actually recalls "the session where I fought DOCKER_HOST"), or
- both, with the policy (§7) choosing.

§13.4's success test ("different source shapes produce comparable episodes") **cannot be written**
until this is decided — comparability is defined relative to a boundary rule. This is the finding
most likely to stall the first implementation slice.

## Finding 4 — `content_hash`, idempotence, and the append-only claim

**Severity: medium — the batch-landing path already learned this lesson; the design should inherit it.**

§2.5 says the stream is append-only and compaction is additive. `FactRecord` carries a
`content_hash` (`activity/models.py:54`), and the storage batch-landing path already established
that idempotence comes from structural keys (`uuid5(source:uri)`), letting re-runs replace rather
than duplicate. The design's observations and episodes need the same discipline stated:

- What is an episode's identity? If it's `(provider, window_start, window_end, granularity)`, then
  re-deriving is idempotent and §7's re-coarsening is a *replace at a new granularity*, not a
  duplicate. The doc should say so.
- §8's reindex suggestions are told to be "idempotent and coalescible" (good) but given a random
  `uuid4` id (§8 model) — those two are in tension. A random id defeats coalescing on re-observation.
  Suggest a content-derived key, mirroring the storage path's `uuid5` scar.

## Finding 5 — descriptor storage (§12 Q1) has a defensible default the doc could just take

**Severity: low — an open question that's more settled than it looks.**

§12 Q1 asks where provider descriptors live (transport reg / core reg / activity facts / registry).
The project already has a registration story (Khipu/watay + the Registrar boundary that
`contribute()` enforces). A provider descriptor is *provider identity + evidence-quality metadata* —
that is registration data, and routing it anywhere but the Registrar re-opens the attribution
boundary the batch path was careful to preserve. Recommend: descriptors are core-registration
records, keyed by `provider_id`, and the descriptor's evidence-quality fields become queryable
provenance. This also answers Q3 (reindex suggestions as facts *and* wrangler-delivered — the fact
is the audit trail, the wrangler delivery is the action).

---

## Smaller notes

- **§4 descriptor is `extra="forbid"` (correct)** — this is the structural-boundary case from
  §2.2, so the closed config is right and consistent. Worth a one-line note in the doc that the
  descriptor being closed while the observation is open is *intentional and principled*, so a
  future reader (or linter-minded AI coder) doesn't "fix" the asymmetry.
- **§7 `GranularityRule.after_age`** implies a re-coarsening sweep must run over time. Nothing in
  the design says *what triggers* it (cron? query-time lazy? on-write?). Cheap to name; expensive
  to leave to the implementer's guess.
- **§10 lists `FsIncrementalCollector` mtime-diff as an input** but the class is actually named/located
  at `src/yanantin/collector/activity/linux/collector.py` — confirm the doc's names match at
  implementation time (they're close but the doc uses `FsIncrementalCollector`; verify the exact
  symbol before Codex wires against it).

---

## Recommended sequencing (amends §13)

The §13 boundary is right, but findings 1–3 are *design decisions*, not implementation steps —
resolve them on paper first, in this order:

1. **Decide the tiering** (Finding 1): is `StorageActivityObservation` a projection over
   `FactRecord.data`, or a stored peer? One sentence, but it shapes every model below it.
2. **Decide the episode boundary** (Finding 3): time-window, activity-coherent, or policy-driven.
   The §13.4 comparability test depends on it.
3. **State the `FsChangeEvent` migration** (Finding 2): wrap / replace / coexist.
4. *Then* §13.1–13.5 as written, with episode + suggestion identity keys (Finding 4) baked in
   from the first model, not retrofitted.

Findings 1–3 are the ones I'd most want a second independent read on — they're where I'm least
certain my recommendation is the right call versus merely *a* consistent call.

---

## Round 2 — review of the revision (2026-07-03, 19:16 doc)

Codex revised the spec against Round 1. All five findings are resolved *substantively*, not
gestured at: §3.1 makes the tiering explicit (observation = payload over `FactRecord.data`,
reading 1); §5.1 states the `FsChangeEvent` migration (coexist, converge at the payload
boundary); §6.1 defines the episode boundary (time-window default / quiet-gap / causal, with the
fileaudit `(proc,fd)` causal case cited); §6 and §8 add deterministic `uuid5` identity, removing
the random-`uuid4` defaults; §12 promotes the descriptor-storage and suggestion-routing questions
to settled defaults. Good revision.

**But the revision adopted findings 1–3 nearly verbatim — including the ones I flagged as
uncertain — without pushing back on any.** That's the deference risk I named. So here is the
stress-test of the *adopted* decision that Round 1 didn't generate and the revision didn't
surface:

### New finding (Round 2) — the payload-model decision defers an indexing cost the read side will pay

**Severity: medium — not a reason to reverse §3.1, but a missing sentence with teeth.**

The store's actual query surface (`src/yanantin/activity/store.py`) is `query_latest` and
`query_range` — **timestamp-indexed, top-level fields only.** It does not query *into*
`FactRecord.data`. §3.1's decision to nest `StorageActivityObservation` inside `data` keeps the
store generic (correct) but has an unstated consequence: the observation's canonical fields —
`path`, `object_ref`, `activity_type`, `process_name` — are exactly the fields the resolver and
the dynamic-faceting path will filter and facet on, and they are now one level deep in an
**unindexed dict**. Filtering them means either backend-specific JSON-path queries (ArangoDB can,
but unindexed unless an explicit index is declared) or promoting them to top-level columns.

This collides directly with the day's own faceting finding: faceting needs the sample-plus-count
(`fullCount`) contract over *queryable* fields, and a field inside `data` is not
queryable-with-count without an index. The design should add one sentence: *the canonical
observation fields the query/facet path depends on may need promotion to indexed top-level fields
or a declared backend JSON index; the payload model keeps the store generic but moves that
indexing cost to the read side, and the first compactor/query slice should decide which canonical
fields are promoted.* Decide it at model time, not when the first facet query is slow at 4.4M rows.

Everything else in the revision I'd merge as-is.
