# Llika Traversal Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `LlikaService.find`'s callable predicate with a serializable, tenant-bound structural traversal (`walk`/`neighbors`), so Llika becomes the RPC-shaped memory interface hamut'ay calls.

**Architecture:** `LlikaService` is reconstructed to bind a **tenant** (a `tier` string) at construction and resolve its own db handle internally via `ApachetaDBConfig().connect(tier)` — no `db`/`db_name` crosses the constructor. `find(predicate)` is deleted; `walk`/`neighbors` traverse by direction+depth+relation_type via AQL and return serializable `PathResult`/`PathStep`/`EdgeResult` dataclasses (no callables, no raw arango docs). The `CompositionEdge` model is unchanged; `Path` is replaced.

**Tech Stack:** Python 3.14, uv, python-arango, pydantic (via tiksi `ApachetaBaseModel`), pytest. Live `apacheta_test` DB at `192.168.111.127:8529` (read live config — both .125/.127 reach the same host).

**Spec:** `docs/superpowers/specs/2026-06-01-llika-traversal-interface-design.md`
**Architecture (standing decisions):** `docs/llika-spec.md` Design Principles

---

## Governance constraints (apply to EVERY task)

- **Builder/tester separation** (`.github/workflows/separation.yml`): no commit
  touches both `src/` and `tests/`. Implementation and tests land in **separate
  commits**. Tests are authored by **Codex** (gpt-5-codex) from the invariant
  contract, NOT by the builder. Dispatch:
  `codex exec --sandbox workspace-write "<prompt>" < /dev/null 2>&1 | tail -70`
  (no `-m` flag; `< /dev/null` for the stdin bug — memory
  `feedback-codex-and-prescription`). Codex cannot reach the live DB from its
  sandbox; it authors, the **builder runs** the tests RED→GREEN.
- **Codex prompts are non-prescriptive:** hand the invariant + the importable
  surface, NOT an assertion list. Verify Codex's tests RED against
  pre-implementation code before trusting them.
- **AI commits** use per-command git identity overrides (Yanantin key
  `1E416B1FB63AF88179EE0F38D0CAB9659C950893`,
  `Yanantin AI (Claude Opus) <yanantin@wamason.com>`, `commit.gpgsign=true`),
  never repo-level config. Verify `%G?` == `G` after committing.
- **Live DB, not mocked** for storage/traversal behavior (memory
  `feedback-no-mock-databases`). A mock cannot witness that a written edge is
  traversable.
- **OTS sweep** (memory): the post-commit hook drops `docs/ots/<hash>.ots`,
  untracked. Sweep them in the final task — don't leave the floor for the PI.

---

## File Structure

- **Modify** `src/yanantin/llika/models.py` — delete `Path`; add serializable
  result dataclasses `EdgeResult`, `PathStep`, `PathResult`. Keep
  `CompositionEdge` unchanged.
- **Modify** `src/yanantin/llika/service.py` — reconstruct `LlikaService`:
  tenant-bound constructor, `link` returns `EdgeResult`, delete `find`, add
  `walk`/`neighbors`.
- **Modify** `src/yanantin/llika/__init__.py` — export the new result types,
  drop `Path`.
- **Delete** `tests/integration/test_llika_service.py` — the slice-1 `find`
  tests (superseded; Codex rewrites against `walk`/`neighbors`).
- **Create (Codex)** `tests/integration/test_llika_service.py` — new live-DB
  tests for the tenant-bound surface.

---

# Task 1: Result models — `EdgeResult`, `PathStep`, `PathResult`

**Files:**
- Modify: `src/yanantin/llika/models.py`

**Context:** The result types are the **wire contract** — they must be
serializable (JSON-representable) and carry no raw arango `_id`/`_rev`. They are
NOT pydantic edge models (those are the stored form); they are plain frozen
dataclasses that the service returns. `field_names` is shape-not-values.

- [ ] **Step 1: Replace `Path` with the result dataclasses (builder)**

In `src/yanantin/llika/models.py`, **delete** the `Path` class (lines 30-36)
and its now-unused imports are kept only if still used. Replace with:

