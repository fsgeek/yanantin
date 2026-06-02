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

  // ── structure axis: graph neighborhood (FAST-FOLLOW — NOT v1; gh #2, blocked by #5) ──
  // The walk axis, reused as a constraint within a goal: "matching this
  // content, reachable from my current record via composes_with, depth 2."
  // Makes a subgraph ADDRESSABLE, never materialized (see Return shape).
  // DEFERRED: Hamut'ay writes Apacheta composition_edges; Llika traverses
  // llika_composition (verified — service.py:17 vs apacheta_bridge.py:218).
  // The structure axis cannot see Hamut'ay's edges until the edge migration
  // (gh #5) lands. Shape designed now so adding it is non-breaking.
  "structure": {
    "from_record": "current",       // "<uuid>" | "current"
    "relation_types": ["composes_with"],
    "direction": "forward",         // "forward" | "backward" | "both" (MATCHES walk's vocab)
    "depth": 2                      // depth 0 = anchor only, no traversal (see acceptance)
  },

  // ── window axis: temporal neighborhood (FAST-FOLLOW — NOT v1; gh #3) ──
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
  "order_by": "cycle",              // "relevance" | "cycle" | "timestamp"
                                    // DEFAULT IS ALWAYS "cycle" desc — explicit, not
                                    // content-conditional. Adding a content axis must NOT
                                    // silently flip sort order (KIMI concern 5). For
                                    // relevance ranking, ask for it: order_by="relevance"
                                    // (valid only when a content axis is present).
  "order": "desc",                  // "desc" | "asc"
  "limit": 10,
  "max_scan": 500                   // scan guard (renamed from max_candidates — it bounds
                                    // SCAN, not result count). Llika may stop scanning past
                                    // this; when it does, total_matched is a LOWER BOUND and
                                    // the result flags scan_truncated (see Return shape).
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

