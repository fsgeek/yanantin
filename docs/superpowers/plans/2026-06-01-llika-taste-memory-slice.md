# Llika Taste-Memory Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the connection singleton (`get_database`) and a minimal Llika graph service (`link`, `find`) so the taste entity gets persistent, traversable memory — proving store→link→find end-to-end over real storage.

**Architecture:** Two subsystems, sequenced by dependency. **(A) Connection singleton** — a module-level memoized `get_database()` in `infra/config.py` keyed on `(host, db_name, username)`, with resolution (explicit arg > env > config) happening *before* memoization; the three existing `ArangoClient` construction sites retrofit to use it. **(B) Llika graph service** — a new `src/yanantin/llika/` package (`CompositionEdge` model, `LlikaService.link/find`) built on the proven singleton. A must land green before B.

**Tech Stack:** Python 3.14, uv, python-arango, pydantic (via tiksi `ApachetaBaseModel`), pytest. Live `apacheta_test` DB at `192.168.111.125:8529` for storage-behavior tests (no mocked DB — memory `feedback-no-mock-databases`).

**Spec:** `docs/superpowers/specs/2026-05-31-llika-taste-memory-slice-design.md`

---

## Governance constraints (apply to EVERY task)

- **Builder/tester separation** (`.github/workflows/separation.yml`): no commit
  touches both `src/` and `tests/`. Implementation and tests land in **separate
  commits**. Tests are authored by **Codex** (gpt-5.3-codex) from the invariant
  contract, NOT by the builder. Dispatch:
  `codex exec --sandbox workspace-write "<prompt>" < /dev/null 2>&1 | tail -60`
  (no `-m` flag; `< /dev/null` for the stdin bug — memory
  `feedback-codex-and-prescription`).
- **Codex prompts are non-prescriptive:** hand the invariant + the module's
  importable surface, NOT an assertion list. Verify Codex's tests RED against
  pre-implementation code before trusting them.
- **AI commits** use per-command git identity overrides (Yanantin key
  `1E416B1FB63AF88179EE0F38D0CAB9659C950893`,
  `Yanantin AI (Claude Opus) <yanantin@wamason.com>`, `commit.gpgsign=true`),
  never repo-level config.
- **Declared-loss-is-debt** (memory): if you edit a file containing a known bug
  identical to one already fixed elsewhere, fix it in the same body of work —
  do not log it as a follow-up while standing in the code. (This is why Task 5
  ports the conn-error discrimination to activity.)

---

## File Structure

**Subsystem A — singleton:**
- Modify `src/yanantin/infra/config.py` — add module-level `get_database()`; `ApachetaDBConfig.connect()` delegates to it.
- Modify `src/yanantin/apacheta/backends/arango.py:104` — source client/db from `get_database`, preserve conn-error discrimination.
- Modify `src/yanantin/activity/backends/arango.py:50,59-66` — source from `get_database` AND port the 3-way conn-error discrimination (same classes from `apacheta.interface.errors`).
- Test: `tests/integration/test_get_database_singleton.py` (Codex, live DB).

**Subsystem B — Llika:**
- Create `src/yanantin/llika/__init__.py` — public exports.
- Create `src/yanantin/llika/models.py` — `CompositionEdge`, `Path`.
- Create `src/yanantin/llika/service.py` — `LlikaService.link/find`.
- Test: `tests/integration/test_llika_service.py` (Codex, live DB).

---

# SUBSYSTEM A — Connection Singleton

### Task 1: `get_database` — resolve-then-memoize

**Files:**
- Modify: `src/yanantin/infra/config.py` (add module-level function + helpers, after the `ApachetaDBConfig` class)
- Test: `tests/integration/test_get_database_singleton.py` (Codex authors — see Task 2)