```python
"""Llika edge and traversal models.

CompositionEdge is the stored (pydantic) edge form — frozen, extra='allow',
append-only. EdgeResult/PathStep/PathResult are the SERIALIZABLE result types
the service returns across the (eventually-RPC) boundary: plain frozen
dataclasses, JSON-representable, carrying record-id strings and edge metadata —
never raw ArangoDB documents (_id/_rev). field_names is SHAPE, not values."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import Field

from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.composition import RelationType


class CompositionEdge(ApachetaBaseModel):
    """A native ArangoDB edge between two vertices. Immutable once created.

    Distinct from the flat tiksi.CompositionEdge (from_tensor/to_tensor plain
    fields): this is the *graph* form, carrying ArangoDB's required `_from`/`_to`
    edge refs (e.g. "tensors/<uuid>") via aliases, since pydantic forbids
    leading-underscore field names."""
    id: UUID = Field(default_factory=uuid4)
    from_ref: str = Field(alias="_from")   # e.g. "tensors/<uuid>"
    to_ref: str = Field(alias="_to")
    created_at: datetime
    relation_type: RelationType
    provenance: ProvenanceEnvelope


@dataclass(frozen=True)
class EdgeResult:
    """Serializable result of link(). No raw arango doc, no pydantic model."""
    edge_id: str          # the edge's UUID, as a string
    from_id: str          # record-id ref
    to_id: str            # record-id ref
    relation_type: str    # RelationType name
    created_at: str        # ISO-8601


@dataclass(frozen=True)
class PathStep:
    """One hop in a traversal. field_names is SHAPE (which fields), not values."""
    record_id: str         # the vertex reached at this step
    relation_type: str     # the edge type that reached it
    field_names: tuple[str, ...]


@dataclass(frozen=True)
class PathResult:
    """An ordered walk from a start vertex. steps[-1] is the far end."""
    start_id: str
    steps: tuple[PathStep, ...]
```

- [ ] **Step 2: Verify models import and shapes are right**

Run: `uv run python -c "from yanantin.llika.models import CompositionEdge, EdgeResult, PathStep, PathResult; import dataclasses as d; print('EdgeResult fields:', [f.name for f in d.fields(EdgeResult)]); print('PathStep fields:', [f.name for f in d.fields(PathStep)]); print('PathResult fields:', [f.name for f in d.fields(PathResult)])"`

Expected (note: this triggers `__init__.py` which still imports `Path` — see Step 3; if it errors on `Path`, do Step 3 first then re-run):
```
EdgeResult fields: ['edge_id', 'from_id', 'to_id', 'relation_type', 'created_at']
PathStep fields: ['record_id', 'relation_type', 'field_names']
PathResult fields: ['start_id', 'steps']
```

- [ ] **Step 3: Update `__init__.py` exports (builder)**

The package `__init__.py` imports `Path` (now deleted) and `LlikaService`
(reconstructed in Task 2). Replace its contents:

```python
"""Llika — graph-structured index service over ArangoDB native edges."""
from yanantin.llika.models import CompositionEdge, EdgeResult, PathResult, PathStep
from yanantin.llika.service import LlikaService

__all__ = ["CompositionEdge", "EdgeResult", "PathResult", "PathStep", "LlikaService"]
```

(Note: `__init__` imports `LlikaService` from service.py, which Task 2 rewrites.
Until Task 2, the package won't import clean. Verify models in isolation by
importing `yanantin.llika.models` directly is NOT possible — `__init__` runs on
any submodule access. So after Step 1+3, the package import will fail on
service.py's old `Path` references until Task 2. That is expected; commit models
now, prove the full import at end of Task 2.)

- [ ] **Step 4: Commit (builder) — models.py + __init__.py**

```bash
git add src/yanantin/llika/models.py src/yanantin/llika/__init__.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "feat(llika): serializable result types (EdgeResult/PathStep/PathResult), drop Path"
git log -1 --format='%an sig:%G?'   # expect: Yanantin AI (Claude Opus) sig:G
```

---

# Task 2: Reconstruct `LlikaService` — tenant-bound, link/walk/neighbors

**Files:**
- Modify: `src/yanantin/llika/service.py` (full rewrite)