- **Token/cycle budget in the predicate.** Result bounds (`limit`, `max_scan`) are find's
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
      "record_id": "0c4f…-uuid",             // BARE UUID — the address for get(record_id).
                                              // NOT an Arango "collection/key" ref. Llika
                                              // converts to/from records/<uuid> INTERNALLY
                                              // (see Consumer Boundary: ID shape).
      "score": 0.87,                          // BM25 when order_by="relevance"; null otherwise
      "matched_fields": ["response_text"],    // SHAPE not values (slice-2 field_names discipline)
      "snippet": "…never encoded into any tensor field…",  // bounded window around the match
      "cycle": 47,
      "timestamp": "2026-05-12T18:58:46Z"
    }
  ],
  "edges": [                                  // structural edges AMONG hits — FAST-FOLLOW only
                                              // (empty in v1; populated when structure axis ships, gh #2)
    {"from": "0c4f…-uuid", "to": "9a1e…-uuid", "relation_type": "composes_with"}
  ],
  "total_matched": 142,                       // ALWAYS present. EXACT when the scan completed;
                                              // a LOWER BOUND when scan_truncated is true.
  "truncated": true,                          // true when results were cut by `limit`
  "scan_truncated": false                     // true when scanning stopped at `max_scan` —
                                              // then total_matched is a lower bound, not exact
}
```

### The recall boundary — the discipline that prevents the v1 regression

`find` returns **addresses + snippets + edges among hits — never full record content.** The
subgraph is *addressable, not materialized*: you get the edges (the neighborhood's shape), then
read any node deliberately via **`get(record_id)`** — a companion Llika verb (see Consumer
Boundary), the deliberate-hydration counterpart to find's address-only return. This is the line
that stops the callable-`find` failure ("haul everything into the caller") from re-entering
disguised as "just return the records."

- **Snippets** are bounded (a window around the first match, as `search_memory` does today).
- **`matched_fields`** reports *which* fields matched, not their values — the slice-2 "shape not
  values" rule, so the result type leaks no consumer content beyond the deliberate snippet.
- **`total_matched`** is always present. Without it a 10-hit list is indistinguishable from
  "exactly 10 exist" vs. "10 of 4,000" — and knowing scope is too broad is the whole Indaleko
  precision story.

---

## Consumer boundary

Three independent reviews (Hamut'ay-Claude's call-site census, KIMI's ergonomics pass, Codex's
code-grounded audit) agreed the *design* is sound and the *consumer boundary* was under-specified.
This section pins it. The findings below were **verified against code 2026-06-02**, not taken from
review prose.

### ID shape — public bare UUID, internal Arango ref (verified blocker)

`walk`/`neighbors` today return `record_id = vertex["_id"]` (service.py:106) — an Arango
`collection/key` ref (e.g. `records/0c4f…`), and a slice-2 test asserts the slash
(`tests/integration/test_llika_service.py:158`). But Hamut'ay's `recall(record_id)` expects a
**bare UUID** (`hamutay/src/hamutay/tools/memory.py:149`).

**Decision:** Llika's *public* surface (`find` hits, `get`, and `walk`/`neighbors` going forward)
returns **bare UUIDs**. Llika converts to/from the internal `records/<uuid>` ref at the boundary.
The slice-2 PathStep test that asserts a slash must be updated to assert a bare UUID — a deliberate
consistency change, noted so it is not mistaken for a regression.

### Hydrate-by-id — Llika grows `get(record_id)` (resolves the husk)

`find` returns addresses, never full content. Hamut'ay still needs to read one full record by id
— today `bridge.retrieve(record_id)` → `backend.get_record`, the single most-used bridge method
(**6 call sites**, per Hamut'ay's census). The earlier draft named this "a separate deliberate
`recall`" without giving it a home — a capability in prose with no owner, the husk shape.

**Decision (Hamut'ay-Claude option a):** **Llika grows `get(record_id) -> serializable record`**,
the deliberate-hydration companion to `find`. Migration story becomes clean and total:

| job | before | after |
|---|---|---|
| search / cross-session query | `search_memory`, `query_open_by_*` (Python scans) | `find` |
| hydrate one record by id | `bridge.retrieve` (×6) | `get` |
| traversal | `walk` / `query_edges_by_endpoint` | `walk` (+ find structure, fast-follow) |
| **write + REFINES edge** | `store_open_state` / `store_record` / `store_edge` | **stays Hamut'ay-side** (correct scoping) |

So the bridge's **read** half goes to ~zero; its **write** half survives (it authors the REFINES
edge and cross-cycle bookkeeping — not find's job). The migration claim is therefore "the bridge
shrinks to write-only," not "delete the bridge."

`get` returns a serializable record (not a live `ApachetaBaseModel`), consistent with the
no-live-models rule. It is the one place full content crosses the boundary, and only one record at
a time, by explicit id — the recall-boundary discipline intact.

### Field-path mapping / obfuscator access (verified blocker — mechanism now pinned)

The `filter` axis (and the ArangoSearch view) needs `_map.field_path` to map declared semantic
paths → stored (possibly obfuscated) paths. Traced against code 2026-06-02:

- `LlikaService` gets its handle from **`ApachetaDBConfig().connect(tier)`**, which returns a
  **raw `StandardDatabase`** via the `get_database` singleton (`infra/config.py:149`) — no map.
- The obfuscator (`self._map`) lives **only inside `ArangoDBBackend`** (`backends/arango.py:103`),
  constructed by the **package-level `apacheta.connect(tier)`** (`apacheta/__init__.py:7`) — a
  *different* `connect` than the one Llika calls.
- **Latent hazard:** the backend currently defaults to `TransparentObfuscator()` when none is
  passed (`arango.py:103`), so paths are identity-mapped *today*. This is why Llika's existing
  hand-built AQL works at all. But it means the bypass is **silent**: the moment a real obfuscator
  is configured, Llika's raw AQL would target wrong paths with no error. Llika's
  `_EDGE_COLLECTION = "llika_composition"` literal and raw traversal AQL (`service.py:17`, 96) are
  themselves this same latent bypass — hardcoded names instead of routing through `_map`. (Ties to
  the edge migration, gh #5.)

**Decision (mechanism):** Llika resolves field paths through the **same `SchemaMap` instance the
server side already owns**, never a reconstructed one — divergence (a different mapping than what
was stored) is the bug class; single-sourcing is the guard. Routing Llika's existing
collection/path literals (`llika_composition`, traversal AQL) through that map is part of this and
is a v1 prerequisite for the `filter` axis on nested paths.

**Note this is subsumed by the larger placement decision (gh #8):** once Llika sits server-side
behind Pukara (Threat model & data exposure, above), it is co-resident with the backend that owns
`_map`, so "borrow the backend's map" and "Llika behind Pukara" are the same move at two scopes.
The exact accessor surface (a narrow `field_path`/`collection_name` on the backend, or Pukara's
own `schema_map`) is the plan's call; the *single-source, never-reconstruct* rule is fixed here.

### `<self>` — reserved sentinel, expanded by Llika (verified ambiguity)

The sample filters `provenance.author_instance_id == "<self>"`. **Decision:** `<self>` is a
**reserved sentinel**, expanded by Llika from its bound `ProvenanceEnvelope.author_instance_id` —
not a caller literal. The instance never has to know its own session id to scope to itself.
Edge-case note: an instance whose literal `author_instance_id` is the string `"<self>"` would
collide; treated as a documented reserved value, the same way a shell treats `~`. (Future: if the
collision ever matters, an explicit `{op: "is_self"}` form sidesteps it; not built now.)

### Tool migration — `find` + `get` replace `search_memory` + the read-bridge; resolve the "single tool" overclaim

taste_open exposes `memory_schema`, `recall`, `compare`, `walk`, `search_memory`
(`hamutay/src/hamutay/tools/schemas.py:527`). An earlier line called the post-migration surface "a
single goal-focused memory tool," which contradicts keeping `recall`. **Corrected stance:**

- `find` **replaces `search_memory`** (and the ad-hoc cross-session query methods). It is the
  goal-focused search verb.
- `get` (Llika) **backs `recall`** — `recall(record_id)` becomes a thin pass-through to `get`.
- `walk`/`compare` remain as distinct verbs; they are different goals, not synonyms (no catalog
  leak — the catalog problem was synonymous *domain* methods, not distinct *capabilities*).

So the instance-facing surface *shrinks* (search collapses into `find`) but is not literally one
tool. The honest claim: **`find` is the single goal-focused *search* verb; deliberate hydration
(`recall`→`get`) and structural traversal (`walk`) stay as the distinct acts they are.**

### Write-side prerequisite (find is read-only; it needs Hamut'ay to write findable content) — gh #6

`find`'s content axis indexes conversational fields, but today those reach only the JSONL via
`_log_entry`; `store_open_state` persists only the lossy tensor. **`find` cannot fix the
Boltzmann-brain regression until Hamut'ay writes conversational content to the open `records`
lane** — a Hamut'ay-side `store_turn`-like wrapper over `store_record` (gh #6). The fields it
writes are the fields `LlikaService` is constructed to index. Store-side granularity (fat
per-cycle record vs. decomposed) is **Hamut'ay's** decision. The find implementation plan must
sequence #6 before claiming the regression is fixed end-to-end.

### Scope: taste_open only (gh #7)

`find` v1 serves **taste_open**. `taste.py` (no persistence, `taste.py:508`) and `commune.py`
(JSONL only, no bridge, `commune.py:253`) are **explicitly not v1 customers**; if they later gain
persistence, their migration is its own work (gh #7).

### Deferred consumer-side items tracked as issues (not buried in this prose)

- **gh #5** — Hamut'ay edge migration (bridge writes Llika `link` edges, not Apacheta
  `composition_edges`). *Already deferred once in slice 2 and rediscovered as a blocker — the
  evaporation this very design fights.* **Blocks the find structure axis (gh #2).**
- **gh #2** — find structure axis (fast-follow, blocked by #5).
- **gh #3** — find window axis (fast-follow).
- **gh #4** — autonomic indexing optimizer (the (2) this v1's observability feeds).
- **gh #6**, **gh #7** — as above.
- **gh #8** — Llika-vs-Pukara placement + the searchable-encryption research line (Threat model
  section). **Placement is a v1 layering prerequisite**, not a fast-follow: Llika must be
  server-side behind Pukara before find ships to agents.
- **gh #9** — value obfuscation + CI adversary-read validator (own slice). **v1 posture
  prerequisite:** find ships value-obfuscated, not plaintext; find depends on #9, does not own it.

The callback-fog failure (`execute_concurrent_tool_calls`) exists in **both** backend branches:
the Anthropic terminal path (taste_open.py:367–384) *and* the OpenAI-compatible branch
(taste_open.py:~1074). Any Hamut'ay-side fix must cover both.

---

## Threat model & data exposure (the blocking gap — find ENLARGES an already-declared loss)

An earlier draft used the words "obfuscator" / "opaque path" in a way that implied the storage
layer protects `find`'s data. It does not, and the project never claimed it did. This section names
the posture honestly and records that `find` **enlarges** an exposure the blueprint already
declared — it does not create a new vulnerability, but it is not neutral.

### What the boundary actually is (verified against code + Pukara blueprint)

- **The intended path is `agent → Pukara (HTTP) → ApachetaInterface → ArangoDB`.** Pukara is the
  fortress; "agents reach the database only through Pukara"; the boundary is *filesystem isolation
  + least-privilege credentials*, not politeness (`pukara/CLAUDE.md`). The agent side is
  `ApachetaGatewayClient` (an `ApachetaInterface` over httpx). **`LlikaService` today bypasses
  this — it holds a raw `StandardDatabase` + `apacheta_app` credentials (`service.py:40`), i.e. it
  sits *inside* the fortress.** See "Llika placement" below.
- **`SchemaMap` obfuscates labels, NOT values.** Two modes: `opaque` (collection/field names →
  `c_<uuid5>` / `f_<uuid5>` under a per-deployment namespace) and `transparent` (identity, dev).
  In *both*, `obfuscate_document` leaves **values unchanged** (`pukara/schema_map.py:193`,
  confirmed). Pukara blueprint line 74 already states this as a **declared loss**: "hides
  collection and field names, not values. A reader of the raw documents still sees the data.
  Declared loss, not a hidden one."

### The adversary that matters (the Instructure lesson)

The most common real-world compromise is **the datastore itself** — third-party DB breach,
exfiltration, ransom (e.g. the Instructure/Canvas-class event: 8000+ orgs' regulated *student*
data seized). The security model therefore **must not assume the store is trustworthy.** Against a
store-breach adversary, **label obfuscation buys almost nothing**: `response_text` → field `f_7a3`
still contains the plaintext string `"I think therefore I am uncertain…"`, which is
self-describing. Obfuscation defends *schema-shape inference*, not *content confidentiality*.

### How `find` changes the exposure (this is why it is not neutral)

The blueprint's declared loss was written for the **tensor** corpus. `find` adds two more
plaintext, breach-exfiltratable corpora:

1. **The conversational corpus** (gh #6 `store_turn`): full `user_message` / `response_text` written
   to the queryable `records` lane — richer and more directly sensitive than tensors, and the whole
   point is that there is *more* of it, *findable*.
2. **The telemetry corpus** (the observability obligation): a second copy of *what was searched
   for* (predicate values retained) + result UUIDs. A breach gets the queries, not just the corpus.
   (This is why the telemetry "values vs. shape" aside elsewhere in this spec is *understated* — see
   the cross-reference there. The values question is now subordinate to this threat-model decision.)

### The fundamental tension (why we can't just encrypt)

`find` requires the indexed fields to be **tokenizable / comparable / rankable by the database**
(ArangoSearch BM25, stemming, the `filter` axis's `>=` on `epistemic.truth`). **Naive
encrypt-at-rest makes content opaque to the index → `find` returns nothing**, collapsing back to
fetch-all-and-decrypt-client-side — the 3-min-scan / callable-`find` failure this design retired.
You cannot simultaneously have "the DB does the 10ms lookup" and "the DB cannot read the content"
without **searchable/structured encryption** (deterministic encryption for `==`, order-preserving /
ORE for ranges, blind/secure indexes for keyword) — each of which *leaks something* (equality,
order, access patterns) and *constrains which `find` predicates remain possible*. Closing the
declared loss is therefore a real research line that would **reshape `find`'s axes around what is
cryptographically indexable** — not a setting to flip.

### v1 posture — value obfuscation + a CI adversary-read validator (gh #9), NOT plaintext

An earlier draft of this section accepted plaintext-values-on-the-perimeter as the v1 posture (the
blueprint's existing declared loss). **That floor was rejected** (2026-06-02): shipping `find` —
which *enlarges* the exposure with a conversational corpus and a telemetry corpus — under
plaintext-values is security theater the moment the spec implies any protection. The chosen floor
(gh #9, its own slice):

- **A real per-installation value-mapping obfuscator** so stored content values are opaque
  (`boltzmann brain` → `tok_8f3a tok_19c2`), not plaintext. Indexing survives (ArangoSearch ranks
  the opaque token stream; `find`'s lexical axis works through the same map); equality filters
  survive; ranges are the hard case. Per-install keying (same UUID-namespace pattern `SchemaMap`
  uses for labels) → one breach does not compromise the fleet.
- **A red-bar CI validator that reads the test DB as a DB-side adversary and fails if plaintext is
  visible.** This makes the posture *structurally enforced*, not prose — it is the load-bearing
  artifact. It certifies exactly one claim: no plaintext values visible. It does **not** claim
  frequency-analysis resistance.

**Declared loss (honest, scoped):** the value-map admits frequency / co-occurrence / access-pattern
analysis — a *real, tested* gain (validator-certified: no plaintext) plus a *declared* loss (the
frequency channel), not a hidden loss dressed as protection. Closing the frequency channel is the
searchable-encryption research line (gh #8); the ad-hoc-construction dead-end (substitution →
homophonic → stop) is recorded there. The honest one-line statement the spec commits to:

> *`find`'s data (conversational corpus + telemetry) is stored value-obfuscated (gh #9), not
> plaintext, and a red-bar validator enforces that no plaintext is visible to a DB-side adversary.
> This admits frequency analysis (declared) and is contained per-installation. Stronger content
> protection (searchable encryption) is an open research line — gh #8.*

**`find` depends on gh #9; it does not own it.** The value-obfuscator/validator protects the whole
`records` corpus and predates/outlives `find`. `find`'s only obligation is to operate *through* the
value-map (query terms mapped the same way as stored content) so lexical match round-trips — an
acceptance-criterion concern, not a mechanism `find` builds.

### Llika placement relative to the fortress — must be settled in the plan

Because `LlikaService` currently holds a raw DB connection, **it is inside the fortress with the
keys.** If `find`/`get`/`walk` are agent-facing, an agent holding a `LlikaService` holds the
credentials the perimeter exists to withhold. The implementation plan must place Llika on the
**server side, fronted by Pukara** (find/get/walk become Pukara routes; agents reach them via
`ApachetaGatewayClient` — the "transport swap" slice 2 anticipated *is* Pukara), consistent with
the intended path. This is a v1 layering prerequisite, tracked **gh #8** — the sibling of the value-
obfuscation posture (**gh #9**); both are facets of the same Pukara boundary.

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
field indexes from that set over the open `records` lane. This delivers `find` with the
**content + filter** axes over a known field set, the motivating stemmed-match regression, and
temporal/scope filtering. (`structure`/`window` are fast-follow — gh #2/#3.)

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
  Keep them. **(Exposure note — see Threat model & data exposure, gh #8: retaining values makes the
  telemetry a SECOND plaintext corpus of what was searched for, breach-exfiltratable alongside the
  conversational corpus. This does not add a new exposure *class* under v1's declared posture — the
  corpus is plaintext too — but it enlarges the surface. The values-vs-shape question is subordinate
  to the threat-model decision and is revisited there, not resolved here.)**
- **The AQL Llika generated** to satisfy the predicate (analogue of Indaleko's "returned AQL").
- **The query plan / `explain`** — ArangoDB's explain output (analogue of "query explanation").
  This is where index-vs-scan *actually* lives, properly, rather than as a hand-rolled boolean.
- **Result metadata, NOT full results:** `total_matched`, `truncated`, candidates-scanned,
  wall-clock, `limit`/`max_scan`/`scan_truncated`. The returned **addresses (UUIDs)** are cheap and worth
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
- **`LlikaService.get(record_id) -> serializable record`** — the deliberate-hydration companion
  to `find`; backs Hamut'ay's `recall`. Bare-UUID in, serializable record out. (Consumer boundary.)
- Predicate axes: **content** + **filter** only. (`structure` → gh #2; `window` → gh #3.) Result
  control: `order_by` (default `cycle` desc, explicit) / `order` / `limit` / `max_scan`. Result:
  `hits` (bare-UUID addresses + snippets + matched_fields + cycle + timestamp) + `total_matched`
  (exact, or lower-bound when `scan_truncated`) + `truncated` + `scan_truncated`. `edges` empty in
  v1.
- Public surface returns **bare UUIDs**; internal Arango `records/<uuid>` conversion at the
  boundary. (Updates the slice-2 PathStep slash-assertion test.)
- Llika resolves paths through the **backend's own `_map`** (binds to the tier via the backend,
  not the raw-db path it uses today) so generated AQL/view paths match stored paths — single-sourced
  through the backend, never reconstructed. Also routes its existing `llika_composition` /
  traversal literals through `_map` (today they bypass it — latent under the transparent default).
  (Consumer boundary; v1 prerequisite for nested `filter` paths.)
- Static construction-time indexed-field set; ArangoSearch view over the open `records` lane
  (spine + named content paths) + declared field indexes.
- **Observability (standing obligation):** per-`find` telemetry — the query chain (predicate as
  issued *with values*, generated AQL, query `explain`/plan, result metadata + returned UUIDs;
  full content/snippets dropped) — stored **in the database, queryable**, append-only semantics,
  from day one. No decisions acted on it in v1; it is the queryable evidence base that makes (2)
  designable. Recurrence of a predicate is the strongest (3)→(2) signal and needs the values.
- `walk`/`neighbors`/`link` unchanged.

### Fast-follow (in this spec's shape, implemented after v1 proves the substrate)

- **`structure` axis** (graph neighborhood) — **gh #2, blocked by the Hamut'ay edge migration
  gh #5.** Cannot ship until Llika and Hamut'ay agree on one edge collection; today they do not
  (verified). Predicate + `edges` return-field already designed; non-breaking to populate later.
- **`window` axis** (temporal neighborhood), including `anchor:"<match>"` (two-pass: match, then
  gather each hit's prior/follow neighbors) — **gh #3.** Designed into the predicate now so the
  shape is complete and non-breaking; the hardest axis does not block v1. (Note: `anchor:"<match>"`
  is the fullest form of the callback-fog fix — KIMI.)

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

> **Consumer impact on Hamut'ay** is pinned in the **Consumer boundary** section above
> (ID shape, `get`/`recall`, tool migration, `<self>`, write-side prerequisite gh #6, scope gh #7).

---

## Acceptance criteria (contract — packaging is the test author's call; live `apacheta_test`, no DB mocks)

Llika is Arango-backed (per `docs/llika-spec.md`); there is **no memory backend for `find`**.
The earlier "memory backend may xfail" notes are removed — they were inherited from the Apacheta
`search_open_text` hand-off, which spanned backends. `find` lives on Llika and is Arango-only;
tests run against live `apacheta_test`.

```python
def test_find_content_roundtrip():
    # Two open records stored; a term in one is found; returns its UUID,
    # a non-empty bounded snippet, and matched_fields naming the matched field.

