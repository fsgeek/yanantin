# Khipu / watay Collection-Binding Mechanism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `Khipu`, the dynamic collection-binding service — the sole creator of ArangoDB collections — with verb `watay(name, definition) -> handle`: create-if-absent, additive indices, ArangoSearch views, schema applied only at creation, names routed through the obfuscator.

**Architecture:** A new service `core/khipu.py` adjacent to (never merged with) `core/registration.py:Registrar`. A `CollectionDefinition` value object carries schema + indices + views. `watay` consults a `well_known_collections` registry for well-known names or takes a minted name, obfuscates the name, and ensures the collection + its indices + views exist — idempotently and never destructively. Schema is generated from a Pydantic model via a ported `arangodb_schema()` envelope helper.

**Tech Stack:** Python 3.14, uv-managed, `python-arango` (`StandardDatabase`, `StandardCollection`), Pydantic v2, pytest against live `apacheta_test`.

## Global Constraints

- Python 3.14, uv-managed (`uv run pytest ...`). Copied verbatim from project norms.
- Tests run against the LIVE `apacheta_test` database — NO mock databases for storage behavior (`feedback_no_mock_databases`). Use the `live_db` fixture pattern from `tests/integration/test_core_registration.py:92`.
- Collection names route THROUGH the obfuscator (C0 invariant, `core/registration.py:89`). The physical collection the DB sees is the obfuscated name; the semantic name lives only in code/registry. Default obfuscator is `TransparentObfuscator` (`core/storage_obfuscator.py:40`).
- `Khipu` owns name→definition→handle ONLY. It owns NOTHING about provider identity — that is `Registrar.register` (op 2). Do not add `Identifier`/`Name`/`Description`/`Version`/provider-`Record` fields to any `Khipu` type.
- Init contract is NEVER destructive: create-if-absent for collection/index/view; schema applied ONLY at collection creation, NEVER on an existing collection.
- AI commits use per-command git config overrides (Yanantin identity), not repo config. Commit message co-author trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. For plan execution, standard `git commit` is acceptable; the final sweep is signed separately.
- Test collections use a `uuid4().hex` suffix and are dropped in a `finally` block (pattern from `tests/integration/test_temporal_query.py`) so they never collide on shared `apacheta_test`.

---

## File Structure

- `src/yanantin/core/collection_definition.py` (new) — `CollectionDefinition` value object (schema/indices/views) + `arangodb_schema(model)` envelope helper. One responsibility: describe a collection.
- `src/yanantin/core/khipu.py` (new) — `Khipu` service + `watay`. One responsibility: ensure a collection exists matching its definition, idempotently, obfuscator-routed.
- `src/yanantin/core/well_known_collections.py` (new) — pure-data registry: semantic name → `CollectionDefinition`. No logic.
- `tests/integration/test_khipu.py` (new) — green-path + idempotency + obfuscation tests.
- `tests/red_bar/test_khipu_schema_never_reconciled.py` (new) — the negative-requirement red bar.

---

### Task 1: `arangodb_schema()` envelope helper + `CollectionDefinition`

**Files:**
- Create: `src/yanantin/core/collection_definition.py`
- Test: `tests/integration/test_khipu.py`

**Interfaces:**
- Consumes: nothing (leaf task).
- Produces:
  - `arangodb_schema(model: type[BaseModel]) -> dict` — returns `{"message": str, "level": "strict", "type": "json", "rule": model.model_json_schema()}`.
  - `CollectionDefinition` (frozen Pydantic model): fields `schema: dict | None = None`, `indices: tuple[dict, ...] = ()`, `views: tuple[dict, ...] = ()`, `edge: bool = False`.

- [ ] **Step 1: Write the failing test**