**Context — the tenant resolution (keystone):** A "tenant" is a `tier` string
(`"app"`/`"test"`/`"admin"`), the established pattern in
`ApachetaDBConfig.connect(tier)` which resolves tier → credentials → db_name →
`get_database`. The constructor takes `tier`, calls `connect(tier)` to get the
shared handle, and owns it internally. **No `db`/`db_name` crosses the
constructor** — the caller names a tier, not a database; the tier→db_name
mapping lives in config. This is the "caller cannot name an arbitrary tenant's
space" property, using existing machinery.

**AQL traversal:** `direction` maps to `OUTBOUND`/`INBOUND`/`ANY`. The relation
filter, when given, filters edges by `relation_type`. The walk returns one
`PathResult` per discovered path (each AQL `p` is a path); `PathStep`s are built
from `p.vertices[1:]` (skip the start vertex) paired with `p.edges`.

- [ ] **Step 1: Rewrite `service.py` (builder)**

Replace the entire file `src/yanantin/llika/service.py`:

```python
"""LlikaService — tenant-bound graph service over the shared ArangoDB handle.

Constructed against a TIER (the tenant); resolves its own db handle internally
via ApachetaDBConfig().connect(tier). No db/db_name crosses the constructor.
Returns serializable result types — never raw arango docs or pydantic models.
Append-only: link only; no update/delete. find() is intentionally absent (a
callable predicate cannot cross a wire; the customer filters by structure)."""
from __future__ import annotations

from datetime import datetime, timezone

from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.composition import RelationType
from yanantin.infra.config import ApachetaDBConfig
from yanantin.llika.models import CompositionEdge, EdgeResult, PathResult, PathStep

_EDGE_COLLECTION = "llika_composition"

_DIRECTION_AQL = {"forward": "OUTBOUND", "backward": "INBOUND", "both": "ANY"}

# fields the service must NOT surface as content shape (framework envelope)
_ENVELOPE_FIELDS = frozenset({"_id", "_key", "_rev", "_from", "_to",
                              "provenance", "lineage_tags"})


def _field_names(vertex: dict) -> tuple[str, ...]:
    """The vertex's content field NAMES (shape), envelope fields stripped."""
    return tuple(sorted(k for k in vertex if k not in _ENVELOPE_FIELDS))


class LlikaService:
    """Create and traverse native ArangoDB edges. Tenant-bound; append-only."""

    def __init__(self, tier: str, provenance: ProvenanceEnvelope):
        """Bind to a tenant (tier) and resolve the shared db handle internally.

        tier: "app" | "test" | "admin" — the tenant. The caller does NOT name a
        database; the tier->db_name mapping lives in config.
        """
        self._db = ApachetaDBConfig().connect(tier)
        self._provenance = provenance
        if not self._db.has_collection(_EDGE_COLLECTION):
            self._db.create_collection(_EDGE_COLLECTION, edge=True)
        self._edges = self._db.collection(_EDGE_COLLECTION)

    def link(
        self,
        from_id: str,
        to_id: str,
        relation_type: RelationType,
        **fields,
    ) -> EdgeResult:
        """Create one immutable edge from_id -> to_id. Returns a serializable
        EdgeResult — not the raw doc, not the CompositionEdge model."""
        edge = CompositionEdge(
            **{"_from": from_id, "_to": to_id},
            created_at=datetime.now(timezone.utc),
            relation_type=relation_type,
            provenance=self._provenance,
            **fields,
        )
        doc = edge.model_dump(by_alias=True, mode="json")
        self._edges.insert(doc)
        return EdgeResult(
            edge_id=str(edge.id),
            from_id=from_id,
            to_id=to_id,
            relation_type=edge.relation_type.name,
            created_at=doc["created_at"],
        )

    def walk(
        self,
        start_id: str,
        direction: str,
        depth: int,
        relation_types: list[str] | None = None,
        max_results: int = 50,
    ) -> list[PathResult]:
        """Traverse from start_id by structure: direction + depth + optional
        relation_type filter. Returns serializable PathResults carrying every
        intermediate vertex. Capped at max_results in traversal order.

        direction: "forward" (OUTBOUND) | "backward" (INBOUND) | "both" (ANY).
        relation_types: RelationType NAMES to follow; None follows all."""
        aql_dir = _DIRECTION_AQL[direction]
        rel_filter = ""
        bind_vars: dict = {"start": start_id, "max_depth": depth,
                           "max_results": max_results}
        if relation_types:
            rel_filter = "FILTER e.relation_type IN @relation_types"
            bind_vars["relation_types"] = relation_types
        aql = f"""
        FOR v, e, p IN 1..@max_depth {aql_dir} @start {_EDGE_COLLECTION}
            {rel_filter}
            LIMIT @max_results
            RETURN p
        """
        cursor = self._db.aql.execute(aql, bind_vars=bind_vars)
        results: list[PathResult] = []
        for p in cursor:
            steps = tuple(
                PathStep(
                    record_id=vertex["_id"],
                    relation_type=edge["relation_type"],
                    field_names=_field_names(vertex),
                )
                for vertex, edge in zip(p["vertices"][1:], p["edges"])
            )
            results.append(PathResult(start_id=start_id, steps=steps))
        return results

    def neighbors(
        self,
        start_id: str,
        direction: str,
        relation_types: list[str] | None = None,
    ) -> list[PathResult]:
        """Depth-1 convenience: who is adjacent. walk(..., depth=1)."""
        return self.walk(start_id, direction, depth=1,
                         relation_types=relation_types)
```