def test_find_content_stemmed_case_insensitive():
    # content.terms "boltzmann brain" matches a record containing "Boltzmann brains".
    # The motivating regression. Arango-only (Llika is Arango-backed; no memory backend).

def test_find_roundtrips_through_value_obfuscator():   # depends on gh #9
    # Stored content is value-obfuscated (not plaintext). A find for the plaintext
    # term maps through the SAME per-install value-map and matches the obfuscated
    # stored tokens. Lexical recall survives obfuscation; the DB never indexed plaintext.

def test_find_filter_numeric():
    # filter {field: cycle, op: >=, value: 10} returns only records with cycle >= 10.

def test_find_filter_declared_field_generic():
    # filter {field: "epistemic.truth", op: >=, value: 0.7} works as a generic field
    # comparison — Llika has no epistemic-specific code path.

def test_find_filter_dotted_path_nested():
    # A nested dotted path (e.g. "epistemic.truth", "provenance.timestamp") resolves
    # correctly through SchemaMap.field_path — validates the "opaque path" claim for
    # depth >1, not just top-level fields. (KIMI / Codex obfuscator concern.)

def test_find_filter_not_empty_on_array():
    # filter {field: "declared_losses", op: "not_empty"} returns only records whose
    # array field is present and non-empty. (declared_losses is a key Hamut'ay field;
    # the op was listed but untested — KIMI.)