**Context the engineer needs:** `infra/config.py` already has an
`ApachetaDBConfig` singleton (via `__new__`/`_instance`) that owns *credentials*
and an `_DEFAULT_CONFIG_FILE` at `~/.yanantin/config/db.ini`. It already emits
`YANANTIN_ARANGO_HOST`/`_DB`/`_USER`/`_PASSWORD` via `write_env()`. What's
missing is a singleton *database handle*. `get_database` is that — a
module-level memoized function. The config object's `connect()` will delegate
to it in Task 3.

- [ ] **Step 1: Write the implementation (builder commit — NO test in this commit)**

In `src/yanantin/infra/config.py`, add after the `ApachetaDBConfig` class. Note the import additions at top (`functools`, `StandardDatabase` type):

```python
# --- add to imports at top of file ---
import functools
from arango.database import StandardDatabase


# --- add at module level, after the ApachetaDBConfig class ---
def _resolve_db_params(
    host: str | None,
    db_name: str | None,
    username: str | None,
    password: str | None,
) -> tuple[str, str, str, str]:
    """Resolve each connection field: explicit arg > env var > config file.

    Resolution happens HERE, before memoization, so that two calls that mean
    the same target (e.g. get_database() and get_database(db_name='apacheta'))
    resolve to the same (host, db_name, username) key and do NOT split into two
    connections. The cache in get_database() sits BEHIND this function.
    """
    cfg = ApachetaDBConfig()  # the credential singleton (load-or-create)
    app_creds = cfg.get_app_credentials()  # {"username", "password"}

    host = host or os.environ.get("YANANTIN_ARANGO_HOST") or cfg.host_url
    db_name = db_name or os.environ.get("YANANTIN_ARANGO_DB") or cfg.db["database"]
    username = username or os.environ.get("YANANTIN_ARANGO_USER") or app_creds["username"]
    password = password or os.environ.get("YANANTIN_ARANGO_PASSWORD") or app_creds["password"]
    return host, db_name, username, password


@functools.lru_cache(maxsize=None)
def _connect_memoized(host: str, db_name: str, username: str, password: str) -> StandardDatabase:
    """One ArangoClient + db handle per distinct resolved target. Memoized.

    Keyed on all four resolved values (password included here only because
    lru_cache keys on all args; the PUBLIC identity contract is per
    (host, db_name, username) — see get_database)."""
    client = ArangoClient(hosts=host)
    return client.db(db_name, username=username, password=password)


def get_database(
    host: str | None = None,
    db_name: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> StandardDatabase:
    """Return the shared ArangoDB handle for a connection target.

    Resolve-then-memoize: fields resolve (explicit > env > config), then the
    resolved (host, db_name, username) determines identity. Two callers meaning
    the same target share one handle; different usernames (the tier boundary,
    enforced by the DB grant) or db_names get distinct handles.

    To reset (tests): get_database.cache_clear().
    """
    resolved = _resolve_db_params(host, db_name, username, password)
    return _connect_memoized(*resolved)


# expose cache_clear on the public name for test isolation
get_database.cache_clear = _connect_memoized.cache_clear
```

- [ ] **Step 2: Verify it imports**

Run: `uv run python -c "from yanantin.infra.config import get_database; print(get_database, get_database.cache_clear)"`
Expected: prints the function and a `cache_clear` callable, no error.

- [ ] **Step 3: Commit (builder)**

```bash
git add src/yanantin/infra/config.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "feat(infra): get_database singleton — resolve-then-memoize"
```

---

### Task 2: Codex authors the singleton-identity tests (live DB)

**Files:**
- Test: `tests/integration/test_get_database_singleton.py` (Codex creates)

- [ ] **Step 1: Dispatch Codex with the invariant contract (NOT an assertion list)**

Write the prompt to `/tmp/codex_singleton_prompt.md`, then dispatch. The prompt body:

```
You are the independent test author for `get_database` in the yanantin project
(Python 3.14, uv, repo /home/tony/projects/yanantin). Design tests from the
CONTRACT below — do NOT transcribe an existing test, and do NOT read any
existing test file for this function. Write to a NEW file:
tests/integration/test_get_database_singleton.py. Run with
`uv run pytest`. Use the LIVE database (apacheta_test, 192.168.111.125:8529) —
do NOT mock ArangoClient; a mock cannot witness "same connection". Test
credentials are in the config (ApachetaDBConfig().get_test_credentials()) and
in YANANTIN_ARANGO_* env vars.

CONTRACT — get_database(host=None, db_name=None, username=None, password=None)
returns a shared StandardDatabase handle. It resolves each field (explicit arg
> env var > config file) THEN memoizes on the resolved (host, db_name,
username). get_database.cache_clear() resets the memo. It is process-global
memoized state.

Properties that must hold (decide for yourself how to assert each, what to set
up, and what else could break):
1. Two calls resolving to the same (host, db_name, username) return the SAME
   handle — proven meaningfully (a write through one is visible to a read
   through the other sharing a real view of storage), however the fields were
   spelled (all-default vs partially-explicit-but-equivalent).
2. Different usernames -> different handles (tier boundary; the DB grant ties a
   user to one database).
3. Different db_names -> different handles (app vs test isolation).
4. Per-field precedence: explicit arg beats env var beats config — e.g. an
   explicit db_name with other fields from env resolves correctly.
5. Resolution precedes memoization: calls differing only in spelling but
   resolving identically do not split into two connections.

get_database is process-global; you must handle cache isolation between tests
so one test's resolved handle doesn't leak into the next and mask a bug. Choose
the isolation strategy yourself. When done, report how many tests, what each
covers in one line, and pass/fail. If any fail, say so — do not adjust the
contract to make them pass.
```

Dispatch: `codex exec --sandbox workspace-write "$(cat /tmp/codex_singleton_prompt.md)" < /dev/null 2>&1 | tail -60`

- [ ] **Step 2: Verify Codex's tests RED against pre-Task-1 code (integrity check)**

```bash
git stash push -- src/yanantin/infra/config.py   # remove get_database
uv run pytest tests/integration/test_get_database_singleton.py -q 2>&1 | tail -15
git stash pop
```
Expected: tests FAIL (ImportError on `get_database`, or assertion failures) — proving they test the new behavior, not pre-existing behavior. If any pass against stashed code, scrutinize that test.

- [ ] **Step 3: Verify GREEN against Task-1 code**

Run: `uv run pytest tests/integration/test_get_database_singleton.py -q`
Expected: all pass.

- [ ] **Step 4: Adversarially check Codex's cache-isolation choice**

Read the test file. Confirm its isolation actually prevents leakage: does each identity test start from a known cache state (e.g. `get_database.cache_clear()` in a fixture)? A test that asserts "same handle" after a prior test seeded the cache with that handle proves nothing. If the isolation has a hole, note it and ask Codex to revise (re-dispatch referencing the specific hole) — do not fix the test yourself (separation).

- [ ] **Step 5: Commit (tester)**

```bash
git add tests/integration/test_get_database_singleton.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "test(infra): get_database singleton identity (Codex, live DB)"
```

---

### Task 3: `connect()` delegates to `get_database`

**Files:**
- Modify: `src/yanantin/infra/config.py:147-164` (the `connect` method)

**Context:** `connect(tier)` currently builds a fresh `ArangoClient` every call
(line 163). It becomes a thin tier→credentials wrapper over `get_database`, so
the singleton is the one connection path. Tier→target mapping stays here.

- [ ] **Step 1: Rewrite `connect` (builder)**

Replace the body of `connect` (currently lines 147-164):

```python
    def connect(self, tier: str = "test") -> StandardDatabase:
        """Connect to ArangoDB and return the shared database handle.

        Args:
            tier: "admin" (connects to _system), "app", or "test"

        Delegates to the module-level get_database singleton so all consumers
        share one connection per resolved target.
        """
        creds = {
            "admin": self.get_admin_credentials,
            "app": self.get_app_credentials,
            "test": self.get_test_credentials,
        }[tier]()
        db_name = "_system" if tier == "admin" else (
            self.db["database"] if tier == "app" else "apacheta_test"
        )
        return get_database(
            host=self.host_url,
            db_name=db_name,
            username=creds["username"],
            password=creds["password"],
        )
```