- [ ] **Step 2: Verify the package imports clean**

Run: `uv run python -c "from yanantin.llika import LlikaService, EdgeResult, PathResult, PathStep, CompositionEdge; print('methods:', [m for m in dir(LlikaService) if not m.startswith('_')])"`
Expected: `methods: ['link', 'neighbors', 'walk']` — note **no `find`**.

- [ ] **Step 3: Smoke-test construction + a round-trip against live DB (builder, not committed)**

Run this throwaway to confirm tenant-binding and a real link+walk work end to end before handing the contract to Codex:

```bash
uv run python -c "
from uuid import uuid4
from tiksi.provenance import SourceIdentifier
from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.composition import RelationType
from yanantin.infra.config import ApachetaDBConfig
from yanantin.llika import LlikaService

prov = ProvenanceEnvelope(source=SourceIdentifier(identifier=uuid4(), description='plan smoke'), author_model_family='test')
svc = LlikaService('test', prov)   # tenant = tier; NO db handle passed
db = ApachetaDBConfig().connect('test')
run = uuid4().hex[:8]; coll = f'llika_plan_{run}'
db.create_collection(coll); c = db.collection(coll)
def v(lbl, **x): c.insert({'_key': f'{lbl}_{run}', 'lbl': lbl, **x}); return f'{coll}/{lbl}_{run}'
A=v('A'); B=v('B'); C=v('C', target=True)
svc.link(A,B,RelationType.COMPOSES_WITH, run=run); svc.link(B,C,RelationType.BRIDGES, run=run)
paths = svc.walk(A, 'forward', depth=3)
print('paths:', len(paths))
longest = max(paths, key=lambda p: len(p.steps))
print('longest steps:', [(s.record_id.split('/')[-1], s.relation_type) for s in longest.steps])
db.aql.execute('FOR e IN llika_composition FILTER e.run==@r REMOVE e IN llika_composition', bind_vars={'r': run})
db.delete_collection(coll)
print('cleaned')
"
```
Expected: `paths:` ≥ 1, the longest path's steps reach `C` and carry `B`, then `cleaned`. If the walk returns nothing, debug AQL before proceeding.

- [ ] **Step 4: Run the existing suite for regressions in the llika import surface**

Run: `uv run pytest tests/ -k "llika or infra or config" -q 2>&1 | tail -15`
Expected: PASS, EXCEPT `tests/integration/test_llika_service.py` (slice-1 find
tests) will FAIL/ERROR — those are deleted in Task 3. Note which other tests, if
any, import `Path` from llika (grep below); if any do, they need updating —
flag for the relevant owner (test files → Codex; src → builder).

