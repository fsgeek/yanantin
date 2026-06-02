# Llika Traversal Interface — Design

*Brainstormed 2026-06-01 between Tony Mason (PI) and Claude Opus 4.8
(yanantin's ward instance). Co-designed through the brainstorming flow;
decisions measured against the **real customer** (hamut'ay's existing graph
tools) rather than the spec's prior abstraction. **Not** independently
validated — the design was shaped collaboratively; the tests will be authored
independently by Codex.*

## Goal

Turn Llika's traversal surface into the **RPC-shaped memory interface** that
hamut'ay calls instead of owning its own graph primitives. Replace the
callable-predicate `find` (un-serializable, un-promotable) with a structural
traversal (`walk`/`neighbors`) whose every argument and result crosses a wire
cleanly. Shape the boundary now so promoting library → network service is a
*transport swap*, not a redesign.

This is the second Llika slice. The first
(`2026-05-31-llika-taste-memory-slice-design.md`) proved store→link→find over
real storage; it shipped a `find(predicate: Callable[[dict], bool])` and
*named the flaw in the same breath* — "a predicate is the thing you already
knew to ask about." **This slice retires that callable.** The earlier spec's
deferred "HTTP predicate protocol" is hereby resolved: it was a solution in
search of a problem, because the real customer filters on edge **structure**
(direction, depth, relation type), never on vertex content.

## Why this shape — the forcing function

ArangoDB has **no fine-grained access control** (verified 2026-06-01: no
ArangoSearch views, the only enforcement is per-database user grants). Tenant
isolation and append-only/frozen invariants therefore *cannot* live in the
database — they must live in a layer **above** it. That layer is yanantin's
memory interface. Since that interface is what eventually becomes the trust
boundary, it must be RPC-shaped from the start: serializable in/out, no raw
database handle in any caller's hands, tenant bound by the *service*, not named
by the *caller*.

## Ownership boundary (the architecture)

**Yanantin is the native memory service.** Graph-walking is a *memory*
concern, and yanantin owns memory. Llika provides the primitives: native edge
storage, `link`, and the traversal surface.

**Hamut'ay is a customer.** It *decides* when a memory or edge is born — it
alone witnesses composition, recall, and injection — and calls yanantin to
persist and traverse. It should own **no** graph primitive. Hamut'ay's current
`tools/graph.py` storage logic, `apacheta_bridge.py` hand-built
`tiksi.CompositionEdge`s, and `_walk_by_record_id` (which its own comments flag
as a placeholder "AQL graph traversal will give better semantics later") are
artifacts of the two repos having been built separately. They dissolve into
client calls. *This slice does not modify hamut'ay* — it builds the interface
hamut'ay will migrate to.

Tiksi exists because yanantin and willay are entangled and needed shared
models neither owns. Hamut'ay must **not** inherit that entanglement: it calls
a clean memory interface across a boundary; it does not import yanantin's
internal models to hand-construct edges (which `apacheta_bridge.py` does today
— that hand-construction *is* the entanglement leaking).

## The three boundary rules

1. **Tenant-bound at construction.** The service is constructed against one
   tenant — a memory space resolved to a database handle it owns *internally*,
   via the existing `get_database` singleton. **No method takes `db` or
   `db_name`.** A caller has no way to name another tenant's space. In-process
   today (tenant id passed at construction); promoted, the tenant comes from
   authenticated identity and the method signatures are byte-identical.
2. **Serializable in, serializable out.** Every argument and every return value
   is JSON-representable. No callables. No `StandardDatabase`. No internal
   pydantic models cross the boundary.
3. **No internal leakage.** Results are clean domain shapes — record-id
   strings and edge metadata — never raw ArangoDB documents (`_id`/`_rev`).

Promotion to a network service = serve the same signatures over HTTP, derive
the tenant from auth. Nothing else changes. The in-process library and the
future RPC service are **one interface, two transports.**

## The service surface

The service keeps the slice-1 name **`LlikaService`** (Llika = Quechua *net /
web / fine mesh* — "the paths between the cairns"; the service *is* the net in
use). It is constructed bound to a tenant and a provenance envelope:

    LlikaService(tenant: <space id>, provenance: ProvenanceEnvelope)

The change from slice 1 is internal: the `db` no longer crosses the
constructor (the service resolves its own handle from the tenant via the
`get_database` singleton). That is not a reason to rename the net.

**Naming rule (project convention):** names are drawn from Quechua (and, for
hamut'ay's LLM-facing *tool* names, Indonesian) — deliberately, because those
namespaces don't collide. Pragmatically: a generic name like `MemoryGraph`
collides on PyPI/import graphs *and* collides with the model's semantic priors
about what such a thing does (the same hazard the tool-name-cue-conflict line
studies). Quechua names are effectively unique in the Python ecosystem and
carry no unintended priors. The metaphor is a bonus; non-collision is the
load-bearing reason.

**Fate of the slice-1 code:** `LlikaService.link` survives largely intact
(re-homed behind the tenant-bound constructor and returning `EdgeResult`).
`LlikaService.find` (callable predicate) is **removed**, replaced by
`walk`/`neighbors`. The `CompositionEdge` model survives unchanged; `Path` is
reshaped into `PathResult`/`PathStep`. The slice-1 integration tests that
exercise `find` are superseded — the independent author rewrites them against
`walk`/`neighbors` (the old `find` tests are deleted, not left dangling).

### `link(from_id, to_id, relation_type, **fields) -> EdgeResult`

Create one immutable native edge `from_id → to_id` in the tenant's
`llika_composition` edge collection (created if absent). `from_id`/`to_id` are
record-id strings; `relation_type` is a `RelationType` name (string).
Append-only: no update, no delete. Returns a clean `EdgeResult`, not the raw
arango doc, not the internal `CompositionEdge`. This is what hamut'ay's
`annotate_edge` and its auto-spine call instead of hand-building edges.

### `walk(start_id, direction, depth, relation_types=None, max_results=50) -> list[PathResult]`

The core traversal — **the AQL traversal hamut'ay's placeholder is waiting
for.** Structure only; no content predicate.

- `direction`: `"forward"` | `"backward"` | `"both"` → AQL
  `OUTBOUND`/`INBOUND`/`ANY`. (Hamut'ay's exact vocabulary.)
- `depth`: int, maximum hops.
- `relation_types`: optional list of `RelationType` names; `None` follows all.
- `max_results`: cap on returned paths (observable truncation, not error).

Returns a list of `PathResult`. The path *is* the answer: each result carries
every intermediate vertex it traversed through, not just the terminal.

### `neighbors(start_id, direction, relation_types=None) -> list[PathResult]`

Depth-1 convenience: `walk(start_id, direction, depth=1, relation_types=...)`.
A thin wrapper — "who is adjacent" is the most common question and earns a
verb. No new logic.

### Cut: `find` and `path`

- `find` (callable predicate) is **deleted**. Content filtering is not a
  service concern this slice; a caller filters returned paths itself if it
  ever needs to.
- `path` (point-to-point A→B reachability) is **not built** — hamut'ay's walk
  is always "from here, outward," never "is there a route A→B." YAGNI until a
  customer needs it.

## Result shapes (the wire contract)

All JSON-representable; none carry arango `_id`/`_rev`.

**`EdgeResult`** (from `link`):

    edge_id: str          # the edge's UUID
    from_id: str          # record-id ref
    to_id: str            # record-id ref
    relation_type: str    # RelationType name
    created_at: str       # ISO-8601

**`PathStep`** — one hop:

    record_id: str        # the vertex reached at this step
    relation_type: str    # the edge type that reached it
    field_names: list[str] # the vertex's content field names — SHAPE, not values

**`PathResult`** — an ordered walk:

    start_id: str
    steps: list[PathStep]  # traversal order; steps[-1] is the far end

`field_names` is deliberately **shape, not contents**: which fields a reached
record has, never their values. A caller wanting values issues a separate
retrieve by `record_id`.

### Cut from results: `summary` and `session`

Hamut'ay's current walk step carries `summary` (a content précis) and
`session` (from `provenance.author_instance_id`). Both are removed from the
service result:

- **`session`** is provenance-interpretation the structural boundary must not
  do, and nothing depends on it. Cut entirely.
- **`summary`** is a *navigational affordance the instance uses* (to know what
  a hop is "about" without a second retrieve), but computing it requires
  interpreting vertex content — which the service must not do. It stays a
  **caller-side concern**: hamut'ay's tool layer computes `summary` from the
  returned `record_id`s exactly as `_step_summary` does today. The affordance
  is preserved; the *interpretation* lives where it belongs (the customer).

## Consumer impact: Hamut'ay (obligation named, note deferred)

Adopting this interface imposes a bounded migration on hamut'ay — a
*relocation* of work it already does, plus deletions:

1. `walk` returns `{record_id, relation_type, field_names}` per step — **no
   `summary`, no `session`.** Hamut'ay's tool layer computes `summary` itself
   (it already has `_step_summary`), now fed by service-returned record_ids.
   **This is the real friction point** — the instance-facing `summary`
   affordance must be re-attached caller-side.
2. The bridge stops hand-building `tiksi.CompositionEdge` and calls `link`.
3. `_walk_by_record_id` (the self-flagged placeholder) is deleted in favor of
   `walk`.
4. No `db` handle crosses to hamut'ay; it holds a tenant-bound service.

**The migration note itself is deferred until this interface lands green** —
written against the *real, tested* method signatures, not these intended ones
(which may shift slightly in implementation). Trigger condition: slice green.
This is a named debt with a concrete trigger, not an open-ended someday.

## What this slice proves — stated precisely

It proves a **serializable, tenant-bound, structurally-filtered graph
traversal** over real storage: that `walk`/`neighbors` return correct ordered
paths (carrying intermediates), filtered by direction/depth/relation, capped
observably, with results that contain nothing un-serializable and no arango
internals. It proves the boundary is **RPC-ready** — the contract is
transport-agnostic.

It does **not** prove multi-tenant *enforcement* (one tenant exists; isolation
is structural-by-construction, not adversarially tested against a hostile
caller) and does **not** prove the network transport (there is none yet). Those
are real and deferred, below.

## Declared losses (named, not eliminated)

- **Invariant enforcement is only as strong as the boundary the caller
  respects.** In-process, a determined caller that obtains a raw handle by
  other means could still bypass append-only. True enforcement arrives only
  with the network transport, where the caller cannot reach the DB at all. This
  slice makes the *interface* correct; it does not make the *process boundary*
  impermeable.
- **No content/full-text search exists** (verified 2026-06-01: no ArangoSearch
  views, no analyzers; "search" today is hamut'ay's `_value_contains` Python
  substring scan over already-retrieved records). This slice is finding-by-
  *structure*; finding-by-*content* is a genuine, deliberate gap. It is a
  *separate future slice* (ArangoSearch view + analyzer, or embeddings), not a
  shortfall of this one.
- **`max_results` truncates in traversal order**, not by relevance — there is
  no relevance signal without a content index. Truncation is observable, not
  silent.

## Named follow-ups (logged, not built)

- **Network transport** — serve the same signatures over HTTP/RPC; tenant from
  authenticated identity. The whole point of the shape; built when a second
  customer or a real trust boundary forces it.
- **Content-search slice** — full-text/semantic search as a sibling method on
  the memory interface.
- **Hamut'ay migration** — re-point its graph tools at this interface; delete
  its parallel primitives. Note authored once this slice is green.
- **`path` (A→B reachability), `ProvenanceEdge`, `AttestationEdge`** — built
  when pulled by a real need (AttestationEdge gated on Willay-as-web-service).
- **Retraction/supersession** — parked until a real instance shows what
  correction means; not designed against synthetic data.

## What's not in scope

Modifying hamut'ay. The network transport. Content search. Multi-tenant auth.
Migration of the existing 259 flat `composition_edges`. Edge types beyond
`CompositionEdge`. Any non-ArangoDB backend.