- [ ] **Step 2: Run the existing config/infra test suite**

Run: `uv run pytest tests/ -k "config or infra or orchestrator" -q`
Expected: PASS (no regression — `connect` returns the same kind of handle).

- [ ] **Step 3: Commit (builder)**

```bash
git add src/yanantin/infra/config.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "refactor(infra): connect() delegates to get_database singleton"
```

---

### Task 4: Retrofit apacheta backend — client from singleton, preserve discrimination

**Files:**
- Modify: `src/yanantin/apacheta/backends/arango.py:104,111-121`

**Context — DO NOT REGRESS:** This file was fixed 2026-05-31 to discriminate
connection-failure modes; the guard is `tests/unit/test_arango_conn_errors.py`
(Codex-authored). The retrofit changes WHERE the client/db comes from, NOT how
failures are diagnosed. `_discriminate_connection_failure` and its tests must
stay green.

- [ ] **Step 1: Rewrite the client/connect lines (builder)**

In `__init__` (line ~104), the backend currently does `self._client = ArangoClient(hosts=host)` then `self._db = self._connect_database()`. Change `_connect_database` to source the handle from `get_database`, keeping the discrimination wrapper. Add import: `from yanantin.infra.config import get_database`.

Replace the `try` block in `_connect_database` (currently the `client.db(...)` + `db.collections()` lines):

```python
    def _connect_database(self) -> StandardDatabase:
        """Connect to the target database via the shared singleton. Fail-stop
        with a discriminated error if it doesn't exist / auth fails / unreachable."""
        try:
            db = get_database(
                host=self._host,
                db_name=self._db_name,
                username=self._username,
                password=self._password,
            )
            db.collections()  # verify the connection works
            return db
        except Exception as e:
            raise self._discriminate_connection_failure(e) from e
```

Remove the now-unused `self._client = ArangoClient(hosts=host)` line in `__init__` (the singleton owns the client). Keep `self._host`, `self._db_name`, etc.

- [ ] **Step 2: Run the conn-error guard + arango suite**

Run: `uv run pytest tests/unit/test_arango_conn_errors.py tests/unit/test_arango_independent.py -q`
Expected: PASS (discrimination preserved). NOTE: tests that mock `ArangoClient` at `yanantin.apacheta.backends.arango.ArangoClient` may need the mock target to move to `yanantin.infra.config.ArangoClient` — if a test fails on mock-patching, that is a test concern; flag it for Codex to revise, do not edit the test yourself.

- [ ] **Step 3: Commit (builder)**

```bash
git add src/yanantin/apacheta/backends/arango.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "refactor(apacheta/arango): source client from get_database singleton"
```

---

### Task 5: Retrofit activity backend — client from singleton + PORT the discrimination

**Files:**
- Modify: `src/yanantin/activity/backends/arango.py:26,50,59-66`

**Context:** activity's `_connect_database` (line ~59-66) has its OWN copy of
the pre-fix blanket "must be provisioned" error. Because we are already editing
this method to swap the client source, we fix the discrimination here too
(declared-loss-is-debt). Activity ALREADY imports from
`apacheta.interface.errors` (line 26) — adding three names is zero new coupling.

- [ ] **Step 1: Extend the errors import + rewrite connect (builder)**

Line 26 — extend the existing import:

```python
from yanantin.apacheta.interface.errors import (
    BackendAuthError,
    BackendUnreachableError,
    DatabaseNotProvisionedError,
    ImmutabilityError,
    NotFoundError,
)
```

Add the driver exception imports near the `arango` imports (line ~21):

```python
from arango.exceptions import ArangoClientError, ArangoServerError, ServerConnectionError
```