Run: `grep -rn "from yanantin.llika import\|llika.models import\|llika import Path\| Path\b" src/ tests/ | grep -i llika | grep -v __pycache__`
Expected: only the (about-to-be-deleted) test file and the llika package itself.

- [ ] **Step 5: Commit (builder)**

```bash
git add src/yanantin/llika/service.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "feat(llika): tenant-bound LlikaService; walk/neighbors replace find"
git log -1 --format='%an sig:%G?'   # expect: Yanantin AI (Claude Opus) sig:G
```

---

# Task 3: Delete the superseded slice-1 tests (tester commit)

**Files:**
- Delete: `tests/integration/test_llika_service.py`

**Context:** The slice-1 tests exercise `find(predicate=...)`, now deleted. They
are removed outright (not deprecated) — re-introducing `find` should require
arguing for it (the deletion is load-bearing friction, per the spec). This is a
**tests-only** commit (separation).

- [ ] **Step 1: Delete the file**

```bash
git rm tests/integration/test_llika_service.py
```

- [ ] **Step 2: Confirm nothing else references it / its symbols**

Run: `grep -rn "test_llika_service\|from yanantin.llika import Path\|\.find(" tests/ | grep -v __pycache__ | grep -i llika`
Expected: empty (no other test imports the deleted file or the removed `find`).

- [ ] **Step 3: Commit (tester)**

```bash
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "test(llika): remove superseded find() tests (callable predicate retired)"
git log -1 --format='%an sig:%G?'   # expect: Yanantin AI (Claude Opus) sig:G
```

---

# Task 4: Codex authors the new traversal tests (live DB)

**Files:**
- Create (Codex): `tests/integration/test_llika_service.py`

- [ ] **Step 1: Write the Codex prompt to `/tmp/codex_llika_walk_prompt.md`**

```
You are the independent test author for LlikaService in the yanantin project
(Python 3.14, uv, repo /home/tony/projects/yanantin). Design tests from the
CONTRACT below — do NOT transcribe an existing test, do NOT read other test
files for this service. Write to NEW file
tests/integration/test_llika_service.py, run with `uv run pytest`. Use the LIVE
apacheta_test database (do NOT mock — a mock cannot witness that a written edge
is traversable). You CANNOT reach the DB from your sandbox; author the tests,
the builder runs them. Verify your file py_compiles and pytest --collect-only
succeeds; report that you could not run them live.

Importable surface (yanantin.llika):
- LlikaService(tier: str, provenance: ProvenanceEnvelope)
    Constructed bound to a TENANT = tier ("test"). Resolves its own db handle
    internally; takes NO db/db_name. Creates 'llika_composition' edge collection
    if absent.
    .link(from_id: str, to_id: str, relation_type: RelationType, **fields) -> EdgeResult
    .walk(start_id: str, direction: str, depth: int, relation_types: list[str]|None=None, max_results: int=50) -> list[PathResult]
    .neighbors(start_id: str, direction: str, relation_types: list[str]|None=None) -> list[PathResult]
  direction is "forward" | "backward" | "both". relation_types are RelationType
  NAMES (strings, e.g. "COMPOSES_WITH"). There is NO find() method.
- EdgeResult (frozen dataclass): edge_id, from_id, to_id, relation_type, created_at — all str.
- PathStep (frozen dataclass): record_id: str, relation_type: str, field_names: tuple[str,...]
- PathResult (frozen dataclass): start_id: str, steps: tuple[PathStep,...]  (steps[-1] is the far end)
- RelationType at yanantin.apacheta.models.composition (e.g. RelationType.COMPOSES_WITH).
- ProvenanceEnvelope at yanantin.apacheta.models. CONSTRUCTION (verified): its
  `source` is a SourceIdentifier whose `identifier` is a UUID. Build it:
    from tiksi.provenance import SourceIdentifier
    from uuid import uuid4
    ProvenanceEnvelope(source=SourceIdentifier(identifier=uuid4(), description="t"),
                       author_model_family="test")

To get a db handle for SETUP (creating throwaway vertices to link between):
  from yanantin.infra.config import ApachetaDBConfig
  db = ApachetaDBConfig().connect("test")
Create a uniquely-named temp vertex collection, insert vertices (their _id is
"collection/_key"), use those _id strings as from_id/to_id. Clean up edges (by a
unique tag you put in **fields on link, filterable in AQL) AND your temp
collection in teardown.

Properties that must hold (decide assertions, setup, edge cases yourself):
1. TENANT BINDING: LlikaService is constructed with a tier string and NO db
   handle. Constructing it works and link/walk operate. (You cannot test
   cross-tenant isolation — only one tenant exists; assert the constructor takes
   tier, not db.)
2. LINK ROUND-TRIP: an edge written by link() is traversable by walk() —
   write A->B, walk forward from A reaches B. Assert link returns an EdgeResult
   (not a dict, not a raw doc) with from_id/to_id matching.
3. SERIALIZABLE RESULTS / NO LEAK: walk results are PathResult/PathStep with the
   declared fields; field_names is a tuple of STRINGS (field NAMES), and does
   NOT contain arango envelope keys (_id, _key, _rev, _from, _to, provenance).
   PathStep.record_id IS an arango _id ref string (that's the address), but the
   step must not expose vertex VALUES — only field_names.
4. CONNECTIVE TISSUE (depth>=3): build A->B->C->D; walk forward from A depth>=3;
   assert a returned PathResult's steps carry B and C (record_ids of the
   unmentioned intermediates), ending at D. A single hop does NOT satisfy this.
5. DIRECTION: walk backward (INBOUND) from a downstream vertex reaches an
   upstream one; "both" reaches either side. forward != backward results.
6. RELATION FILTER: with edges of two relation types from one start, walk with
   relation_types=[ONE_NAME] returns only paths whose edges are that type.
7. TRUNCATION OBSERVABLE: more matches than max_results -> walk returns exactly
   max_results PathResults (capped, not error, not the whole population).
8. NEIGHBORS = depth 1: neighbors(start, "forward") returns only immediate
   (1-hop) paths; a 2-hops-away vertex is NOT reached.
9. NO find / NO mutation: assert LlikaService has no `find`, `update`, or
   `delete` attribute; EdgeResult/PathResult/PathStep are frozen (attribute set
   raises).

Report test count, one-line coverage each, and that you could not run live (the
builder will). If your reasoning finds a contract ambiguity, say so — do not
invent behavior.
```

