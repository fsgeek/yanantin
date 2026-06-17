# Index-backed find — ranked text (A) + time pruner (B)

*2026-06-16. Brainstormed with Tony, grounded in his prior Indaleko implementation
(`~/projects/indaleko/db/db_collections.py` views + `~/projects/indaleko/query/cli.py:1173` query
history). Replaces the substring-scan "festering wound" (`relevance: 1.0`, load-all-then-filter) on
both the yanantin `find()` and Hamut'ay `search_memory` sides — they are ONE unbuilt road.*

## What this is (one paragraph)

Give yanantin's `find()` and (through the bridge) Hamut'ay's `search_memory` **honest, index-backed
ranked retrieval**, replacing the Python substring full-scan that exists on both sides. Two coordinated
storage objects over the open-records lane: **(A) an `arangosearch` text view** for tokenized,
analyzer-driven, BM25-ranked text matching, and **(B) a `search-alias` timestamp view** over inverted
index(es) for time-slice pruning — the north-star "timestamp as the search-space reducer." A is the text
matcher; B is the time pruner; B runs FIRST and A ranks B's survivors (Tony's dissertation measured a
99.9% search-space reduction from a one-month window — B is the mechanism, not an optimization). A
**minimal (C) find-event capture** ships WITH them — prune-ratio, query-shape, duplicate-frequency,
elapsed — because the 99.9% lever was only ever visible through measurement; the full activity-collector
and the analysis on top stay a future spec.

## The justification is capability (A) + scale-headroom (B), NOT present latency

At current scale (low thousands of records) the brute-force scan is fine — Tony's Indaleko numbers
settle it: 28.5M files scanned in ~3 min; we have ~0.0001% of that. So neither object is justified by
"the scan is slow now." Their real justifications differ and both are honest:

- **(A) text view = a CAPABILITY we lack at ANY scale.** The substring scan cannot tokenize, stem, or
  rank. `find("carry forward")` cannot match "carried forward" or rank a record mentioning it twice
  above one mentioning it once. That is a capability hole, not a speed hole — true at 1k records and at
  32M. This is the immediate customer relief (the wound Tony sees).
- **(B) timestamp view = THE MECHANISM, not headroom.** Tony's dissertation evaluation measured it:
  **reducing the window to a single month gave a 99.9% search-space reduction** on his 28.5M-file
  dataset (28.5M → ~28.5k candidates). That is not an optimization — it is what makes find *tractable
  at all* on a large corpus. A ranks the SURVIVORS of B's prune; you never rank 28.5M things, you rank
  the ~28.5k a month-window leaves. So B is the FIRST half of find and A operates on its output. Without
  an index, time-slicing is itself a full scan (scan ≈ 3 min vs indexed ≈ 10ms + marshaling at 32M) —
  i.e. the pruner that's supposed to make find cheap would be the expensive operation. Build the seam
  while data is small and migrations are free (build-for-N, run-1); at scale it is load-bearing.

### Why time is the lever and the knowledge graph is the luxury (the strategic why)