Add `from yanantin.infra.config import get_database`. Rewrite `_connect_database` (currently around line 59) to source from the singleton and discriminate (mirroring apacheta's `_discriminate_connection_failure`):

```python
    def _connect_database(self, username: str, password: str) -> StandardDatabase:
        try:
            db = get_database(
                host=self._host,
                db_name=self._db_name,
                username=username,
                password=password,
            )
            db.collections()
            return db
        except Exception as e:
            raise self._discriminate_connection_failure(e) from e

    def _discriminate_connection_failure(self, e: Exception) -> ConnectionError:
        where = f"ArangoDB database '{self._db_name}' at {self._host}"
        if isinstance(e, (ServerConnectionError, ArangoClientError)):
            return BackendUnreachableError(
                f"Cannot reach {where}. Check the host, port, and network "
                f"(is the server running and listening?). Error: {e}"
            )
        http_code = getattr(e, "http_code", None)
        if isinstance(e, ArangoServerError):
            if http_code in (401, 403):
                return BackendAuthError(
                    f"Authentication rejected by {where}. Check the credentials "
                    f"and that the user has access to this database — this is not "
                    f"a provisioning problem. Error: {e}"
                )
            if http_code == 404:
                return DatabaseNotProvisionedError(
                    f"Cannot connect to {where}. Database must be provisioned by "
                    f"an admin before the application can use it. Error: {e}"
                )
        return ConnectionError(f"Unexpected failure connecting to {where}. Error: {e}")
```

Remove the now-unused `self._client = ArangoClient(hosts=host)` line. Keep `self._host`/`self._db_name` assignments (the discrimination message needs them — confirm `self._host` is set in `__init__`; if not, add it).

- [ ] **Step 2: Run the activity test suite**

Run: `uv run pytest tests/ -k "activity" -q`
Expected: PASS. If an activity connection test asserted the old "Cannot connect / must be provisioned" message for a generic failure, it will now fail (the message changed) — flag for Codex to update (same pattern as apacheta's `test_fails_if_database_unreachable` removal), do not edit yourself.

- [ ] **Step 3: Commit (builder)**

```bash
git add src/yanantin/activity/backends/arango.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "refactor(activity/arango): singleton client + port conn-error discrimination"
```

---

### Task 6: Full-suite regression gate for subsystem A

- [ ] **Step 1: Run the entire unit + integration suite**

Run: `uv run pytest tests/unit tests/integration -q 2>&1 | tail -15`
Expected: all pass (modulo any tests Codex still owes a revision on from Tasks 4/5 — those must be resolved before proceeding to subsystem B).

- [ ] **Step 2: Confirm only 2 ArangoClient sites remain (config is the only constructor)**

Run: `grep -rn "ArangoClient(" src/yanantin/ | grep -v __pycache__`
Expected: exactly ONE construction site — `infra/config.py` (inside `_connect_memoized`). apacheta and activity no longer construct their own. (If `infra/orchestrator.py` constructs one for admin provisioning, that is acceptable and out of scope — note it, don't change it.)

---

# SUBSYSTEM B — Llika Graph Service

### Task 7: `CompositionEdge` and `Path` models

**Files:**
- Create: `src/yanantin/llika/__init__.py`
- Create: `src/yanantin/llika/models.py`

**Context:** Edge models inherit `ApachetaBaseModel` (from tiksi:
`from yanantin.apacheta.models.base import ApachetaBaseModel` — re-exported;
config is `frozen=True, extra="allow"`). `RelationType` (10 members) is at
`yanantin.apacheta.models.composition`. `ProvenanceEnvelope` at
`yanantin.apacheta.models` (tiksi-backed). ArangoDB edges need `_from`/`_to` as
`tensors/<uuid>`-style refs; pydantic forbids leading-underscore field names, so
use aliases.

- [ ] **Step 1: Write `models.py` (builder)**

```python
# src/yanantin/llika/models.py
"""Llika edge and traversal models. Frozen, extra='allow', append-only."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import Field

from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.composition import RelationType


class CompositionEdge(ApachetaBaseModel):
    """A native ArangoDB edge between two vertices. Immutable once created."""
    id: UUID = Field(default_factory=uuid4)
    from_ref: str = Field(alias="_from")   # e.g. "tensors/<uuid>"
    to_ref: str = Field(alias="_to")
    created_at: datetime
    relation_type: RelationType
    provenance: ProvenanceEnvelope


class Path(ApachetaBaseModel):
    """An ordered traversal result: the path is the answer, not just the end.

    vertices and edges are raw dicts as returned by ArangoDB — Llika does not
    interpret vertex kinds (per llika-spec)."""
    vertices: tuple[dict, ...]
    edges: tuple[dict, ...]
```

- [ ] **Step 2: Write `__init__.py` (builder)**

```python
# src/yanantin/llika/__init__.py
"""Llika — graph-structured index service over ArangoDB native edges."""
from yanantin.llika.models import CompositionEdge, Path
from yanantin.llika.service import LlikaService

__all__ = ["CompositionEdge", "Path", "LlikaService"]
```

(Note: `__init__` imports `LlikaService` from Task 8 — it will not import-clean until Task 8 lands. That is expected; commit `models.py` now, `__init__` after Task 8. To verify Step 1 in isolation, import `models` directly.)

- [ ] **Step 3: Verify models import**

Run: `uv run python -c "from yanantin.llika.models import CompositionEdge, Path; print(CompositionEdge.model_config)"`
Expected: prints config showing `frozen` and `extra='allow'`, no error.

- [ ] **Step 4: Commit (builder)**

```bash
git add src/yanantin/llika/models.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "feat(llika): CompositionEdge + Path models"
```

---

### Task 8: `LlikaService.link` and `find`

**Files:**
- Create: `src/yanantin/llika/service.py`
- Modify: `src/yanantin/llika/__init__.py` (becomes import-clean now)

**Context:** `link` creates a native edge in the `llika_composition` edge
collection (create it if absent). `find` runs an AQL traversal
`FOR v, e, p IN 1..max_depth OUTBOUND @start ...` and evaluates the Python
`predicate` on each discovered vertex, collecting paths to matches. Edge
collections in ArangoDB are created with `create_collection(name, edge=True)`.

- [ ] **Step 1: Write `service.py` (builder)**

```python
# src/yanantin/llika/service.py
"""LlikaService — thin graph service over a shared ArangoDB handle."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from uuid import uuid4

from arango.database import StandardDatabase

from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.composition import RelationType
from yanantin.llika.models import CompositionEdge, Path

_EDGE_COLLECTION = "llika_composition"


class LlikaService:
    """Create and traverse native ArangoDB edges. Append-only; no update/delete."""

    def __init__(self, db: StandardDatabase, provenance: ProvenanceEnvelope):
        self._db = db
        self._provenance = provenance
        if not db.has_collection(_EDGE_COLLECTION):
            db.create_collection(_EDGE_COLLECTION, edge=True)
        self._edges = db.collection(_EDGE_COLLECTION)

    def link(self, from_id: str, to_id: str, relation_type: RelationType, **kwargs) -> CompositionEdge:
        """Create one immutable edge from_id -> to_id. kwargs become open fields."""
        edge = CompositionEdge(
            **{"_from": from_id, "_to": to_id},
            created_at=datetime.now(timezone.utc),
            relation_type=relation_type,
            provenance=self._provenance,
            **kwargs,
        )
        doc = edge.model_dump(by_alias=True, mode="json")
        self._edges.insert(doc)
        return edge

    def find(
        self,
        vertex_id: str,
        predicate: Callable[[dict], bool],
        max_depth: int = 4,
        max_results: int = 50,
    ) -> list[Path]:
        """Walk OUTBOUND from vertex_id; return paths to vertices matching
        predicate (Python-side), capped at max_results in traversal order.

        SCOPE (Phase 1): raw traversal — walks ALL edges including superseded
        ones; honors NO retraction semantics. The path is the answer."""
        aql = f"""
        FOR v, e, p IN 1..@max_depth OUTBOUND @start {_EDGE_COLLECTION}
            RETURN p
        """
        cursor = self._db.aql.execute(
            aql, bind_vars={"max_depth": max_depth, "start": vertex_id}
        )
        results: list[Path] = []
        for p in cursor:
            terminal = p["vertices"][-1]
            if predicate(terminal):
                results.append(
                    Path(vertices=tuple(p["vertices"]), edges=tuple(p["edges"]))
                )
                if len(results) >= max_results:
                    break
        return results
```

- [ ] **Step 2: Verify the package imports clean**

Run: `uv run python -c "from yanantin.llika import LlikaService, CompositionEdge, Path; print('ok')"`
Expected: prints `ok`, no error.

- [ ] **Step 3: Commit (builder)**

```bash
git add src/yanantin/llika/service.py src/yanantin/llika/__init__.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "feat(llika): LlikaService link + find (traversal)"
```

---

### Task 9: Codex authors the Llika service tests (live DB)

**Files:**
- Test: `tests/integration/test_llika_service.py` (Codex creates)

- [ ] **Step 1: Dispatch Codex with the invariant contract**

Write to `/tmp/codex_llika_prompt.md`, then dispatch. Body:

```
You are the independent test author for LlikaService in the yanantin project
(Python 3.14, uv, repo /home/tony/projects/yanantin). Design tests from the
CONTRACT below — do NOT transcribe an existing test, do NOT read other test
files for this service. Write to NEW file
tests/integration/test_llika_service.py, run with `uv run pytest`. Use the LIVE
apacheta_test database (do NOT mock — a mock cannot witness that a written edge
is actually traversable). Get a handle via
`from yanantin.infra.config import get_database; db = get_database(db_name='apacheta_test', ...)`
using test credentials (ApachetaDBConfig().get_test_credentials()).

Importable surface:
- yanantin.llika.LlikaService(db: StandardDatabase, provenance: ProvenanceEnvelope)
    .link(from_id: str, to_id: str, relation_type: RelationType, **kwargs) -> CompositionEdge
    .find(vertex_id: str, predicate: Callable[[dict], bool], max_depth=4, max_results=50) -> list[Path]
- yanantin.llika.CompositionEdge (frozen, extra=allow; fields incl _from/_to aliases)
- yanantin.llika.Path (vertices: tuple[dict,...], edges: tuple[dict,...])
- RelationType at yanantin.apacheta.models.composition (e.g. RelationType.COMPOSES_WITH)
- ProvenanceEnvelope at yanantin.apacheta.models
You will need real vertex documents to link between — create throwaway docs in
a test collection (e.g. insert into a 'tensors' collection or a temp collection)
so _from/_to refs resolve. Clean up edges/vertices you create.

Properties that must hold (decide assertions, setup, and edge cases yourself):
6. An edge written by link() is traversable by find() — round-trip through real
   storage (write A->B, find from A reaches B).
7. find() returns the PATH (vertices + edges), not just the terminal vertex,
   and stops at predicate match.
8. MULTI-HOP CONNECTIVE TISSUE: build depth >= 3 (A->B->C->D); find from A with
   a predicate matching ONLY the far end (D), naming nothing about B/C; assert
   the returned path CARRIES B and C — vertices the predicate never mentioned.
   A single-hop test does NOT satisfy this. This is the property that earns the
   "discovery is in the path" claim.
9. TRUNCATION OBSERVABLE: with more matches than max_results, find() returns
   exactly max_results paths (capped is not error, not the whole population).
10. Edges are immutable — there is no update/delete affordance on LlikaService
    or CompositionEdge (assert the absence of such methods / frozen model).

Report test count, one-line coverage each, pass/fail. If any fail, say so — do
not adjust the contract.
```

Dispatch: `codex exec --sandbox workspace-write "$(cat /tmp/codex_llika_prompt.md)" < /dev/null 2>&1 | tail -60`

- [ ] **Step 2: Verify RED against pre-service code**

```bash
git stash push -- src/yanantin/llika/service.py
uv run pytest tests/integration/test_llika_service.py -q 2>&1 | tail -15
git stash pop
```
Expected: FAIL (ImportError on LlikaService). Confirms coupling to the new code.

- [ ] **Step 3: Verify GREEN**

Run: `uv run pytest tests/integration/test_llika_service.py -q`
Expected: all pass.

- [ ] **Step 4: Adversarially check the connective-tissue test (property 8)**

Read the test for property 8. Confirm it ACTUALLY builds depth ≥ 3 and asserts the intermediate vertices are present in the returned path — NOT a single hop, NOT just asserting the terminal. This is the property most likely to be under-built (the morning's whole lesson). If it's single-hop, re-dispatch Codex citing the specific gap; do not fix it yourself.

- [ ] **Step 5: Commit (tester)**

```bash
git add tests/integration/test_llika_service.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" -c commit.gpgsign=true \
  commit -m "test(llika): link/find round-trip + connective tissue (Codex, live DB)"
```

---

### Task 10: End-to-end slice gate + final regression

- [ ] **Step 1: Full suite**

Run: `uv run pytest tests/ -q 2>&1 | tail -15`
Expected: all pass.

- [ ] **Step 2: Separation-gate self-check across all new commits**

```bash
for C in $(git log --oneline origin/main..HEAD | awk '{print $1}'); do
  F=$(git diff-tree --no-commit-id --name-only -r "$C")
  S=$(echo "$F" | grep -c '^src/'); T=$(echo "$F" | grep -c '^tests/')
  if [ "$S" -gt 0 ] && [ "$T" -gt 0 ]; then echo "$C VIOLATES (src+tests)"; else echo "$C ok"; fi
done
```
Expected: every commit `ok` — no commit mixes src/ and tests/.

- [ ] **Step 3: Confirm the store→link→find narrative works as a script**

Run a short manual script (not committed) that: gets a handle via `get_database`, constructs `LlikaService`, links three real vertices A→B→C, and `find`s from A with a predicate matching C — asserting the path carries B. This is the human-legible proof the slice's headline claim holds end-to-end. Report the path returned.

---

## Self-Review (completed by plan author)

**Spec coverage:**
- get_database resolve-then-memoize + 3-site retrofit → Tasks 1,3,4,5. ✓
- Singleton identity invariants 1–5 → Task 2 (Codex). ✓
- CompositionEdge / Path / link / find → Tasks 7,8. ✓
- Llika invariants 6–10 (incl. connective tissue, truncation) → Task 9 (Codex). ✓
- Live-DB-not-mock discipline → stated in every Codex prompt + governance. ✓
- Preserve apacheta conn-error discrimination → Task 4 context + Step 2 guard. ✓
- Activity conn-error port (declared-loss-is-debt) → Task 5. ✓
- Builder/tester separation → separate commits throughout + Task 10 Step 2. ✓
- find() max_depth=4/max_results=50 guard → Task 8 signature. ✓

**Deferred-by-spec, correctly absent from plan:** edge supersession/retraction,
other 3 edge types, neighbors/walk/path, migration, HTTP predicate protocol,
singleton liveness/reconnect. (All in spec's Declared Losses / Follow-ups.)

**Placeholder scan:** no TBD/TODO; every code step shows code; every test step
names the file and expected pass/fail. ✓

**Type consistency:** `get_database(host,db_name,username,password)` signature
identical across Tasks 1,3,4,5,9. `CompositionEdge`/`Path`/`LlikaService.link`/
`find` signatures identical Tasks 7,8,9. `RelationType`, `ProvenanceEnvelope`
import paths consistent. ✓

**Known interface risk flagged for execution:** Tasks 4/5 may break tests that
mock `ArangoClient` at the old construction site (now moved to
`infra.config`). The plan flags this in-task and routes the fix to Codex
(test revision), not the builder — preserving separation. This is a real
execution-time contingency, named, not a placeholder.