```python
# in tests/integration/test_khipu.py
from pydantic import BaseModel
from yanantin.core.collection_definition import arangodb_schema, CollectionDefinition


class _SampleModel(BaseModel):
    name: str
    count: int


def test_arangodb_schema_wraps_model_json_schema():
    env = arangodb_schema(_SampleModel)
    assert env["level"] == "strict"
    assert env["type"] == "json"
    assert env["rule"] == _SampleModel.model_json_schema()
    assert "message" in env


def test_collection_definition_defaults_are_empty():
    d = CollectionDefinition()
    assert d.schema is None
    assert d.indices == ()
    assert d.views == ()
    assert d.edge is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_khipu.py::test_arangodb_schema_wraps_model_json_schema tests/integration/test_khipu.py::test_collection_definition_defaults_are_empty -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yanantin.core.collection_definition'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/yanantin/core/collection_definition.py
"""A collection's shape: schema (from a Pydantic model), indices, views.

`Khipu.watay` consumes a CollectionDefinition to create+shape a collection.
Schema is generated from the model via arangodb_schema() — Indaleko's envelope
(data_models/base.py:93) ported verbatim: level 'strict' = validate on every
write (NOT 'no extra fields'; that is additionalProperties, governed by the
model's extra= config). A model with extra='allow' keeps an open lane.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


def arangodb_schema(model: type[BaseModel]) -> dict:
    """Wrap a Pydantic model's JSON schema in ArangoDB's validation envelope."""
    return {
        "message": "Document did not conform to the collection schema.",
        "level": "strict",
        "type": "json",
        "rule": model.model_json_schema(),
    }


class CollectionDefinition(BaseModel):
    """The shape of one collection. Pure data; no DB handle, no identity."""

    model_config = ConfigDict(frozen=True)

    schema: dict | None = None
    indices: tuple[dict, ...] = ()
    views: tuple[dict, ...] = ()
    edge: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_khipu.py::test_arangodb_schema_wraps_model_json_schema tests/integration/test_khipu.py::test_collection_definition_defaults_are_empty -v`
Expected: PASS (both)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/core/collection_definition.py tests/integration/test_khipu.py
git commit -m "feat(core): CollectionDefinition + arangodb_schema envelope helper"
```

---

### Task 2: `Khipu.watay` — create-if-absent collection, obfuscator-routed, schema at creation

**Files:**
- Create: `src/yanantin/core/khipu.py`
- Test: `tests/integration/test_khipu.py`

**Interfaces:**
- Consumes: `CollectionDefinition`, `arangodb_schema` (Task 1); `StorageObfuscator`/`TransparentObfuscator` (`core/storage_obfuscator.py`); `StandardDatabase` (`python-arango`).
- Produces:
  - `Khipu(db: StandardDatabase, obfuscator: StorageObfuscator | None = None)`.
  - `Khipu.watay(name: str, definition: CollectionDefinition) -> StandardCollection` — returns the live (physical/obfuscated) collection handle. Creates the collection if absent and applies `definition.schema` ONLY at creation; applies indices/views (Task 3). Idempotent.

- [ ] **Step 1: Write the failing test**

```python
# in tests/integration/test_khipu.py — add these imports at top:
from uuid import uuid4
import pytest
from yanantin.infra.config import ApachetaDBConfig, get_database
from yanantin.core.khipu import Khipu


@pytest.fixture
def live_db():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )


def test_watay_creates_collection_under_obfuscated_name(live_db):
    semantic = f"khipu_t_{uuid4().hex}"
    khipu = Khipu(db=live_db)  # TransparentObfuscator default → physical == semantic
    try:
        handle = khipu.watay(semantic, CollectionDefinition())
        assert handle.name == semantic
        assert live_db.has_collection(semantic)
    finally:
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)


def test_watay_applies_schema_at_creation(live_db):
    from pydantic import BaseModel

    class _Doc(BaseModel):
        required_field: str

    semantic = f"khipu_t_{uuid4().hex}"
    khipu = Khipu(db=live_db)
    try:
        khipu.watay(semantic, CollectionDefinition(schema=arangodb_schema(_Doc)))
        props = live_db.collection(semantic).properties()
        assert props.get("schema") is not None
        assert props["schema"]["level"] == "strict"
    finally:
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)


