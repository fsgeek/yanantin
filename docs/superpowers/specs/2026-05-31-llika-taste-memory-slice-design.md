# Llika Taste-Memory Slice — Design

*Brainstormed 2026-05-31 between Tony Mason (PI) and Claude Opus 4.8,
with an adversarial review pass (Claude Desktop). Co-designed, internally
consistent, framing challenged once by a same-family reviewer — **not**
independently validated (the reviewer helped shape the direction; see
"What this slice does not prove"). Scaled to a thin vertical slice, not the
whole Llika layer.*

## Goal

Give the taste entity (hamut'ay's `taste_open`) persistent, **traversable**
memory that outlives a single session — so a non-standard AI entity can
remember who it was and shape who it becomes. Yanantin provides the
infrastructure; hamut'ay owns the LLM-facing tools that call it.

This slice builds and proves **store → link → find** end-to-end. *store*
already works (apacheta's append-only document store). The new yanantin-side
work is a connection singleton plus a minimal Llika graph service exposing
`link` and `find`.

**What this slice proves — stated precisely (the value claim, turned inward).**
It proves **graph-traversal correctness over real storage**: that `link` writes
a native edge and `find` walks it back, returning the *path*. It does **not**
prove the epistemic capability the customer named ("discover what you didn't
know to ask about"). It can't, for two reasons the design must own rather than
let a slogan paper over:

1. `find` takes a `predicate: Callable[[dict], bool]` — a predicate *is*
   the thing you already knew to ask about. A predicate-bounded walk is a
   search with a programmable halt, not predicate-free discovery. The discovery
   this slice can honestly claim is **in the path, not the predicate**: you
   supply a known stopping condition, and what you didn't know to ask about is
   the *connective tissue the traversal surfaces between source and match*.
   That is a real and narrower notion of discovery, and it is the one claimed.
2. The thing the customer actually touches is the **hamut'ay tool**, which is
   out of scope. So the customer-named operation is validated one layer below
   where the customer sees it. The slice de-risks the *engine*; it does not
   de-risk the *capability*.

## Why a slice, not the layer

The full Llika spec (`docs/llika-spec.md`, approved 2026-03-31, never
implemented) defines four edge types and four traversal methods. Every prior
instance wandered off to the tool-name cue-conflict research line instead of
building any of it (see memory `project-request-capability-type2`). The slice
de-risks the *whole stack* by proving the operation the customer actually
named — `find` ("discover what you didn't know to ask about") — over real
storage, rather than building a complete layer no one has exercised.

`find()` transitively needs depth-limited walk machinery, so building it
yields `walk()`'s core for nearly free; `walk()` becomes "find without the
predicate" in a later slice.

## Ownership boundary

| Layer | Owner | This slice builds |
|---|---|---|
| LLM-facing tools (names, descriptions, schemas) | hamut'ay | nothing — hamut'ay's call |
| Graph service Python API (`link`, `find`) | yanantin | **yes** |
| Connection management (singleton) | yanantin | **yes** |
| Document store (`store`) | yanantin (apacheta) | already exists |

The brainstorm's legibility principles
(`docs/brainstorm-llm-tool-surface.md`) are guidance for hamut'ay's tool
design, not yanantin code. Yanantin exposes a clean Python API; hamut'ay
wraps it in tools shaped for the operating model.

## Component 1 — Connection singleton

### The problem it fixes

The llika-spec's premise is "singleton database, one ArangoDB connection per
process, shared between Apacheta and Llika." **This was never implemented.**
Three sites each construct their own `ArangoClient`:

- `src/yanantin/apacheta/backends/arango.py` (`self._client = ArangoClient(...)`)
- `src/yanantin/activity/backends/arango.py`
- `src/yanantin/infra/config.py:connect()` — and it rebuilds the client on
  *every call*.

The singleton-ness wasn't hidden; it didn't exist. Llika is the forcing
function: with one consumer you can fake a singleton with a private
attribute; with two, the fakery shows as edges potentially pointing at
vertices fetched through a different connection. We build the singleton now
and retrofit **all four** consumers, rather than adding a fourth violator or
leaving invisible debt that "won't be more visible until it breaks."

### Interface

```python
def get_database(
    host: str | None = None,
    db_name: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> StandardDatabase:
    ...
```

Lives in `src/yanantin/infra/config.py` — where the credential logic and the
`YANANTIN_ARANGO_*` env-var convention (already emitted by
`config.write_env()`) already live.

### Resolution, then memoization

**Order is load-bearing.** Resolve every field *before* keying the cache,
otherwise `get_database()` and `get_database(db_name="apacheta")` — which mean
the same target — split into two connections, defeating the singleton. The
cache sits *behind* resolution, not in front of it.

Per-field fallback precedence:

1. **Explicit argument** (tests, special cases)
2. **Environment variable** (`YANANTIN_ARANGO_HOST`/`_DB`/`_USER`/`_PASSWORD`)
   — headless/CI-friendly, no credentials on disk
3. **Config file** (Indaleko's overridable-default model)

After resolution, memoize on `(host, db_name, username)`. Password is fetched
but **not** part of the cache key (don't key on secrets; username→password is
1:1 anyway).

### Username is the tier boundary

Each database user is granted access to exactly one database. So keying on
`username` *is* the admin/app/test separation — enforced by the access grant,
not by a redundant `tier` label kept in sync by hand. This mirrors Indaleko,
which held a system handle and a user handle in one object precisely because
admin (provisioning) and app (use) need different credentials. Here that split
falls out for free: different usernames → different cache keys → different
handles. Separation of concern, structural.

`config.connect(tier)` becomes a thin wrapper that maps a tier to credentials
and calls `get_database`.

### Retrofit, preserving the error discrimination

`apacheta/backends/arango.py` was just fixed (2026-05-31) to discriminate
connection-failure modes (`BackendAuthError` / `BackendUnreachableError` /
`DatabaseNotProvisionedError`). The retrofit changes *where the client comes
from* (now `get_database`), **not** *how connection failures are diagnosed*.
The discrimination logic and its independent Codex tests
(`tests/unit/test_arango_conn_errors.py`) must stay green through the
retrofit — they are the guard that proves the behavior survived.

## Component 2 — Llika graph service

New package `src/yanantin/llika/`. This slice builds two files.

### `models.py`

```python
class CompositionEdge(ApachetaBaseModel):  # frozen=True, extra="allow"
    # _from, _to as ArangoDB vertex refs ("tensors/<uuid>")
    # id: UUID, created_at: datetime, provenance: ProvenanceEnvelope
    # relation_type: RelationType  (enum already exists, 10 members)
```

Plus a `Path` return type (ordered `vertices` + `edges`), also frozen /
`extra="allow"`. One edge type this slice; the other three (Attestation,
Provenance, Membership) are a logged follow-up.

`ApachetaBaseModel` lives in `tiksi` (`tiksi/src/tiksi/base.py`); config is
`{frozen: True, extra: "allow", ...}` — Llika edges inherit it, same
append-only philosophy as the rest of apacheta.

### `service.py`

```python
class LlikaService:
    def __init__(self, db: StandardDatabase): ...   # handle from get_database()

    def link(self, from_id, to_id, relation_type, **kwargs) -> CompositionEdge:
        """Create one immutable native ArangoDB edge. Provenance auto-attached
        from the service's context. kwargs become open-schema fields."""

    def find(
        self,
        vertex_id,
        predicate: Callable[[dict], bool],
        max_depth: int = 4,
        max_results: int = 50,
        direction = OUTBOUND,
    ) -> list[Path]:
        """Walk the graph from vertex_id, evaluating `predicate` Python-side on
        each discovered vertex. Return the PATHS to matching vertices (capped at
        max_results) — the path is the answer, not just the destination.
        Finding-as-path-connectivity (see value claim above), not searching."""
```

`find`'s predicate is a Python callable (a stopping condition on the
traversal, not an attribute filter). This is correct for direct-import callers
— taste/hamut'ay import yanantin's Python API. Serializing a graph query
across an HTTP boundary (when Llika eventually gets a Pukara face) is a
genuinely separate design problem — **not** prejudged here. A callable shipped
as source text and `eval`'d remotely is arbitrary RCE; the wire protocol needs
its own design. Logged, not solved.

**The callable-predicate fork, named on purpose (not a silent deferral).**
An arbitrary `Callable[[dict], bool]` is opaque Python — it cannot be compiled
to AQL. So the moment callers pass real callables (and they will, because that
is the interface handed to them), the deferred "AQL predicate pushdown"
optimization can *never* apply to those calls; pushdown could only ever arrive
as a *second*, declarative predicate form, fragmenting the interface. This is a
fork, not a sequence: the convenient Phase-1 type forecloses the Phase-2 fix.
**Decision: accept the callable for this slice, with eyes open.** The slice's
job is to prove traversal correctness for direct-import callers; the declarative
predicate language is part of the *same* future design problem as the HTTP wire
protocol (both need a serializable predicate), and they should be solved
together, once, rather than bolted on. Recorded as a deliberate Phase-1 cost,
not an oversight.

### Edge supersession — deferred, with the intended shape recorded

`find` as specified walks **all** edges, including ones a later correction
supersedes; nothing in this slice distinguishes a live relationship from a
retracted one during traversal. For a *memory* — "remember who it was and shape
who it becomes" — traversing contradicted edges as if live is a semantic-layer
correctness gap even though the storage layer (append-only, immutable) is
correct. Memory without principled retraction is accumulation, not biography.

**This is deferred, not solved in this slice — but the intended shape is a
written decision, deferred on *architectural* grounds (the addition is free),
not on "ran out of time" grounds:**

- **Retraction is a backward reference by id.** A retraction edge *names the
  edge it supersedes* as its target. Arango edges are addressable documents
  with stable ids, so an edge can reference another edge. Correction =
  "this retracts edge X," a retraction the traversal can honor — **not** a
  parallel vertex-to-vertex assertion the reader must reconcile. (Note the
  current `CompositionEdge._from/_to` are *vertex* refs; the retraction edge
  type is a distinct, later addition, not a reinterpretation of this one.)
- **`find` honoring it is a later filter, not a redesign.** A subsequent slice
  adds "skip edges named as the target of a live retraction" to the walk.
  Additive.
- **Why deferral is safe (the architectural ground).** Append-only +
  `extra="allow"` means the retraction edge type is purely additive: existing
  edges don't move, no migration, no change to this slice's model, no caller
  breakage. The later addition costs nothing this slice forecloses. This is the
  *opposite* of the callable-predicate fork above — there, Phase 1 forecloses
  the Phase-2 fix; here, Phase 1 leaves it free. The distinction is exactly why
  one is "named cost" and the other is "safe deferral."

(Distinct from Willay's `next_id`, which is a *forward* commitment in
attestation receipts — opposite direction, different project. The two collided
in conversation; they are not the same mechanism. See Willay's receipt-
authenticity spec.)

### Boundaries held

- **Append-only.** Edges immutable — no update, no delete. Corrections create
  new edges (same as apacheta records).
- **One-directional dependency.** Llika knows apacheta; apacheta doesn't know
  Llika. Integration happens at the caller level.
- **ArangoDB-only.** Graph traversal is why ArangoDB was chosen; no
  multi-backend abstraction for Llika.

## Testing

**Live `apacheta_test` database — no mocked DB operations.** (Memory
`feedback-no-mock-databases`.) A mocked `ArangoClient` proves the
memoization dict deduplicates calls; it proves nothing about whether two
handles share a real connection or whether a `link()` is visible to a
`find()`. For a singleton *connection*, "same connection" is exactly what a
mock cannot witness. The test substrate must be the property's actual
substrate.

(Mocking remains acceptable for *control-flow* tests with no storage property
— e.g. the existing error-discrimination tests, which assert which exception
type maps to which failure. The line: asserting something about storage → live
DB; asserting your own branch logic → mock is fine.)

### Properties the tests must establish (contract for the independent author)

Phrased as invariants, not assertions — handed to Codex (the independent test
author) as "what must be true," leaving "how to assert it and what else could
break" to Codex's judgment per builder/tester separation.

**Singleton identity:**

1. Two calls resolving to the same `(host, db_name, username)` return the
   same handle — proven by a write through one and a read through the other
   sharing a view of real storage (not mere Python `is` on a mock).
2. Different usernames → different handles (tier boundary: app ≠ admin).
3. Different db_names → different handles (app ≠ test isolation).
4. Per-field precedence: explicit arg > env var > config file. An explicit
   `db_name` with other fields from env resolves correctly.
5. Resolution precedes memoization — calls that differ in spelling but resolve
   identically do not split into two connections.

**Llika round-trip:**

6. An edge written by `link()` is traversable by `find()` — round-trip
   through real storage.
7. `find()` returns the *path*, not just the terminal vertex, and stops at
   predicate match.
8. Edges are immutable — no update/delete affordance exists.

`get_database` is process-global memoized state; live tests need cache
isolation so one test's resolved handle doesn't leak into the next and mask a
bug. **The isolation strategy is Codex's to choose** — handed as a named
property of the system, then checked adversarially by the builder for actual
leakage prevention. (Not prescribed here, per
`feedback-codex-and-prescription`.)

### Builder/tester separation

CI (`.github/workflows/separation.yml`) bans any commit touching both `src/`
and `tests/`. Implementation and tests land in separate commits; tests are
authored by Codex (gpt-5.3-codex) from this spec's invariant contract, not by
the builder. Builder verifies Codex's tests RED against pre-implementation
code before trusting them.

## Declared losses (named, not eliminated)

- **`find` scaling is unproven, and the live-DB test substrate cannot prove
  it.** A bounded-breadth walk over an append-only graph that *only ever grows*
  gets monotonically slower for the life of the system; Python-side predicate
  evaluation pulls the frontier out of Arango to filter in-app, forfeiting the
  in-database traversal that is the stated reason for choosing ArangoDB.
  `max_depth=4` + `max_results=50` are a Phase-1 *guard*, not a solution —
  they cap the blast radius, they don't make the operation in-database. **A
  small live `apacheta_test` DB verifies correctness and is blind to this
  scaling property exactly as a mock would be** — "no mocked DB" answers
  "same connection / round-trip works," not "tractable at scale." A scale
  substrate (a populated graph, a perf assertion) is a separate, named future
  test. The no-mock discipline is correct for what it targets and silent on
  what it doesn't.
- **Connections are not append-only; the singleton has no liveness story.**
  `get_database` memoizes long-lived *mutable* resources with no eviction or
  invalidation — the classic "works until a credential rotation or network
  event, then wedged forever" bug. Password is kept out of the cache key on a
  "username→password is 1:1" assumption that holds *until the first rotation*,
  after which the cache serves a handle bound to stale credentials with no path
  to notice. The error-discrimination retrofit can *detect* a dead handle; it
  gives the singleton no way to *replace* one. **Phase-1 scope: detect-and-fail
  (a dead handle surfaces as a discriminated connection error), not
  reconnect.** Invalidation/reconnect-on-failure is a named deferral — recorded
  here because "connections aren't append-only" deserves the same declared-
  incompleteness treatment the edge types get.
- **Edge supersession** — see the dedicated section above. `find` walks
  retracted edges as live in Phase 1.

## Named follow-ups (logged, not built)

- The other three edge types (Attestation, Provenance, Membership) and the
  other traversal methods (`neighbors`, `walk`, `path`).
- Migration of existing flat `CompositionEdge` documents to native edges
  (`migration.py`).
- HTTP/Pukara wire-protocol for graph-query predicates (the serialization
  problem `find`'s callable defers).
- Retrofitting any *other* `ArangoClient` construction sites discovered beyond
  the three named here.

## What's not in scope

- hamut'ay-side tool definitions (their decision, their repo).
- Willay attestation integration (`attest` operation) — needs the
  AttestationEdge type, a later slice.
- ArangoSearch views, weighted traversal, AQL predicate pushdown.
- Access control on traversal (Pukara handles trust at the HTTP layer).