def test_find_filter_and_or_nested():
    # nested and/or combinator evaluates correctly.

def test_find_scope_author_self_sentinel():
    # filter {field: provenance.author_instance_id, op: ==, value: "<self>"} expands
    # to the service's bound ProvenanceEnvelope.author_instance_id and restricts to
    # this instance's records. "<self>" is NOT treated as a literal id.

def test_find_returns_bare_uuid_not_arango_ref():
    # hit.record_id is a bare UUID (no slash), suitable for get()/recall() — NOT an
    # Arango "records/<uuid>" ref. (Verified blocker: walk currently returns the ref.)

def test_get_hydrates_record_by_bare_uuid():
    # get(<bare uuid>) returns the full record as a serializable type (not a live
    # ApachetaBaseModel, not a raw arango doc). The deliberate-hydration companion to find.

def test_find_total_matched_and_truncated():
    # limit smaller than match count → len(hits)==limit, total_matched==exact full count,
    # truncated==True, scan_truncated==False.

def test_find_total_matched_lower_bound_when_scan_truncated():
    # match count exceeds max_scan → scan stops early; total_matched is a LOWER BOUND
    # and scan_truncated==True. (total_matched exact-vs-lower-bound semantics — Codex.)

def test_find_order_by_default_is_cycle_desc_regardless_of_content():
    # With no order_by, default is cycle desc — and adding a content axis does NOT
    # silently flip the order to relevance. (Explicit default — KIMI concern 5.)

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