Tony spent years on a rich knowledge graph — genuinely valuable, and *more valuable to LLMs than to
humans*. But its blocking problem was never technical; it was **incentive**: building the graph requires
humans to do work for a payoff years out — a tough sell. The timestamp/activity path dissolves that,
because **the activity data already exists**: the tech industry tracks everyone exhaustively, and some
of that data is available to the tracked. So we don't build a corpus and wait years — we *convert*
existing historical activity into "AQL over files + history." The 99.9% time-prune is what makes the
data-you-already-have *sufficient* for sloppy-episodic-memory queries. Time is the lever (data you have,
1000× reduction); the graph is the luxury (data you'd wait years for). This is why find rests on the
timestamp index and NOT on the graph being built first.

## Two corrections the Indaleko ground forced (would have been missed in the abstract)

1. **The view indexes fields by their OBFUSCATED (UUID) names, resolved through the StorageObfuscator
   — never hardcoded semantic names.** Indaleko's `ObjectsTextView` indexes `434f7ac1-...` (= Modified)
   etc., with "Timestamps promoted to top-level fields explicitly." Under yanantin's opaque storage
   (this morning's obfuscator seam), field names ARE UUIDs. So the view's field→analyzer map must be
   built by passing semantic field names through the `StorageObfuscator.field_name()` at view-creation
   time. This ties index-backed find to the obfuscator seam: they are the same system. (Transparent
   mode → semantic names pass through unchanged; opaque mode → UUIDs.)
2. **`search-alias` IS the swappable-composition mechanism we already committed to.** Indaleko built the
   timestamp pruner as a `search-alias` view bundling four inverted indices (Created/Modified/Accessed/
   Changed) behind one stable name (`ObjectsTimestampView`). A search-alias names a *set of indices* you
   can recompose without changing the consumer's query target — which is exactly the "ranking/index
   swappable behind a stable name" seam from the BM25-first/relevance-later decision. One mechanism
   serves both B and the swappability requirement. (`arangosearch` view = text matcher; `search-alias`
   view = named index bundle; Indaleko used BOTH on one collection — they are complementary, not
   either/or.)

## Relevance is honest BM25 now, swappable later; the score field DECLARES its absence

Per the "both, sequenced" decision: ship index-backed honest BM25 as v1, build the seam so the ranking
function is swappable (the search-alias mechanism above), study "what SHOULD rank an instance's memory"
as later research on top — without re-plumbing.

The substring scan's ORIGINAL SIN was `relevance: 1.0` — a field whose contract is "relevance" holding
a value that wasn't. The fix (Tony: "is there a way to signal back 'not implemented' for the scores?" —
yes, that's the move):

- **`rank`**: 1st, 2nd, 3rd … — REAL, the BM25 ordering. Implemented, honest.
- **`score`**: present in schema, value = a declared-loss envelope (the harness's own
  `_declared_loss_stub` pattern, `taste_open.py:392`): `{"status": "not_normalized", "raw_bm25": <float>,
  "meaning": "engine score; not a probability; not comparable across queries"}`. The raw number is
  available to research WITHOUT claiming to be normalized relevance.
- **No bare `relevance: <float>` field.** That field can only lie at this stage; it is deleted, not
  filled. When the research answers "what is relevance here," it lights up honestly instead of having
  always-pretended.

## Scope — A+B is one spec; the A/B BALANCE is honestly OPEN; C is a future spec

- **A and B ship as one coordinated build.** They are the two halves of one find operation; designing
  them apart would force a premature commitment to a boundary that is not yet known.
- **The A/B ORDERING is decided by measurement; only the window's HARDNESS stays open.** Tony's 99.9%
  finding settles the ordering: **prune-by-time-FIRST, then rank** — because rank-then-filter would rank
  28.5M records to discard 99.9% of them, which is not a search-space reduction at all but a post-filter
  on work already done. What remains genuinely open: is the time window a HARD pre-filter (out-of-window
  records are invisible) or a STRONG PRIOR that ranking can override for an unusually relevant
  out-of-window hit? That resolves with experience + (C)'s data. (Note: an earlier draft called the
  balance "fully open" — that was over-caution; the ordering is earned by data, only the hardness is
  open. Don't drift to "open" in the safe direction any more than to "settled" in the convenient one.)
- **(C) find-event capture is MINIMAL-BUT-PRESENT in this build** (moved in from "future spec").
  Rationale, Tony's: the 99.9% lever was only visible through EVALUATION, not design — so build the
  instrument WITH the thing it measures, or we resolve the A/B window-hardness by guessing instead of
  measuring (repeating the "didn't know time was the lever until the dissertation" gap). And Tony: "C
  isn't very hard" — Indaleko already prototyped it (`cli.py:1173` `QueryHistoryData`). The MINIMAL C is
  not "log everything"; it is the few signals that teach the open questions: **prune-ratio**
  (candidates-before vs after the time window — the 99.9% axis), **query shape**, **duplicate-query
  frequency** (Tony's example — repeats are a cache/materialization signal), and **elapsed**. Emitted as
  a find-event from the first ranked find. The full activity-COLLECTOR that consumes these, and the
  ANALYSIS/auto-optimization on top, stay a future research spec ([[project_find_operations_are_activity_streams]]).
  C-minimal here = the instrument; C-full later = the research.

## Components (A+B)

### A — the `arangosearch` text view

Over the open-records collection. Field→analyzer map built by resolving semantic field names through
the `StorageObfuscator` at creation time (correction 1). Analyzers: start with `text_en` (stemming);
Indaleko's custom analyzers (`indaleko_snake_case`, `_camel_case`, `_filename`) are a proven later
refinement for identifier-shaped content, deferred. `stored_values` for the fields find returns as
snippets/addresses so result assembly doesn't re-fetch. yanantin `find()` queries it broadly; Hamut'ay
`search_memory` queries it with the lineage/author filter it ALREADY passes (scope ∈ session/
cross_session/all). One view, scope via filter (start here; per-lane views not foreclosed).

### B — the `search-alias` timestamp view

Inverted index on the record timestamp axis, behind a stable search-alias name. Enables bounded
time-slice seeks (the north-star pruner) and serves as the swappable-composition seam. Which timestamp
field(s) and whether multiple axes (author/instance, lineage, kind) also get inverted indices in v1 is
part of the open A/B-balance question — v1 builds the time axis (the north-star one); other axes added
when a query pattern demonstrably hammers them (evidence-driven, per "queries teach us what to
optimize"), NOT gold-plated up front.

### C-minimal — the find-event capture (the instrument)

Every find emits one event capturing the signals that teach the open questions — NOT a general
activity log. Fields: `terms`, `time_window` (if any), `candidates_before_prune` and
`candidates_after_prune` (the prune-ratio — the 99.9% axis), a normalized `query_shape`
(for duplicate/cluster detection), `duplicate_of` (prior identical query, if detected), `elapsed_ms`,
and the returned ranked addresses. Ordering decided so the prune-ratio is meaningful (before = full
candidate set, after = post-time-window). Written to a capture sink; the activity-collector that
CONSUMES these and the analysis/auto-optimization on top are a future spec. Build so emitting the event
is natural and find is never un-observable — but keep C-minimal genuinely minimal (these signals, not
"everything").

### The find result contract (honesty surface)

`rank` (real) + `score` (declared-loss envelope) + matched-field SHAPE + bare-UUID addresses + bounded
snippets, never full content (hydrate one hit deliberately via `get`). Returns `(returned_count,
total_matched)` — the LIMIT-returns-total contract ([[project_limit_returns_total_not_just_page]]); with
a real index, `total_matched` comes from the engine (fullCount/pushdown), NOT `len(filtered)` over a
materialized Python set (which is the very disease this build removes).

## Error handling

Fail-stop, consistent with the substrate. View/index absent or unbuildable ⇒ raise, do NOT silently
fall back to the substring scan (that would re-grow the wound and lie about capability). If the view
genuinely cannot be created (permissions, missing collection), that is a hard error surfaced to the
caller, not a degraded mode.

## Testing (green vs live `apacheta_test`, no mocks)

1. Index a record set with known term frequencies → `find(term)` returns them RANKED (a record with the
   term twice ranks above once) — proves BM25 ranking exists (the capability the substring scan lacked).
2. Stemming: `find("carry forward")` matches a record saying "carried forward" — proves analyzer
   tokenization (substring scan provably cannot).
3. `rank` is a true ordering; `score` is the declared-loss envelope (status=not_normalized, raw_bm25
   present); NO bare `relevance` float anywhere — proves the honesty surface (the anti-`1.0` red bar).
4. Obfuscated-field indexing: build the view under an OPAQUE obfuscator → it indexes UUID field names
   and find still works; under transparent → semantic names. Proves correction 1 (the obfuscator seam).
5. Time-slice (B): `find` constrained to [T1,T2] returns only in-window records via the search-alias —
   and (at small scale, a correctness test not a perf test) returns the SAME set the scan would, proving
   the pruner doesn't drop or duplicate.
6. `total_matched` comes from the engine, not a Python `len()` over a materialized full set — proves the
   pushdown (LIMIT-returns-total done right).
7. Both consumers: yanantin `find()` and Hamut'ay `search_memory` (via bridge, lineage-filtered) both
   resolve through the view — the substring loop is DELETED on both sides, not patched.
8. **C-minimal:** a find emits an event carrying `candidates_before_prune`/`candidates_after_prune`
   (the prune-ratio), `query_shape`, `elapsed_ms`; a repeated identical query is detected as a
   duplicate. Proves the instrument exists — the thing that would have surfaced the 99.9% finding.

## OPEN ITEMS (do NOT collapse)

1. **The time-window HARDNESS** — hard pre-filter (out-of-window invisible) vs strong-prior (ranking
   can override for an exceptional out-of-window hit). The ORDERING (prune-first) is decided by Tony's
   99.9% measurement; only hardness is open. Resolves with experience + C's data.
2. **Which axes beyond time get inverted indices** — evidence-driven (C's query-shape/duplicate data),
   not up-front gold-plating.
3. **Custom analyzers** (snake/camel/filename) — proven in Indaleko, deferred until content shape
   demands them.
4. **(C) FULL find-as-activity** — the collector that consumes find-events + the analysis/auto-optimization
   on top (Tony: "preferably automatically, but that's its own research project"). C-MINIMAL (the event
   emission) is IN this build; C-FULL is the future spec. Depends on the activity lane.
