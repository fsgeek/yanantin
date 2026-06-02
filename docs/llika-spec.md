# Llika — Graph-Structured Index Service

*Llika (Quechua: net, web, fine mesh). The paths between the cairns.*

*Design date: 2026-03-31. Status: approved, not yet implemented.*

## What It Is

A graph-structured index service for yanantin. Sits alongside Apacheta
(vertex/document store) and uses ArangoDB's native graph capabilities
for edge storage and traversal.

Apacheta stores authored compressions. Llika stores the relationships
between them. Apacheta doesn't know about Llika. Llika knows about
Apacheta. The dependency is one-directional.

## Why It Exists

The taste experiment (hamut'ay) produces self-structured tensors whose
fields emerge over time. Storing them was unblocked by opening
ApachetaBaseModel to `extra="allow"` (2026-03-31). But storage isn't
enough — the model needs to *find* through graph traversal, not just
search by query string.

Finding vs. searching: search returns what you asked for. Finding
discovers what you didn't know to ask about. A graph traversal
starting from a tensor can surface a scout report from a model the
taste instance has never seen, about code it wasn't thinking about,
connected through three hops of relationship. No query string gets
you there.

This is Indaleko's core insight applied to AI-side data: "if the
results are more than 50 entries, you need a better finding strategy."

## Design Principles

- **ArangoDB-only.** No multi-backend abstraction. Graph traversal is
  why we chose ArangoDB. InMemory and DuckDB don't get graph features.
  We're more likely to add replication/sharding than switch databases.

- **Thin service, no ABC.** `LlikaService` is a concrete class. If a
  second backend materializes, we extract an interface then. YAGNI.
  *(Name retained deliberately — Quechua, non-colliding. See "Naming"
  below and `memory/project_naming_convention.md`.)*

- **Singleton database — but the handle does not cross to callers.**
  *(Superseded 2026-06-01. Original principle: "one connection per
  process, shared between Apacheta and Llika; Llika discovers vertex
  collections from the shared database handle." That remains true for
  the connection layer — `get_database` is still the one connection per
  resolved target.)* What changed: **`LlikaService` no longer accepts a
  `db` handle from its caller, and never hands one out.** It is
  constructed bound to a *tenant* (a memory space) and resolves its own
  handle internally via the `get_database` singleton. Forcing function:
  ArangoDB has **no fine-grained access control** (verified 2026-06-01:
  no ArangoSearch views; the only enforcement is per-database user
  grants). Tenant isolation and the append-only/frozen invariants
  therefore cannot live in the database — they must live in the
  interface *above* it. A caller that holds a raw handle can bypass
  every invariant, so callers get the service, never the handle.

- **RPC-shaped boundary (the memory interface is a service-in-waiting).**
  *(Added 2026-06-01.)* Yanantin **is** the native memory service;
  graph-walking is a memory concern and yanantin owns memory. Other
  projects (hamut'ay first) are **customers** — they decide *when* a
  memory/edge is born (they alone witness composition, recall,
  injection) and call yanantin to persist and traverse. They own **no**
  graph primitive. Because this interface eventually becomes the trust
  boundary, it is RPC-shaped from the start, by three rules every
  memory-interface method must honor:
    1. **Tenant-bound at construction** — no method takes `db`/`db_name`;
       the caller cannot name another tenant's space.
    2. **Serializable in, serializable out** — no callables, no
       `StandardDatabase`, no internal pydantic models cross the boundary.
       (This is why the slice-1 `find(predicate: Callable)` is retired:
       a callable cannot cross a wire.)
    3. **No internal leakage** — results are clean domain shapes
       (record-id strings + edge metadata), never raw arango docs.
  Promoting library → network service is then a *transport swap*: same
  signatures over HTTP, tenant from authenticated identity. The
  in-process library and the future RPC service are one interface, two
  transports. *(This keeps the entanglement out of customers: hamut'ay
  must not import yanantin's internal models to hand-build edges — it
  calls a clean interface. Tiksi exists because yanantin and willay are
  entangled; customers must not inherit that.)*

- **Frozen, open-schema, append-only.** Same philosophy as
  ApachetaBaseModel. Edges are immutable once created. No update, no
  delete. Corrections happen by creating new edges, same as tensors.
  `extra="allow"` on all edge models.

- **One-directional dependencies.** Apacheta doesn't know about Llika.
  Willay doesn't know about Llika. Jabberwock doesn't know about
  Llika. Llika knows about all of them, but they don't know about it.
  Integration happens at the caller level.

- **Naming: Quechua, for non-collision.** *(Recorded 2026-06-01.)*
  Package/service/class names are Quechua (hamut'ay's LLM-facing *tool*
  names are Indonesian). The load-bearing reason is non-collision, not
  metaphor: a generic name like `MemoryGraph` collides on PyPI/the
  import graph AND with the model's semantic priors about what such a
  thing does (the hazard the tool-name-cue-conflict line studies).
  Quechua names are effectively unique in the Python ecosystem and carry
  no unintended priors. *Llika* = net / web / fine mesh — the paths
  between the cairns; the service is the net in use.

- **Finding-by-structure only; no content index yet.** *(Recorded
  2026-06-01.)* Llika finds by *structure* (graph traversal). It does
  **not** find by *content* — there is no full-text/semantic index
  (verified 2026-06-01: no ArangoSearch views, no analyzers; "search"
  today is a Python substring scan over already-retrieved records). A
  content index is a real, deliberate gap and a *separate future slice*
  (ArangoSearch view + analyzer, or embeddings), not a shortfall of the
  traversal surface.

## Module Structure

```
src/yanantin/llika/
    __init__.py          # Public API exports
    models.py            # Edge models (4 types), traversal result models
    service.py           # LlikaService — thin class, singleton DB handle
    edges.py             # Edge creation: link(), provenance auto-attachment
    traversal.py         # neighbors(), walk()  [find()/path() cut 2026-06-01:
                         #   find's callable predicate can't cross a wire and
                         #   the customer filters by edge STRUCTURE, not vertex
                         #   content; path (A->B reachability) is YAGNI until
                         #   pulled. Traversal is structure-only:
                         #   direction(forward/backward/both) + depth + relation_type.]
    migration.py         # Existing composition edges → native graph
    __main__.py          # CLI: explore, traverse, path operations
```

## Edge Types

Four edge types, each mapping to a native ArangoDB edge collection.
All edges share common fields, then specialize.

### Common fields (every edge)

| Field | Type | Description |
|-------|------|-------------|
| `_from` | string | ArangoDB vertex reference (e.g., `tensors/uuid`) |
| `_to` | string | ArangoDB vertex reference |
| `id` | UUID | Same pattern as Apacheta |
| `created_at` | datetime | Timestamp |
| `provenance` | ProvenanceEnvelope | Who created this edge, when, from what context |

All edge models inherit from `ApachetaBaseModel` (frozen=True,
extra="allow"). Same base, same philosophy. No separate LlikaBaseModel.

### 1. CompositionEdge (`llika_composition`)

| Field | Type | Description |
|-------|------|-------------|
| `relation_type` | RelationType enum | COMPOSES_WITH, CORRECTS, BRIDGES, etc. (9 types) |
| `ordering` | int | For non-commutative composition |
| `authored_mapping` | str or None | Bridge composition description |

Direct migration from existing flat documents in Apacheta. Same
fields, new storage as native ArangoDB edges.

### 2. AttestationEdge (`llika_attestation`)

| Field | Type | Description |
|-------|------|-------------|
| `claim_text` | str | What was claimed |
| `evidence_ref` | str | DOI, URL, or content hash of evidence |
| `scores` | dict | T/I/F from Willay evaluation |
| `receipt_id` | UUID | Link back to the Willay receipt |

`_from` = tensor containing the claim. `_to` = evidence entity or
another tensor.

### 3. ProvenanceEdge (`llika_provenance`)

| Field | Type | Description |
|-------|------|-------------|
| `role` | enum | AUTHORED, REVIEWED, ATTESTED, STORED, DISPATCHED |
| `context` | dict | Model name, session ID, machine ID, cycle number (freeform) |

`_from` = actor entity. `_to` = artifact they produced.

### 4. MembershipEdge (`llika_membership`)

| Field | Type | Description |
|-------|------|-------------|
| `relationship` | str | "instance_of", "runs_on", "part_of", "member_of" |

`_from` = member entity. `_to` = group entity. Maps to Jabberwock's
Rath concept.

### Graph definition

One named ArangoDB graph (`llika`) containing all four edge collections
and all relevant vertex collections (tensors, activity facts, Jabberwock
entities).

## Service Interface

### Constructor

```python
class LlikaService:
    def __init__(self, db: StandardDatabase)
```

Takes the singleton database handle. Same handle Apacheta's
ArangoDBBackend uses. Discovers vertex collections from the shared
database rather than requiring separate configuration.

### Write (1 method)

**`link(from_id, to_id, edge_type, **kwargs) → edge`**

Create an edge. The edge type determines the collection. kwargs become
fields on the edge (open schema). Provenance is attached automatically
from the service's context. Immutable — no update, no delete.

### Traversal (4 methods)

**`neighbors(vertex_id, edge_types=None, direction=ANY) → list[Neighbor]`**

One hop. Returns vertex + connecting edge pairs. Filter by edge type
and direction.

**`walk(vertex_id, min_depth=1, max_depth=3, edge_types=None, direction=OUTBOUND) → Subgraph`**

Depth-limited traversal. Returns discovered vertices, edges, and paths.
Configurable depth, direction, edge type filter. Maps to AQL's
`FOR v, e, p IN min..max OUTBOUND`.

**`find(vertex_id, predicate, max_depth=10, edge_types=None, direction=OUTBOUND) → list[Path]`**

Walk until you hit something matching a condition. Predicate is a
callable `(vertex: dict) → bool` evaluated Python-side on each
discovered vertex. Returns paths to matching vertices — the path is
the answer, not just the destination. This is finding, not searching.
AQL pushdown for predicates is a future optimization (declared loss).

**`path(from_id, to_id, edge_types=None, k=3) → list[Path]`**

K shortest paths between two vertices. Each path tells a different
story about the relationship. Maps to AQL's `K_SHORTEST_PATHS`.

### Return types

| Type | Fields | Description |
|------|--------|-------------|
| `Neighbor` | vertex, edge, direction | One-hop result |
| `Path` | vertices, edges | Ordered sequence through the graph |
| `Subgraph` | vertices, edges, paths | Discovered territory from a walk |

All frozen, extra="allow". Vertices returned as dicts — Llika doesn't
know what kind of vertex it found (tensor, fact, entity). The consumer
interprets. Llika just walks the graph.

### What's deliberately absent

- No update, no delete (immutable edges)
- No aggregation (consumer's job)
- No text search (Apacheta's rummage and ArangoSearch handle that)
- No batch traversal (add when a consumer needs it)

## Migration

`migration.py` handles one-time conversion of existing data:

1. Read all CompositionEdge documents from Apacheta's flat collection
2. Create native ArangoDB edges in `llika_composition` with `_from`/`_to`
   pointing at tensor vertex documents
3. Read all NegationRecord documents, create corresponding edges
4. Log what was migrated, what was skipped (e.g., edges referencing T8)
5. Idempotent — safe to run twice, content-addressed by source UUID

Flat documents in Apacheta remain untouched. Immutable history.
Llika's edge collections become the canonical path for graph queries.

## Integration

### Willay (attestation edges)

Willay doesn't know about Llika. The caller bridges them:

1. Willay evaluates a claim, returns a `ReceiptRecord`
2. Caller creates attestation edge via `llika.link(tensor_id,
   evidence_id, EdgeType.ATTESTATION, scores=..., receipt_id=...)`
3. The attestation is now traversable in the graph

### Jabberwock (entity membership)

Jabberwock entities become vertices. Rath membership relationships
become `llika_membership` edges. Jabberwock's `Brillig` service
continues to work against the activity stream; Llika provides the
graph traversal layer on top.

### Cairn provenance extraction (batch job)

The cairn's ~10,000 files have provenance metadata in HTML comments.
Extracting provenance edges is a separate batch job:

1. Parse cairn file headers for model identity
2. Resolve model names to Jabberwock entities (or create them)
3. Create provenance edges: model entity → cairn document

This can run as a background job, gradually building the provenance
graph from historical data.

## First Customer: Taste (hamut'ay)

The taste experiment needs four operations exposed as tools (the
tool design is hamut'ay's decision, not Llika's):

- **Store** — persist a self-structured tensor via Apacheta
- **Link** — connect tensors via Llika (composition, attestation)
- **Find** — traverse the graph from the current tensor
- **Attest** — verify a claim via Willay, store as attestation edge

These operations give the taste model persistent memory that outlives
any single session, with relationship discovery through graph
traversal rather than keyword search.

## Declared Losses

- No multi-backend support. ArangoDB-only.
- No ArangoSearch views yet (temporal + semantic filtered RAG is a
  future layer).
- No weighted traversal beyond what K_SHORTEST_PATHS provides.
- Python-side predicate evaluation in `find()` — AQL pushdown for
  predicates is future optimization.
- No access control on graph traversal (all edges visible to all
  consumers). Pukara handles trust boundaries at the HTTP layer.