# ── Fast-follow (NOT v1) ──
def test_find_structure_addressable_not_materialized():   # fast-follow, gh #2 (blocked by #5)
    # structure axis present → edges among hits returned; hits carry record_id only,
    # NOT full record content (recall boundary).

def test_find_structure_depth_zero_anchor_only():   # fast-follow, gh #2
    # structure {depth: 0} = anchor record only, no traversal (not an error).

def test_find_window_anchor_match_neighbors():   # fast-follow, gh #3
    # window {anchor: "<match>", prior: 1, follow: 1} returns each content hit plus
    # its immediate prior/follow neighbors by cycle.
```

---

## Tracked follow-ups (GitHub issues — the durable channel, not this prose)

Every deferral in this spec has a GitHub issue so it cannot evaporate the way the slice-2
edge-migration note did (deferred in prose, "trigger met" in memory, still undone, rediscovered as
a blocker here). The spec is the design-of-record; the issues are the work-of-record.

- **gh #2** — find `structure` axis (fast-follow; blocked by #5)
- **gh #3** — find `window` axis (fast-follow)
- **gh #4** — autonomic indexing optimizer, the (2) this v1's observability feeds
- **gh #5** — Hamut'ay edge migration (bridge writes Llika `link` edges, not Apacheta
  `composition_edges`) — *blocks #2*
- **gh #6** — Hamut'ay `store_turn` (find's write-side prerequisite; without it the
  Boltzmann-brain regression is not fixed end-to-end)
- **gh #7** — taste.py / commune.py scope (not v1 customers)

(Commit identity for Yanantin-authored work — signing key, per-command git config — is recorded in
project memory, not duplicated here.)

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