def test_watay_is_idempotent(live_db):
    semantic = f"khipu_t_{uuid4().hex}"
    khipu = Khipu(db=live_db)
    try:
        h1 = khipu.watay(semantic, CollectionDefinition())
        h2 = khipu.watay(semantic, CollectionDefinition())
        assert h1.name == h2.name == semantic
        assert live_db.has_collection(semantic)
    finally:
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_khipu.py::test_watay_creates_collection_under_obfuscated_name -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yanantin.core.khipu'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/yanantin/core/khipu.py
"""Khipu — the dynamic collection-binding service (the knotted-cord registry).

Verb `watay` ("to tie/bind"): bind a collection name to its definition and
ensure the collection exists. The SOLE creator of collections (after the legacy
static creators are migrated). Adjacent to core/registration.py:Registrar — NOT
merged: Khipu owns name->definition->handle, Registrar owns provider identity.

Init contract (NEVER destructive):
  - collection: create only if absent
  - schema: applied ONLY at creation; never touched on an existing collection
    (schema is data — an enforcement boundary + published interface; a change
    is a migration, not an init side-effect)
  - indices/views: create-if-absent, additive (Task 3)
"""

from __future__ import annotations

from arango.collection import StandardCollection
from arango.database import StandardDatabase

from yanantin.core.collection_definition import CollectionDefinition
from yanantin.core.storage_obfuscator import StorageObfuscator, TransparentObfuscator


class Khipu:
    """Binds collection names to their definitions; ensures they exist."""

    def __init__(
        self,
        db: StandardDatabase,
        obfuscator: StorageObfuscator | None = None,
    ) -> None:
        self._db = db
        self._obfuscator = obfuscator or TransparentObfuscator()

    def watay(
        self, name: str, definition: CollectionDefinition
    ) -> StandardCollection:
        """Bind semantic `name` to `definition`; ensure the collection exists.

        Returns the live (physical/obfuscated) collection handle. Schema is
        applied ONLY when the collection is newly created.
        """
        physical = self._obfuscator.collection_name(name)
        if not self._db.has_collection(physical):
            collection = self._db.create_collection(physical, edge=definition.edge)
            if definition.schema is not None:
                collection.configure(schema=definition.schema)
        else:
            collection = self._db.collection(physical)
        return collection
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_khipu.py::test_watay_creates_collection_under_obfuscated_name tests/integration/test_khipu.py::test_watay_applies_schema_at_creation tests/integration/test_khipu.py::test_watay_is_idempotent -v`
Expected: PASS (all three)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/core/khipu.py tests/integration/test_khipu.py
git commit -m "feat(core): Khipu.watay creates collection (obfuscator-routed, schema-at-creation)"
```

---

### Task 3: Additive indices + ArangoSearch views (create-if-absent)

**Files:**
- Modify: `src/yanantin/core/khipu.py` (extend `watay`)
- Test: `tests/integration/test_khipu.py`

**Interfaces:**
- Consumes: Task 2 `Khipu.watay`.
- Produces: `watay` now also ensures each `definition.indices` entry and `definition.views` entry exists. Index dicts are `python-arango` `add_index` payloads (`{"type": "persistent", "fields": [...], "sparse": bool, "name": str}`). View dicts are `{"name": str, "type": "arangosearch", "links": {...}}`. Index/view creation is keyed by index/view NAME for absence-checking.

- [ ] **Step 1: Write the failing test**