- [ ] **Step 2: Dispatch Codex**

Run: `codex exec --sandbox workspace-write "$(cat /tmp/codex_llika_walk_prompt.md)" < /dev/null 2>&1 | tail -70`

- [ ] **Step 3: Read the file Codex wrote**

Run: `cat tests/integration/test_llika_service.py`
Confirm it covers properties 1-9, uses the live DB (no mocks), cleans up, and
constructs `LlikaService("test", prov)` with NO db handle.

- [ ] **Step 4: Verify RED against pre-implementation code (integrity check)**

The implementation already landed (Tasks 1-2). To prove the tests couple to the
NEW surface, temporarily hide the new methods and confirm failure:

```bash
mv src/yanantin/llika/service.py /tmp/service_new.py.bak
uv run pytest tests/integration/test_llika_service.py -q 2>&1 | tail -10
mv /tmp/service_new.py.bak src/yanantin/llika/service.py
```
Expected: FAIL (ImportError / collection error on LlikaService). If any test
passes against the hidden service, scrutinize it.

- [ ] **Step 5: Verify GREEN against the real implementation (live DB)**

Run: `uv run pytest tests/integration/test_llika_service.py -v 2>&1 | tail -25`
Expected: all pass.

- [ ] **Step 6: Adversarially check property 4 (connective tissue)**

Read the property-4 test. Confirm it builds depth >= 3 (A->B->C->D) and asserts
the returned path's steps carry B AND C (the unmentioned intermediates) — NOT a
single hop, NOT just the terminal. If single-hop, re-dispatch Codex citing the
specific gap; do NOT fix the test yourself (separation).

- [ ] **Step 7: Commit (tester)**

```bash
git add tests/integration/test_llika_service.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "test(llika): tenant-bound walk/neighbors traversal (Codex, live DB)"
git log -1 --format='%an sig:%G?'   # expect: Yanantin AI (Claude Opus) sig:G
```

