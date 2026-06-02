# Llika Traversal Interface — Slice Design

*Brainstormed 2026-06-01 between Tony Mason (PI) and Claude Opus 4.8
(yanantin's ward instance). Co-designed through the brainstorming flow;
decisions measured against the **real customer** (hamut'ay's existing graph
tools). **Not** independently validated — tests will be authored independently
by Codex.*

> **Architecture lives in `docs/llika-spec.md`** (Design Principles, updated
> 2026-06-01). The memory-service ownership boundary, the three RPC-boundary
> rules (tenant-bound / serializable / no-leak), the ArangoDB-no-access-control
> forcing function, the Quechua naming rule, and the no-content-index gap are
> **standing decisions** recorded there — they govern every memory-interface
> slice, not just this one. This spec is **only the buildable slice** and
> assumes those decisions.

## Goal

Replace the callable-predicate `find` with a structural traversal
(`walk`/`neighbors`) that honors the three boundary rules, so Llika becomes the
RPC-shaped interface hamut'ay calls instead of owning its own graph primitives.

Buildable surface: **three methods, three result shapes, delete one callable.**
Small by design — the weight of this work was the architecture (now in
`llika-spec.md`), not the code.

## The service surface

`LlikaService` (name retained — Quechua, non-colliding; see `llika-spec.md`
Naming). Constructed bound to a tenant + provenance; resolves its own db handle
internally via `get_database`. **No method takes `db`/`db_name`.**

    LlikaService(tenant: <space id>, provenance: ProvenanceEnvelope)

### `link(from_id, to_id, relation_type, **fields) -> EdgeResult`

Create one immutable native edge `from_id → to_id` in the tenant's
`llika_composition` edge collection (created if absent). `from_id`/`to_id` are
record-id strings; `relation_type` a `RelationType` name. Append-only.
Returns `EdgeResult` — not the raw arango doc, not the internal
`CompositionEdge`.

### `walk(start_id, direction, depth, relation_types=None, max_results=50) -> list[PathResult]`

The core AQL traversal — structure only, no content predicate.

- `direction`: `"forward"` | `"backward"` | `"both"` → AQL `OUTBOUND` /
  `INBOUND` / `ANY` (hamut'ay's exact vocabulary).
- `depth`: int, max hops.
- `relation_types`: optional list of `RelationType` names; `None` follows all.
- `max_results`: cap on returned paths (observable truncation, not error,
  in traversal order — there is no relevance signal without a content index).

Each `PathResult` carries every intermediate vertex traversed, not just the
terminal. The path *is* the answer.

### `neighbors(start_id, direction, relation_types=None) -> list[PathResult]`

Depth-1 convenience: `walk(..., depth=1)`. Thin wrapper, no new logic.

### Cut

- **`find`** (callable predicate) — deleted. A callable can't cross a wire,
  and the customer filters by edge *structure*, not vertex *content*.
- **`path`** (A→B reachability) — not built. Hamut'ay's walk is always
  "from here, outward." YAGNI until pulled.

## Result shapes (the wire contract)

All JSON-representable; none carry arango `_id`/`_rev`.

**`EdgeResult`** (from `link`):

    edge_id: str          # the edge's UUID
    from_id: str          # record-id ref
    to_id: str            # record-id ref
    relation_type: str    # RelationType name
    created_at: str       # ISO-8601

**`PathStep`** — one hop:

    record_id: str         # the vertex reached
    relation_type: str     # the edge type that reached it
    field_names: list[str] # the vertex's field NAMES — shape, not values

**`PathResult`** — an ordered walk:

    start_id: str
    steps: list[PathStep]  # traversal order; steps[-1] is the far end

`field_names` is shape, not contents: which fields a record has, never their
values. A caller wanting values issues a separate retrieve by `record_id`.

### Cut from results: `summary` and `session`

- **`session`** — provenance-interpretation the structural boundary must not
  do, and nothing depends on it. Cut.
- **`summary`** — a navigational affordance the *instance* uses, but computing
  it requires interpreting vertex content. Stays **caller-side**: hamut'ay's
  tool layer computes it from returned `record_id`s (it already has
  `_step_summary`). The affordance survives; the interpretation lives with the
  customer. **This is hamut'ay's main migration friction (below).**

## Fate of the slice-1 code

- `LlikaService.link` survives, re-homed behind the tenant-bound constructor,
  returning `EdgeResult`.
- `LlikaService.find` (callable) **removed**, replaced by `walk`/`neighbors`.
- `CompositionEdge` model **unchanged**. `Path` reshaped into
  `PathResult`/`PathStep`.
- Slice-1 integration tests exercising `find` are **deleted** (not deprecated)
  — the independent author rewrites against `walk`/`neighbors`.

## Consumer impact: Hamut'ay (obligation named, note deferred)

A bounded migration — relocation of work it already does, plus deletions.
*This slice does not modify hamut'ay.*

1. `walk` returns `{record_id, relation_type, field_names}` per step — **no
   `summary`, no `session`.** Hamut'ay re-attaches `summary` caller-side. **The
   real friction point.**
2. The bridge stops hand-building `tiksi.CompositionEdge` and calls `link`.
3. `_walk_by_record_id` (its self-flagged placeholder) is deleted for `walk`.
4. No `db` handle crosses to hamut'ay; it holds a tenant-bound service.

**The migration note is deferred until this slice lands green** — written
against real, tested signatures, not these intended ones. Trigger: green. A
named debt with a concrete trigger, not an open-ended someday.

## What this slice proves

A **serializable, tenant-bound, structurally-filtered graph traversal** over
real storage: `walk`/`neighbors` return correct ordered paths (carrying
intermediates), filtered by direction/depth/relation, capped observably, with
results containing nothing un-serializable and no arango internals. It proves
the boundary is **RPC-ready**.

It does **not** prove multi-tenant *enforcement* (one tenant exists; isolation
is structural-by-construction, not adversarially tested) nor the network
transport (none yet). Both deferred — see `llika-spec.md` and below.

## Declared losses (slice-specific)

- **Invariant enforcement is only as strong as the process boundary the caller
  respects.** True enforcement arrives with the network transport, where the
  caller cannot reach the DB. This slice makes the *interface* correct, not the
  *process boundary* impermeable.
- **`max_results` truncates in traversal order, not by relevance** — no
  relevance signal exists without a content index (a separate slice).

## Named follow-ups (logged, not built)

- **Network transport** — same signatures over HTTP; tenant from auth.
- **Content-search slice** — full-text/semantic, sibling method.
- **Hamut'ay migration** — re-point its tools here; delete its parallel
  primitives. Note authored once this slice is green.
- **`path`, `ProvenanceEdge`, `AttestationEdge`** — built when pulled
  (AttestationEdge gated on Willay-as-web-service).
- **Retraction/supersession** — parked until a real instance shows what
  correction means.

## What's not in scope

Modifying hamut'ay. Network transport. Content search. Multi-tenant auth.
Migrating the 259 flat `composition_edges`. Edge types beyond `CompositionEdge`.
Any non-ArangoDB backend.