```python
# in tests/integration/test_khipu.py
def test_watay_creates_indices_additively(live_db):
    semantic = f"khipu_t_{uuid4().hex}"
    defn = CollectionDefinition(
        indices=(
            {"type": "persistent", "fields": ["uri"], "unique": True, "name": "uri_idx"},
        )
    )
    khipu = Khipu(db=live_db)
    try:
        khipu.watay(semantic, defn)
        idx_names = {i["name"] for i in live_db.collection(semantic).indexes()}
        assert "uri_idx" in idx_names
        # idempotent: second call does not raise on the existing index
        khipu.watay(semantic, defn)
        idx_names2 = {i["name"] for i in live_db.collection(semantic).indexes()}
        assert "uri_idx" in idx_names2
    finally:
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)


def test_watay_creates_arangosearch_view(live_db):
    semantic = f"khipu_t_{uuid4().hex}"
    view_name = f"khipu_view_{uuid4().hex}"
    defn = CollectionDefinition(
        views=(
            {
                "name": view_name,
                "type": "arangosearch",
                "links": {semantic: {"fields": {"label": {"analyzers": ["text_en"]}}}},
            },
        )
    )
    khipu = Khipu(db=live_db)
    try:
        khipu.watay(semantic, defn)
        view_names = {v["name"] for v in live_db.views()}
        assert view_name in view_names
    finally:
        if view_name in {v["name"] for v in live_db.views()}:
            live_db.delete_view(view_name)
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_khipu.py::test_watay_creates_indices_additively tests/integration/test_khipu.py::test_watay_creates_arangosearch_view -v`
Expected: FAIL — `uri_idx` not in index names (indices not yet applied) / view not created.

- [ ] **Step 3: Write minimal implementation**

```python
# src/yanantin/core/khipu.py — replace the watay method body's return with the
# index/view ensure-steps before returning. Full updated method:

    def watay(
        self, name: str, definition: CollectionDefinition
    ) -> StandardCollection:
        physical = self._obfuscator.collection_name(name)
        if not self._db.has_collection(physical):
            collection = self._db.create_collection(physical, edge=definition.edge)
            if definition.schema is not None:
                collection.configure(schema=definition.schema)
        else:
            collection = self._db.collection(physical)

        existing_index_names = {i.get("name") for i in collection.indexes()}
        for index in definition.indices:
            if index.get("name") not in existing_index_names:
                collection.add_index(index)

        existing_view_names = {v["name"] for v in self._db.views()}
        for view in definition.views:
            if view["name"] not in existing_view_names:
                self._db.create_arangosearch_view(
                    name=view["name"], properties={"links": view.get("links", {})}
                )

        return collection
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_khipu.py::test_watay_creates_indices_additively tests/integration/test_khipu.py::test_watay_creates_arangosearch_view -v`
Expected: PASS (both)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/core/khipu.py tests/integration/test_khipu.py
git commit -m "feat(core): watay applies indices + arangosearch views (create-if-absent)"
```

---

### Task 4: RED BAR — schema is never reconciled on an existing collection

**Files:**
- Create: `tests/red_bar/test_khipu_schema_never_reconciled.py`

**Interfaces:**
- Consumes: `Khipu`, `CollectionDefinition`, `arangodb_schema` (Tasks 1-2).
- Produces: a governance red bar asserting the negative requirement. This test must PASS (the behavior is already correct from Task 2's "schema only at creation"), and it exists to TRIP if a future change makes `watay` reconcile schema on an existing collection.

- [ ] **Step 1: Write the test (asserts the negative requirement)**

```python
# tests/red_bar/test_khipu_schema_never_reconciled.py
"""RED BAR: watay must NEVER apply or alter schema on a collection that already
exists. Schema is a property of the data (enforcement boundary + published AQL
interface); a change is a migration, not an init side-effect. If this trips,
someone made watay reconcile schema on an existing collection — STOP.
"""

from uuid import uuid4

import pytest
from pydantic import BaseModel

from yanantin.core.collection_definition import CollectionDefinition, arangodb_schema
from yanantin.core.khipu import Khipu
from yanantin.infra.config import ApachetaDBConfig, get_database


class _Doc(BaseModel):
    required_field: str


@pytest.fixture
def live_db():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )


def test_watay_does_not_apply_schema_to_preexisting_schemaless_collection(live_db):
    semantic = f"khipu_rb_{uuid4().hex}"
    khipu = Khipu(db=live_db)
    try:
        # 1. Create the collection schema-less (definition carries no schema).
        khipu.watay(semantic, CollectionDefinition())
        assert live_db.collection(semantic).properties().get("schema") is None

        # 2. watay AGAIN with a now-schema-bearing definition for the same name.
        khipu.watay(semantic, CollectionDefinition(schema=arangodb_schema(_Doc)))

        # 3. The existing collection's schema MUST remain untouched (None).
        #    Applying it here would break the next update to any non-conforming
        #    existing record — that is a migration, not an init side-effect.
        assert live_db.collection(semantic).properties().get("schema") is None
    finally:
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)
```

- [ ] **Step 2: Run the test to verify it PASSES (behavior already correct)**

Run: `uv run pytest tests/red_bar/test_khipu_schema_never_reconciled.py -v`
Expected: PASS — Task 2 already guarantees schema-only-at-creation; this red bar locks it in.

- [ ] **Step 3: (No implementation change — this task is the guard.)**

If the test FAILS, `watay` is reconciling schema on existing collections — fix `watay` so the schema branch runs ONLY inside the `if not has_collection` block (it already does in Task 2; a failure means a regression).

- [ ] **Step 4: Commit**

```bash
git add tests/red_bar/test_khipu_schema_never_reconciled.py
git commit -m "test(red_bar): watay never reconciles schema on an existing collection"
```

---

### Task 5: `well_known_collections` registry (name → CollectionDefinition)

**Files:**
- Create: `src/yanantin/core/well_known_collections.py`
- Test: `tests/integration/test_khipu.py`

**Interfaces:**
- Consumes: `CollectionDefinition` (Task 1).
- Produces:
  - `WELL_KNOWN: dict[str, CollectionDefinition]` — the registry. Seeded with ONE entry to prove the shape: `"khipu_self"` (the registry's own marker collection) → an empty definition. (Storage/activity/semantic definitions are added by their OWN later plans; this plan only proves the registry mechanism, NOT real well-known definitions, per the spec's "this plan is the mechanism alone.")
  - `lookup(name: str) -> CollectionDefinition` — returns the definition for a well-known name, raises `KeyError` with a clear message if absent.

- [ ] **Step 1: Write the failing test**

```python
# in tests/integration/test_khipu.py
from yanantin.core.well_known_collections import WELL_KNOWN, lookup


def test_well_known_registry_is_pure_data():
    # Every value is a CollectionDefinition; no logic objects.
    assert all(isinstance(v, CollectionDefinition) for v in WELL_KNOWN.values())


def test_lookup_returns_definition_for_known_name():
    assert isinstance(lookup("khipu_self"), CollectionDefinition)


def test_lookup_raises_for_unknown_name():
    with pytest.raises(KeyError):
        lookup("definitely_not_registered")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_khipu.py::test_well_known_registry_is_pure_data tests/integration/test_khipu.py::test_lookup_returns_definition_for_known_name tests/integration/test_khipu.py::test_lookup_raises_for_unknown_name -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yanantin.core.well_known_collections'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/yanantin/core/well_known_collections.py
"""The well-known collections registry: semantic name -> CollectionDefinition.

PURE DATA. No logic, no creation. Khipu.watay consults this for a well-known
name's definition ON binding (pulled on demand — NOT an eager startup walk).
This keeps Indaleko's db_collections.py registry SHAPE while deleting its eager
static creator.

This plan (the mechanism) seeds ONE marker entry to prove the registry shape.
Real well-known definitions (Objects, activity_facts, semantic extractors) are
added by their OWN later plans — do not add them here speculatively.
"""

from __future__ import annotations

from yanantin.core.collection_definition import CollectionDefinition

WELL_KNOWN: dict[str, CollectionDefinition] = {
    "khipu_self": CollectionDefinition(),
}