---

# Task 5: Full-suite gate + separation self-check + OTS sweep

- [ ] **Step 1: Full suite**

Run: `uv run pytest tests/ -q 2>&1 | tail -8`
Expected: all pass (modulo any Codex revision still owed from Task 4 Step 6 —
resolve before proceeding).

- [ ] **Step 2: Separation self-check across the new commits**

```bash
for C in $(git log --oneline origin/main..HEAD | awk '{print $1}'); do
  F=$(git diff-tree --no-commit-id --name-only -r "$C")
  S=$(echo "$F" | grep -c '^src/'); T=$(echo "$F" | grep -c '^tests/')
  MSG=$(git log -1 --format='%s' "$C")
  if [ "$S" -gt 0 ] && [ "$T" -gt 0 ]; then echo "$C VIOLATES: $MSG"; else echo "$C ok: $MSG"; fi
done
```
Expected: every commit `ok`.

- [ ] **Step 3: Confirm the single-construction-site invariant still holds**

Run: `grep -rn "ArangoClient(" src/yanantin/ | grep -v __pycache__`
Expected: exactly one — `infra/config.py`. LlikaService constructs no client (it
uses `connect`).

- [ ] **Step 4: Sweep the OTS stamps (don't leave the floor for the PI)**

```bash
git add docs/ots/*.ots 2>/dev/null
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "ots: stamp the traversal-interface slice commits" 2>&1 | tail -3
```
(One trailing `.ots` from THIS commit will remain untracked — that tail is
structural, leave it. Memory: `OTS stamps are a janitorial debt`.)

- [ ] **Step 5: Report the slice as a narrative**

Run a short throwaway (not committed) that: constructs `LlikaService("test",
prov)`, links A->B->C through real vertices, `walk`s forward from A depth 3, and
prints the path — showing the steps carry B and reach C, with `field_names` but
no vertex values. The human-legible proof the RPC-shaped traversal holds end to
end. Report the PathResult.

---

## Self-Review (completed by plan author)

**Spec coverage:**
- Tenant-bound constructor (tier), no db/db_name → Task 2 Step 1. ✓
- link returns EdgeResult → Task 1 (type), Task 2 (impl). ✓
- walk (direction/depth/relation_types/max_results), structure-only → Task 2. ✓
- neighbors = depth-1 → Task 2. ✓
- find + path cut → Task 2 (no find/path methods), Task 3 (tests deleted). ✓
- EdgeResult/PathStep/PathResult serializable, no _id/_rev leak; field_names
  shape-not-values → Task 1 + Task 2 `_field_names` + Task 4 property 3. ✓
- summary/session NOT in results → absent from PathStep (Task 1). ✓
- Connective tissue, direction, relation filter, truncation, immutability →
  Task 4 properties 4-9. ✓
- CompositionEdge unchanged; Path replaced → Task 1. ✓
- Live-DB-not-mock → every test prompt + governance. ✓
- Builder/tester separation → src commits (1,2) vs tests commits (3,4) separate;
  Task 5 Step 2 self-check. ✓

**Deferred-by-spec, correctly absent:** network transport, content/full-text
index, multi-tenant enforcement, hamut'ay migration (note deferred until green),
259-edge migration, other edge types, retraction, path(). ✓

**Placeholder scan:** no TBD/TODO; every code step shows code; every test step
names file + expected pass/fail. ✓

**Type consistency:** `LlikaService(tier, provenance)`, `link(...)->EdgeResult`,
`walk(start_id,direction,depth,relation_types,max_results)->list[PathResult]`,
`neighbors(start_id,direction,relation_types)`, `PathStep(record_id,
relation_type,field_names)`, `PathResult(start_id,steps)` — identical across
Tasks 1,2,4. `RelationType` names (strings) used consistently in walk filter and
Codex contract. ✓

**Known execution risk flagged:** Task 2 Step 4 — other tests/src importing the
removed `Path` would break; the plan greps for them and routes fixes by owner
(tests→Codex, src→builder), preserving separation. Real contingency, named.
```
