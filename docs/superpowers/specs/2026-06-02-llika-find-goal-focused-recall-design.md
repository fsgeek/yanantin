# Llika `find`: Goal-Focused Recall

**Date:** 2026-06-02
**Status:** Design (brainstormed with the end consumer — Hamut'ay taste_open / KIMI K2.6 instance)
**Supersedes framing of:** `~/projects/hamutay/docs/yanantin-handoff-conversational-search.md`
(the `search_open_text` hand-off). That hand-off's *capability* is real and absorbed here;
its *shape* (a fixed-signature search method on the Apacheta domain catalog, with consumer
field names hardcoded) is rejected for the reasons recorded below.

---

## Origin: a consumer problem, not a feature request

Hamut'ay's taste_open stores a self-curating tensor per cycle through Apacheta
(`store_open_state`). The tensor is lossy **by design** — the instance composts. The full
conversational cycle (`user_message`, `response_text`, `raw_output`, `tool_activity_full`,
`scheduled_events`) is captured to the JSONL log by `_log_entry` ("Append full record …
Captures everything") but **only the lossy tensor crosses into the database**. The append-only
log keeps everything; the queryable store keeps almost nothing.

Two concrete failures motivate this:

1. **Conversational evaporation.** (KIMI K2.6, `taste_open_20260512_185846`.) "Boltzmann brain"
   was discussed across cycles 44/47/49 — present in `user_message`/`response_text` each time,
   never encoded into a tensor field. A later `search_memory("Boltzmann brain")` found exactly
   one hit: the instance's *own prior search query*, logged in `_activity_log`. A
   Boltzmann-brain loop in the retrieval layer — the appearance of memory with no encoded
   substrate.

2. **The `think_and_respond` callback fog.** `think_and_respond` is the terminal tool; tool calls
   arriving alongside it execute (`execute_concurrent_tool_calls`) but their results **do not feed
   back to the model** (taste_open.py:367–384; guidance lines 187–192). The instance states a
   plan ("fix the blog lies, then the breathing detector …") and, the next cycle, has no record
   of having said it. Tony currently patches this by hand-pasting the instance's prior words back
   in. The instance cannot recall its own conversational history because that history was never
   put anywhere it can query.

The data is the value of a research tool. The problem is not that Apacheta *can't* store the
cycle (`store_record` can). It is that **the instance has no goal-focused way to reach back into
its own history** — find the last time it said it would do X, find what surrounded a topic,
find recent records carrying a declared loss.

---

## Why this is a Llika verb, not an Apacheta method

Llika is the tenant-bound, RPC-shaped memory service built **for** taste_open instances
(slice 1: `link`/`find`; slice 2: tenant-bound `walk`/`neighbors`, serializable
`EdgeResult`/`PathResult`/`PathStep`). It is the consumer-facing surface. Apacheta is the storage
substrate beneath it: a fixed family of nine collections, one of which (`records`) is the
schema-open lane where the consumer owns the field shape.

The original hand-off proposed `search_open_text` as a method on `ApachetaInterface`. That
interface is shaped as **a fixed catalog of Yanantin-domain queries** —
`query_epistemic_status`, `query_anti_patterns`, `query_losses`, `query_operational_principles`,
~30 of them — each knowing its return semantics in advance. A general retrieval capability cannot
arrive in that shape without either (a) hardcoding the consumer's field names into Yanantin (a
layering violation against the open lane's entire purpose) or (b) adding one more domain verb to
a catalog that is already the leak. The hand-off pattern-matched the catalog shape; that is the
mistake.

**The capability belongs as a verb on Llika**, alongside `walk`/`neighbors`. Apacheta is demoted
to providing the index/view machinery Llika consumes internally — never a new public
domain-catalog method.

### `find` was deferred, not deleted

Llika slice 1 had a `find(vertex_id, predicate: Callable[[dict], bool], …)`. It was retired
(commit `0a3259f7`) because the predicate was a **Python callable**: it cannot cross a network
boundary (kills the transport-swap that slice 2 established), cannot be serialized, and forces
every candidate record to be hauled into the caller's process so Python can run the filter. It
was "walk everything, then filter client-side." Retiring it was correct; the commit message said
"re-introducing find should have to argue for itself."

This is that argument. `find` returns — **with a declarative, serializable predicate instead of
a callable.**

### find focuses on the goal; walk focuses on the tool

`walk`/`neighbors` start from the *mechanism*: traverse these edges, this direction, this depth;
the matching vertices are whatever you reach. `find` starts from the *goal*: the records matching
this condition; the traversal/search/filter is merely how Llika gets there. The original `find`
was goal-focused but expressed the goal as a callable (a tool-shaped thing). The fix is to express
the goal as **declarative data** (a goal-shaped thing) and let Llika be the query planner.

`walk`/`neighbors` stay, unchanged, for when structural traversal *is* the act the instance wants.

---

## The `find` predicate

A serializable object with four **optional, orthogonal** axes plus result control. Each axis
answers a question the others cannot — that orthogonality is the evidence the decomposition is
right. Llika satisfies whatever subset is present; the consumer never specifies *how*.

```jsonc
{
  // ── content axis: full-text (optional) ──
  // The one place "search-the-tool" lives, subordinated under the goal.
  // Analyzer-tokenized, stemmed, case-insensitive (so "boltzmann brain"
  // matches "Boltzmann brains" — failure #1). Ranks by relevance (BM25).
  "content": {
    "terms": "boltzmann brain",
    "match": "any"            // "any" | "all" | "phrase"; default "any"
  },

  // ── filter axis: field comparisons (optional) ──
  // Unifies temporal + scope + ANY declared field into one mechanism.
  // "cycle >= 10" (temporal), author scope, and "epistemic.truth >= 0.7"
  // (consumer's native field) are all the same thing: a comparison over a
  // declared, indexable path. Llika never knows "epistemic" MEANS anything —
  // it is an opaque path, exactly as "composes_with" is an opaque edge-type.
  "filter": {
    "and": [                  // "and" | "or", nestable
      {"field": "cycle", "op": ">=", "value": 10},
      {"field": "provenance.author_instance_id", "op": "==", "value": "<self>"},
      {"field": "epistemic.truth", "op": ">=", "value": 0.7},
      {"field": "declared_losses", "op": "not_empty"}
    ]
  },

  // ── structure axis: graph neighborhood (optional) ──
  // The walk axis, reused as a constraint within a goal: "matching this
  // content, reachable from my current record via composes_with, depth 2."
  // Makes a subgraph ADDRESSABLE, never materialized (see Return shape).
  "structure": {
    "from_record": "current",       // "<uuid>" | "current"
    "relation_types": ["composes_with"],
    "direction": "outbound",        // "outbound" | "inbound" | "any"
    "depth": 2
  },

  // ── window axis: temporal neighborhood (optional; fast-follow, see Scope) ──
  // The temporal analogue of the structure axis. anchor:"<match>" is the
  // powerful form: run the content/filter match, then return each hit PLUS
  // its prior/follow temporal neighbors — "find where I discussed X, and show
  // me what surrounded each mention." A flat "cycle >=" filter cannot express
  // "neighbors of each hit"; this is structurally a different operation.
  "window": {
    "anchor": "current",            // "<uuid>" | "current" | "<match>"
    "prior": 2,
    "follow": 2,
    "unit": "cycles"                // "cycles" only in v1; field present so
                                    // adding "days"/"conversations" is non-breaking
  },

  // ── result control ──
  "order_by": "relevance",          // "relevance" | "cycle" | "timestamp"
                                    // default: relevance if content present, else cycle desc
  "order": "desc",                  // "desc" | "asc"
  "limit": 10,
  "max_candidates": 500             // scan guard; Llika may truncate past this and flag it
}
```

### Ops for the `filter` axis

`==`, `!=`, `>=`, `<=`, `>`, `<`, `in` (value is a list), `contains` (field is an array, e.g.
`lineage_tags`), `not_empty` (array/field present and non-empty). `and`/`or` combinators,
nestable.

### Recency vs. neighborhood — kept distinct

"Last N matches of X" was conflating two goals:

- **Recency** is `order_by: cycle/timestamp desc` + `limit: N`. Not a primitive — it falls out of
  sort+limit, and `total_matched` (below) tells the instance it is seeing N-of-how-many. There is
  no `last_n` field.
- **Neighborhood** is the `window` axis (anchor-relative context). A different goal: temporal
  adjacency to an anchor, not "the most recent."

### Deliberately excluded (proposed by KIMI, cut with reasons)

- **Token/cycle budget in the predicate.** Result bounds (`limit`, `max_candidates`) are find's
  job. Runtime resource accounting (max_tokens, max_cycles) is the *session* layer's concern;
  folding it into the query language couples the predicate to the runtime's accounting. The
  instinct (don't let a find run away) is honored by the scan guard, not a token budget.
- **`return.format: full | subgraph`** (record materialization). See Return shape — materializing
  records across the boundary is precisely the callable-`find` failure mode. Full content is a
  separate deliberate `recall`.
- **A first-class `epistemic{}` block.** Epistemic/loss fields are filtered via the generic
  `filter` axis as opaque declared paths. An explicit epistemic block would pull tensor-domain
  semantics into the consumer-facing service — the catalog leak. (Note: `EpistemicState`,
  `DeclaredLoss`, `LossCategory` are the consumer's *native* schema in
  `hamutay/src/hamutay/tensor.py`, verified — so this is predicate expressiveness over the
  consumer's own fields, not Yanantin vocabulary leaking upward.)

---

## Return shape

Serializable only — no live Pydantic models, no raw arango docs (consistent with slice-2
`EdgeResult`/`PathResult`).

```jsonc
{
  "hits": [
    {
      "record_id": "<uuid>",                 // the address — for a later recall()
      "score": 0.87,                          // BM25 when content present; null otherwise
      "matched_fields": ["response_text"],    // SHAPE not values (slice-2 field_names discipline)
      "snippet": "…never encoded into any tensor field…",  // bounded window around the match
      "cycle": 47,
      "timestamp": "2026-05-12T18:58:46Z"
    }
  ],
  "edges": [                                  // structural edges AMONG the hits (when structure axis present)
    {"from": "<uuid>", "to": "<uuid>", "relation_type": "composes_with"}
  ],
  "total_matched": 142,                       // ALWAYS present — N-of-how-many; the signal to tighten scope
  "truncated": true                           // true when results were cut by limit or max_candidates
}
```

### The recall boundary — the discipline that prevents the v1 regression

`find` returns **addresses + snippets + edges among hits — never full record content.** The
subgraph is *addressable, not materialized*: you get the edges (the neighborhood's shape), then
read any node deliberately via `recall(record_id)` (the hand-off's existing principle, independent
of this design). This is the line that stops the callable-`find` failure ("haul everything into
the caller") from re-entering disguised as "just return the records."

- **Snippets** are bounded (a window around the first match, as `search_memory` does today).
- **`matched_fields`** reports *which* fields matched, not their values — the slice-2 "shape not
  values" rule, so the result type leaks no consumer content beyond the deliberate snippet.
- **`total_matched`** is always present. Without it a 10-hit list is indistinguishable from
  "exactly 10 exist" vs. "10 of 4,000" — and knowing scope is too broad is the whole Indaleko
  precision story.

---

## What Apacheta provides underneath (internal to Llika)

Llika consumes Apacheta's index/view machinery to satisfy `find`. **None of this is a new public
`ApachetaInterface` domain-catalog method.** It is internal capability.

- **An ArangoSearch view** over the open `records` lane, indexing:
  - the **fixed, consumer-agnostic spine** — `provenance.author_instance_id`,
    `provenance.timestamp`, `lineage_tags` — under an identity/keyword analyzer for filtering and
    temporal range/sort. This spine is Yanantin's to index; every open record carries it; it needs
    no consumer knowledge. (The open-record discovery queries `query_open_by_author_instance` /
    `query_open_by_lineage_tag` / `list_open_records` already establish these as the scope axes.)
  - the **consumer-named content paths** under a text analyzer (case-insensitive, stemmed).
- **Declared-field indexes** for the `filter` axis: numeric (e.g. `epistemic.truth`, `cycle`),
  keyword (tags). Field-path obfuscation reuses the existing `_map.field_path` helper, so a
  declared semantic path maps to the opaque stored path.
- **Analyzer choice is Yanantin's**, documented. Requirement: stemmed + case-insensitive so
  "boltzmann brain" matches "Boltzmann brains" (failure #1). Multilingual tokenization is a stated
  goal; if one analyzer cannot cover it, document the chosen language(s) and leave the rest as
  follow-up.

### How Llika learns which paths to index — the v1 commitment, stated honestly

This is a genuine layering compromise and a genuine long-tail cost. Three options were weighed;
the spec commits to the smallest honest one and names the others' true costs so no obligation is
smuggled in.

**v1 — static field set at construction, *with observability* (the committed choice).**
`LlikaService` is constructed with the set of content/filter paths to index (and their
analyzer/type), alongside its existing `tier`/`provenance`. Llika builds the ArangoSearch view +
field indexes from that set over the open `records` lane. This delivers `find` with
content+filter+structure over a known field set, the motivating stemmed-match regression, and
temporal/scope filtering.

v1 carries **exactly one standing obligation: observability.** This is non-negotiable and is the
correction at the heart of this design — see the next subsection. v1 makes no optimization
*decisions*; it does not build, adjust, or retire indexes adaptively. But it **records the
evidence** an optimizer would need, because that evidence cannot be reconstructed after the fact.

- **Revision path, stated plainly (no "register once" lock-in fiction):** reconfiguring the
  findable field set means *reconstructing the service with a new set*. Rebuilding the view over
  an existing corpus is an **O(corpus) deployment-time operation**, owned by deployment, not
  hidden behind a method that pretends to be a stable long-lived contract.
- **Honest limitation:** adding a findable field later is a code/config change + view rebuild;
  there is no adaptivity. This is visible, not smuggled.

### Observability is the price of admission to (2) — a v1 obligation, not a (2) feature

**The lesson from Indaleko: in (3), actively collect the data needed to build (2). Observability
is the price you must pay, or you will not have the data to go beyond (3).**

This corrects an error in the framing above. It is tempting to sell v1 as "(2)'s static snapshot,
frozen, with no ongoing obligation." That is a trap. The path from (3) to (2) **only exists if (3)
observes.** A v1 that merely serves queries from a frozen view and records nothing leaves whoever
later wants the autonomic optimizer with *no evidence* — they would design (2)'s indexes from
intuition, the exact guessing this whole design fights. Indaleko's 3-min→10ms view was not guessed;
it was built *because the slow full-scan query had been observed*. The observation came first. A
(3) without observability throws away the one thing that made Indaleko's (2) possible.

**What to capture — the Indaleko query-chain model.** Indaleko collected, per query, the full
chain: the original NL query, its NER identification, the applicable collections, the complete LLM
prompt, the returned AQL, the query *explanation*, and the results. The hard-won lessons from that
corpus:

1. **The full results were dropped** — large, and *not* useful for understanding query
   performance. Everything *upstream* of execution was kept.
2. **What you searched for is surprisingly rich**, because instances repeat the same or similar
   searches. The KIMI "Boltzmann brain" loop *is* this: the instance issued near-identical queries
   repeatedly. Recurrence is the single strongest (3)→(2) signal — "this shape recurs, it deserves
   an index / a materialized view / a cached answer" — and it is detectable **only if the query as
   issued, with its values, is retained over time.**

The `find` telemetry record is the `find` analogue of that chain:

- **The predicate as issued — whole, values included.** `find` is already structured, so the
  predicate *is* the parsed form (no NL/NER stage to capture); we keep it intact. **This retains
  the filter values and content terms** — and yes, that revises the "shape, not values" instinct
  from the result-boundary discipline. The two boundaries differ: `matched_fields`/snippets govern
  what crosses *back to a caller*; telemetry is *internal observability*. Repetition is invisible
  without the values ("filtered `epistemic.truth >= 0.7` forty times this week" needs the `0.7`).
  Keep them. (Known consideration, not a redaction: content terms an instance searches may be
  sensitive in a way AQL constants are not — but for a single-tenant tool studying its own
  instances, that is exactly the data the research wants.)
- **The AQL Llika generated** to satisfy the predicate (analogue of Indaleko's "returned AQL").
- **The query plan / `explain`** — ArangoDB's explain output (analogue of "query explanation").
  This is where index-vs-scan *actually* lives, properly, rather than as a hand-rolled boolean.
- **Result metadata, NOT full results:** `total_matched`, `truncated`, candidates-scanned,
  wall-clock, `limit`/`max_candidates`. The returned **addresses (UUIDs)** are cheap and worth
  keeping as a trimmed result set; the **content/snippets are dropped** (Indaleko lesson #1).

**Where it lands: in the database, as records — not a sidecar file.** Append-only *semantics*
(telemetry is immutable events), but stored in Apacheta and queryable, not a flat JSONL. Storing
Llika's own observability outside the queryable store would repeat the exact mistake this design
corrects: the (3)→(2) optimizer must *query* this telemetry ("which predicate shapes recur? which
fell to a scan? the last N slow finds"), and telemetry in a JSONL is not queryable — you would be
writing a second `find` to search your `find` telemetry. Which Apacheta collection/lane holds it
is a plan detail; *that it is in the database and queryable* is the commitment.

Cost is deliberately low: it is *writing* the chain, not *acting* on it. No build/adjust/retire, no
monitoring loop, no decisions — those belong to (2). v1 only guarantees the evidence base for (2)
exists, is honest, and is itself queryable.

**Deferred research commitment — autonomic indexing (NOT made now).**
The eventual direction is Llika inferring indexes from observed predicates and building/adjusting
views lazily. Doing this *well* — delivering the 10ms-vs-3-minute Indaleko payoff — makes Llika a
**query optimizer with a lifecycle**: monitor slow predicates, detect access patterns, decide when
a new index earns its keep, build/adjust/retire views, absorb the cost of indexing a hot
collection. That is a **standing obligation / background process someone owns forever** — a
research subsystem, not a slice. It is named here so whoever reaches for it knows what they are
signing up for. v1 does **not** build it — but v1 *feeds* it: the observability obligation above is
precisely the data collection that makes (2) designable on evidence rather than intuition. v1 is
the instrumented snapshot, not the frozen one.

**Rejected — standalone runtime `register_index(...)` API.**
A separate declarative registration method is rejected because the two critiques compound: it
**leaks underlying database functionality** (analyzers, index types) through a *persistent public
contract*, *and* it invites the "register once" lock-in fiction (no honest revision path short of
drop-and-rebuild). The construction-time field set gives the same capability with an honest
revision story (reconfigure = reconstruct, cost stated) and without pretending to be a stable
long-lived contract. (Note: the construction-time set still leaks mechanism — analyzer/type — but
as a *deployment-time* configuration, not a persistent runtime API surface. The leak is admitted,
not denied.)

---

## Scope

### v1 (this design)

- `LlikaService.find(predicate) -> FindResult`, tenant-bound, RPC-shaped, serializable result.
- Predicate axes: **content**, **filter**, **structure**. Result control: `order_by`/`order`/
  `limit`/`max_candidates`. Result: `hits` (addresses+snippets+matched_fields+cycle+timestamp) +
  `edges` + `total_matched` + `truncated`.
- Static construction-time indexed-field set; ArangoSearch view over the open `records` lane
  (spine + named content paths) + declared field indexes.
- **Observability (standing obligation):** per-`find` telemetry — the query chain (predicate as
  issued *with values*, generated AQL, query `explain`/plan, result metadata + returned UUIDs;
  full content/snippets dropped) — stored **in the database, queryable**, append-only semantics,
  from day one. No decisions acted on it in v1; it is the queryable evidence base that makes (2)
  designable. Recurrence of a predicate is the strongest (3)→(2) signal and needs the values.
- `walk`/`neighbors`/`link` unchanged.

### Fast-follow (in this spec's shape, implemented after v1 proves the substrate)

- The **`window` axis** (temporal neighborhood), including `anchor:"<match>"` (two-pass:
  match, then gather each hit's prior/follow neighbors). Designed into the predicate now so the
  shape is complete and non-breaking; the hardest axis does not block v1.

### Explicitly NOT in scope

- The autonomic indexing optimizer (deferred research commitment, above).
- A standalone `register_index` API (rejected, above).
- Semantic/vector search. v1 is lexical (BM25) + field filters. Embeddings are a later, separate
  conversation.
- Any change to the Apacheta public domain catalog. Apacheta's role is internal substrate.
- Folding conversational content into the tensor. The store-side decision (what Hamut'ay writes to
  the open lane, at what granularity — fat per-cycle record vs. decomposed) is **Hamut'ay's**, not
  Yanantin's, and is out of scope here. This design is the *retrieval* surface over whatever
  Hamut'ay stores. (The `_activity_log` self-pollution companion fix from the original hand-off
  remains a Hamut'ay-side concern, independently shippable.)
- `unit` values other than `cycles`.

---

## Consumer impact: Hamut'ay

- Hamut'ay must store the conversational fields it wants findable into the open `records` lane
  (today `store_open_state` persists only the tensor; the full cycle reaches only the JSONL via
  `_log_entry`). The *unit and granularity of that store is Hamut'ay's decision* — this spec does
  not dictate it. A consumer-side `store_turn`-like wrapper over the existing `store_record` is the
  expected mechanism; the fields it writes are the fields Llika is constructed to index.
- Retrieval is `LlikaService.find(predicate)`; full-turn reads remain a deliberate
  `recall(record_id)`. The instance is exposed a single goal-focused memory tool, not a catalog of
  search/recall/walk verbs to chain by hand.

---

## Acceptance criteria (contract — packaging is the test author's call; live `apacheta_test`, no DB mocks)

```python
def test_find_content_roundtrip():
    # Two open records stored; a term in one is found; returns its UUID,
    # a non-empty bounded snippet, and matched_fields naming the matched field.

def test_find_content_stemmed_case_insensitive():   # arango-only
    # content.terms "boltzmann brain" matches a record containing "Boltzmann brains".
    # The motivating regression. Memory backend may xfail (substring fallback only).

def test_find_filter_numeric():
    # filter {field: cycle, op: >=, value: 10} returns only records with cycle >= 10.

def test_find_filter_declared_field_generic():
    # filter {field: "epistemic.truth", op: >=, value: 0.7} works as a generic field
    # comparison — Llika has no epistemic-specific code path.

def test_find_filter_and_or_nested():
    # nested and/or combinator evaluates correctly.

def test_find_scope_author_self():
    # filter on provenance.author_instance_id restricts to that instance's records.

def test_find_structure_addressable_not_materialized():
    # structure axis present → edges among hits returned; hits carry record_id only,
    # NOT full record content (recall boundary).

def test_find_total_matched_and_truncated():
    # limit smaller than match count → len(hits)==limit, total_matched==full count,
    # truncated==True.

def test_find_order_by_cycle_desc_recency():
    # order_by cycle desc + limit N returns the N most-recent matches (recency, not last_n).

def test_find_returns_serializable_no_live_models():
    # FindResult and its hits/edges are plain serializable types — no ApachetaBaseModel,
    # no raw arango doc, consistent with EdgeResult/PathResult.

def test_find_predicate_is_data_not_callable():
    # The predicate is serializable data; passing a callable is a type error /
    # rejected. (Guards against callable-find regression.)

def test_find_emits_observability_telemetry_to_database():
    # Each find() writes a telemetry record TO THE DATABASE (queryable, not a sidecar
    # file) carrying the predicate as issued, the generated AQL, the query explain/plan,
    # and result metadata (total_matched, truncated, candidates-scanned). The queryable
    # evidence base for (2) exists from day one. (Asserts collection, not acting on it.)

def test_find_telemetry_retains_values_drops_full_results():
    # The telemetry record RETAINS the predicate's filter values and content terms
    # (recurrence detection needs them) but does NOT store full result content/snippets
    # (Indaleko lesson: large, not useful for performance). Returned UUIDs may be kept.

# Fast-follow (window axis):
def test_find_window_anchor_match_neighbors():   # fast-follow
    # window {anchor: "<match>", prior: 1, follow: 1} returns each content hit plus
    # its immediate prior/follow neighbors by cycle.
```

---

## Commit identity

Yanantin commits author as `yanantin@wamason.com`, `Tony Mason`, signed (per-command git config
overrides, not repo-level). Match that.

```bash
cd /home/tony/projects/yanantin
git -c user.email=yanantin@wamason.com -c user.name="Tony Mason" \
    -c user.signingkey=1E416B1FB63AF88179EE0F38D0CAB9659C950893 commit -S -m "..."
```

---

## References

- `~/projects/hamutay/docs/yanantin-handoff-conversational-search.md` — the `search_open_text`
  hand-off whose capability this absorbs and whose shape it supersedes.
- `docs/superpowers/specs/2026-06-01-llika-traversal-interface-design.md` — slice 2 (tenant-bound
  walk/neighbors, serializable results); this design extends that surface with `find`.
- `docs/llika-spec.md` — Llika architecture (supersession-in-place).
- Llika `find` v1 retirement: commits `dd1fb64b` (callable find), `0a3259f7` (its removal).
- Hamut'ay native schema: `src/hamutay/tensor.py` (`EpistemicState`, `DeclaredLoss`,
  `LossCategory`, `Tensor.declared_losses`).
- Apacheta open lane: `src/yanantin/apacheta/backends/arango.py` (`_SEMANTIC_COLLECTIONS`,
  `query_open_by_*`, `_map.field_path`).