def lookup(name: str) -> CollectionDefinition:
    """Return the definition for a well-known name; raise KeyError if unknown."""
    if name not in WELL_KNOWN:
        raise KeyError(
            f"{name!r} is not a well-known collection. Add it to WELL_KNOWN "
            "in its owning plan, or pass a definition to watay directly."
        )
    return WELL_KNOWN[name]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_khipu.py::test_well_known_registry_is_pure_data tests/integration/test_khipu.py::test_lookup_returns_definition_for_known_name tests/integration/test_khipu.py::test_lookup_raises_for_unknown_name -v`
Expected: PASS (all three)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/core/well_known_collections.py tests/integration/test_khipu.py
git commit -m "feat(core): well_known_collections registry (name -> CollectionDefinition)"
```

---

### Task 6: Full-suite verification + open-lane confirmation

**Files:**
- Test: `tests/integration/test_khipu.py` (add the open-lane test)

**Interfaces:**
- Consumes: all prior tasks.
- Produces: a test confirming an `extra="allow"` model's schema does NOT emit `additionalProperties: false`, so the open semantic-attribute lane survives — guarding against accidental lane-closure.

- [ ] **Step 1: Write the open-lane test**

```python
# in tests/integration/test_khipu.py
def test_open_lane_survives_extra_allow_model():
    from pydantic import BaseModel, ConfigDict

    class _OpenDoc(BaseModel):
        model_config = ConfigDict(extra="allow")
        core: str

    env = arangodb_schema(_OpenDoc)
    # extra='allow' => model_json_schema does NOT set additionalProperties:false.
    assert env["rule"].get("additionalProperties") is not False
```

- [ ] **Step 2: Run the full Khipu suite + the red bar**

Run: `uv run pytest tests/integration/test_khipu.py tests/red_bar/test_khipu_schema_never_reconciled.py -v`
Expected: PASS — every test in both files.

- [ ] **Step 3: Confirm no regression in the existing registration suite**

Run: `uv run pytest tests/integration/test_core_registration.py -v`
Expected: PASS — `Khipu` is adjacent and additive; it must not have touched `Registrar` behavior.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_khipu.py
git commit -m "test(khipu): open-lane survival + full-suite green"
```

---

## Self-Review

**Spec coverage** (against `2026-06-18-dynamic-collection-registration-design.md`):
- `watay(name, definition) -> handle`, sole creator → Tasks 2-3. ✓
- Init contract (create-if-absent collection/index/view) → Tasks 2-3. ✓
- Schema at creation only, NEVER reconciled → Task 2 (behavior) + Task 4 (red bar). ✓
- Schema-from-model envelope, `level: strict` → Task 1. ✓
- Names route through obfuscator (C0 honored) → Task 2 (`collection_name`) + Task 2 test. ✓
- `well_known_collections.py` registry, name→definition, pure data, pulled-on-demand → Task 5. ✓
- `Khipu` ADJACENT to `Registrar`, owns NO provider identity → Global Constraints + Task 6 Step 3 (no-regression). ✓
- Open lane survives (`extra="allow"` ≠ `additionalProperties:false`) → Task 6. ✓
- DEFERRED (correctly NOT in this plan): the three use-cases, real well-known definitions (storage/activity/semantic), static-creator migration, schema-retrofit migration. Each gets its own plan. ✓

**Placeholder scan:** No "TBD"/"handle edge cases"/"similar to". Every code step shows real code; every command shows expected output. ✓

**Type consistency:** `CollectionDefinition` fields (`schema`/`indices`/`views`/`edge`) used identically in Tasks 1, 2, 3, 5. `watay(name, definition) -> StandardCollection` signature identical across Tasks 2, 3, 4. `arangodb_schema(model) -> dict` identical in Tasks 1, 4, 6. `lookup`/`WELL_KNOWN` identical in Task 5. ✓

**Known divergence flagged honestly:** `db.create_arangosearch_view(name=, properties=)` and `col.indexes()`/`col.add_index()` are real `python-arango` methods (verified). ArangoSearch views have no existing yanantin precedent — Task 3 is the first; the link structure in the test is minimal and may need tuning against real fields when a real well-known view lands (its owning use-case plan). This does not block the mechanism.
