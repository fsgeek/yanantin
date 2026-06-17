> # ⛔ SUPERSEDED — DO NOT EXECUTE
> This draft was written BEFORE the collector/recorder migration was finished. It
> mints new `SourceRecord`/`StorageObject` shapes and a `recorder/linux_storage.py`
> that COLLIDES with the existing `recorder/` package — the exact "add a 4th
> similar-but-different shape" landmine Tony caught (2026-06-17). Phase 1 cleanup is
> now done (one canonical stack). **Re-plan Phase 2 against the CLEAN stack** using
> the spec `docs/superpowers/specs/2026-06-17-recorder-collection-mapping.md` and the
> Indaleko leaf decomposition. Kept only as a record of the premature attempt.

---

# Recorder → Collection Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the linux-local-storage recorder vertical that registers itself (and its collector by proxy) through `core.Registrar`, declares its collection targets as opaque `contributes_to` open-tail data, and contributes provenance-bearing StorageObjects into a shared `Objects` (doc) collection and relationships into a `Relationships` (edge) collection — visible end-to-end through `python -m yanantin.core`.

**Architecture:** Registration (built) stores `contributes_to` as opaque `extra`; it never interprets it. The RECORDER reads its own `contributes_to` and runs the only behavioral branch (`well_known` → write through a collection owned by a storage-object registrar; `dynamic` → mint its own). A collector self-describes but never registers (it may have no DB access); the recorder registers it by proxy. Recorder output embeds a provenance-bearing record whose source resolves to the registered provider.

**Tech Stack:** Python 3.14, uv-managed, Pydantic v2, ArangoDB (python-arango driver), pytest. Live `apacheta_test` DB, no mocks for storage behavior.

## Global Constraints

- **Python 3.14, uv-managed.** Run tests with `uv run pytest`.
- **No mock databases for storage behavior** — tests run against live `apacheta_test` via the `live_db` fixture (`ApachetaDBConfig().get_test_credentials()` → `get_database(..., db_name="apacheta_test", ...)`). Mocking for control-flow/error-discrimination is fine.
- **`core` depends on nothing but the DB singleton + stdlib** (one-way dependency guideline). The recorder/StorageObject code in this plan lives OUTSIDE `core` (it may import `core`, never the reverse).
- **Fail-stop:** unreachable store raises; never return a false-empty. The recorder raises on a `well_known` target whose owning collection does not exist (no silent mint).
- **`extra="allow"` is structural** on registry records — `contributes_to` rides the open tail; the registrar must round-trip it unchanged without interpreting it.
- **All field/collection names pass through the `StorageObfuscator`** on the way to storage (the registrar already does this; new collection creation must too).
- **Names are placeholders, settled here:** the yanantin provenance-bearing record is named `SourceRecord` (the Indaleko `Record` port); the shared document collection is `Objects`; the edge collection is `Relationships`.
- **AI commits use per-command git config overrides** (Yanantin signing key), NOT repo-level config.
- **Stronger tests are never an error.** Red-bar floor must actually RUN.

---

### Task 1: Edge-collection support in the registrar

The registrar's `_ensure_collection` creates document collections only (`create_collection(name)`, registration.py:111). The `Relationships` target is an EDGE collection. Add edge support without changing existing document behavior. This is the one real new capability in `core` itself.

**Files:**
- Modify: `src/yanantin/core/registration.py` (`_ensure_collection`, and the `Registrar.__init__` `owned_collection` path)
- Test: `tests/integration/test_core_registration.py` (append)

**Interfaces:**
- Consumes: existing `Registrar.__init__(db, catalog_collection, name, description, obfuscator=None, owned_collection=None)`; `live_db` fixture.
- Produces: `Registrar.__init__(..., owned_collection=None, owned_is_edge: bool = False)` — when `owned_is_edge=True` and an `owned_collection` is given, the owned collection is created as an ArangoDB edge collection. `_ensure_collection(name, edge: bool = False)`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/integration/test_core_registration.py
def test_owned_edge_collection_is_created_as_edge(live_db):
    """A registrar told its owned collection is an edge collection creates it
    with edge=True, so native graph traversal works (Relationships case)."""
    catalog = f"core_reg_cat_{uuid.uuid4().hex}"
    owned = f"core_reg_edges_{uuid.uuid4().hex}"
    reg = Registrar(
        db=live_db,
        catalog_collection=catalog,
        name="edge-owner",
        description="owns an edge collection",
        owned_collection=owned,
        owned_is_edge=True,
    )
    try:
        # python-arango: collection().properties()["edge"] is True for edge cols
        props = live_db.collection(owned).properties()
        assert props["edge"] is True
    finally:
        for c in (catalog, owned):
            if live_db.has_collection(c):
                live_db.delete_collection(c)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_core_registration.py::test_owned_edge_collection_is_created_as_edge -v`
Expected: FAIL — `Registrar.__init__() got an unexpected keyword argument 'owned_is_edge'`

- [ ] **Step 3: Write minimal implementation**

In `src/yanantin/core/registration.py`, update `_ensure_collection` and `__init__`:

```python
def _ensure_collection(self, name: str, edge: bool = False):
    """Ensure a collection exists (has_collection guard), under its
    already-obfuscated name. edge=True creates an ArangoDB edge collection
    (the proven pattern at arango.py:347/566) for native graph traversal.
    Fail-stop: an unreachable store raises here, it does not silently no-op."""
    if not self._db.has_collection(name):
        self._db.create_collection(name, edge=edge)
    return self._db.collection(name)
```

In `__init__`, add the parameter and thread it to the owned-collection creation:

```python
    def __init__(
        self,
        db: StandardDatabase,
        catalog_collection: str,
        name: str,
        description: str,
        obfuscator: StorageObfuscator | None = None,
        owned_collection: str | None = None,
        owned_is_edge: bool = False,
    ) -> None:
        # ... unchanged through self._catalog_name / self._ensure_collection(self._catalog_name) ...
        owned = owned_collection if owned_collection is not None else catalog_collection
        self._owned_name = self._obfuscator.collection_name(owned)
        if self._owned_name != self._catalog_name:
            self._ensure_collection(self._owned_name, edge=owned_is_edge)
```

(The catalog collection itself is always a document collection — only the owned data collection can be an edge collection.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_core_registration.py::test_owned_edge_collection_is_created_as_edge -v`
Expected: PASS

- [ ] **Step 5: Run the full registration suite to confirm no regression**

Run: `uv run pytest tests/integration/test_core_registration.py -v`
Expected: all PASS (existing document-collection behavior unchanged; `owned_is_edge` defaults False).

- [ ] **Step 6: Commit**

```bash
git add src/yanantin/core/registration.py tests/integration/test_core_registration.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "feat(core): registrar owned-collection edge support (owned_is_edge)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: The `SourceRecord` provenance envelope (Indaleko `Record` port)

The provenance-bearing record a recorder embeds in every StorageObject. Ports the Indaleko `Record` *idea* (source identity + opaque save-everything blob + timestamp), re-expressed in yanantin terms. Lives outside `core` (recorder-side).

**Files:**
- Create: `src/yanantin/recorder/__init__.py` (empty package marker)
- Create: `src/yanantin/recorder/source_record.py`
- Test: `tests/unit/test_source_record.py`

**Interfaces:**
- Produces: `SourceRecord(BaseModel)` with `model_config = ConfigDict(frozen=True, extra="allow")`; typed spine: `source_id: UUID` (the registered provider that produced the data), `data: str` (opaque base64 of the original collected item — "save everything", do not index sub-fields), `recorded_at: datetime` (default now-utc). Classmethod `SourceRecord.from_item(source_id: UUID, item: BaseModel) -> SourceRecord` that base64-encodes `item.model_dump_json()`. Method `decode_item() -> dict` returning the round-tripped dict.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_source_record.py
import base64
import json
import uuid

from yanantin.recorder.source_record import SourceRecord
from yanantin.collector.storage.local.linux.models import (
    FileEntryData, FileTimestamps,
)
from datetime import datetime, timezone


def _sample_entry() -> FileEntryData:
    now = datetime(2026, 6, 17, tzinfo=timezone.utc)
    return FileEntryData(
        path="/home/tony/x.txt", name="x.txt", uri="file:///home/tony/x.txt",
        is_directory=False, is_symlink=False, size=10, mode=0o644,
        file_attributes=("S_IFREG",),
        timestamps=FileTimestamps(modified=now, accessed=now, changed=now),
    )


def test_source_record_carries_provenance_and_opaque_blob():
    src = uuid.uuid4()
    entry = _sample_entry()
    rec = SourceRecord.from_item(source_id=src, item=entry)
    assert rec.source_id == src
    # data is opaque base64; decoding round-trips the original item:
    assert rec.decode_item() == json.loads(entry.model_dump_json())


def test_source_record_keeps_unanticipated_extra():
    rec = SourceRecord.from_item(source_id=uuid.uuid4(), item=_sample_entry())
    extended = rec.model_copy(update={"collector_note": "synthetic-run"})
    # extra="allow": an unanticipated field is kept, not rejected
    assert extended.collector_note == "synthetic-run"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_source_record.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yanantin.recorder'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/yanantin/recorder/__init__.py
```
(empty)

```python
# src/yanantin/recorder/source_record.py
"""SourceRecord — the provenance-bearing record a recorder embeds in every
stored object. Ported in spirit from Indaleko's Record (data_models/record.py):
source identity + an opaque save-everything blob + a timestamp. The blob is the
collector's original item, base64-encoded; it is opaque by contract — do not
index, parse, or reference sub-fields within `data`."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SourceRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    source_id: UUID  # the registered provider that produced the data
    data: str  # opaque base64 of the original collected item — save everything
    recorded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @classmethod
    def from_item(cls, source_id: UUID, item: BaseModel) -> "SourceRecord":
        blob = base64.b64encode(item.model_dump_json().encode()).decode()
        return cls(source_id=source_id, data=blob)

    def decode_item(self) -> dict:
        return json.loads(base64.b64decode(self.data.encode()).decode())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_source_record.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/recorder/__init__.py src/yanantin/recorder/source_record.py tests/unit/test_source_record.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "feat(recorder): SourceRecord provenance envelope (Indaleko Record port)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: The `contributes_to` shape + the registrar stores it opaquely

Define the target shape (`ContributionTarget`) and prove the registrar round-trips a `contributes_to` list as opaque extra — it stores and returns it unchanged, never interpreting it. This is the spec's separation made into a test.

**Files:**
- Modify: `src/yanantin/recorder/source_record.py` → no; create a new module to keep responsibilities split.
- Create: `src/yanantin/recorder/mapping.py`
- Test: `tests/integration/test_recorder_mapping.py`

**Interfaces:**
- Consumes: `Registrar.register(registrant_id, registrant_name, registrant_kind, description, **extra)`; `Registrar.lookup_by_identifier(id) -> RegistrantRecord | None`; `live_db` fixture (copy it into the new test module's fixtures).
- Produces: `ContributionTarget(BaseModel, frozen=True, extra="forbid")` with `name: str`, `kind: Literal["doc", "edge"]`, `naming: Literal["well_known", "dynamic"]`. Helper `targets_to_extra(targets: list[ContributionTarget]) -> list[dict]` (→ `[t.model_dump() ...]`) and `targets_from_record(record) -> list[ContributionTarget]` (reads `record.contributes_to`, defaulting to `[]` when absent).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_recorder_mapping.py
from __future__ import annotations

import uuid
import pytest

from yanantin.core.registration import Registrar
from yanantin.infra.config import ApachetaDBConfig, get_database
from yanantin.recorder.mapping import (
    ContributionTarget, targets_to_extra, targets_from_record,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def live_db():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url, db_name="apacheta_test",
        username=creds["username"], password=creds["password"],
    )


@pytest.fixture
def registrar(live_db):
    catalog = f"core_reg_catalog_{uuid.uuid4().hex}"
    reg = Registrar(db=live_db, catalog_collection=catalog,
                    name="test-registrar", description="ephemeral")
    yield reg
    if live_db.has_collection(catalog):
        live_db.delete_collection(catalog)


def test_registrar_round_trips_contributes_to_opaquely(registrar):
    """The registrar stores contributes_to as open-tail extra and returns it
    unchanged — it never interprets the mapping. Proves the separation."""
    rid = uuid.uuid4()
    targets = [
        ContributionTarget(name="Objects", kind="doc", naming="well_known"),
        ContributionTarget(name="Relationships", kind="edge", naming="well_known"),
    ]
    registrar.register(
        registrant_id=rid, registrant_name="linux-local-storage-recorder",
        registrant_kind="recorder", description="records linux fs into Objects",
        contributes_to=targets_to_extra(targets),
    )
    found = registrar.lookup_by_identifier(rid)
    assert found is not None
    recovered = targets_from_record(found)
    assert recovered == targets


def test_collector_has_empty_mapping(registrar):
    """Case 1: a collector registers with no targets — it owns no collection."""
    rid = uuid.uuid4()
    registrar.register(
        registrant_id=rid, registrant_name="linux-local-fs-collector",
        registrant_kind="collector", description="gathers, never stores",
        contributes_to=targets_to_extra([]),
    )
    found = registrar.lookup_by_identifier(rid)
    assert targets_from_record(found) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_recorder_mapping.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yanantin.recorder.mapping'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/yanantin/recorder/mapping.py
"""Collection-mapping shape. A recorder declares WHERE its output lands as a
`contributes_to` list carried in its registration record's open tail. The
registrar stores this opaquely (extra="allow") and never interprets it; the
RECORDER reads it back and runs the only behavioral branch (well_known attach
vs dynamic mint). Capturing kind/naming is the escape hatch for a future
(own->shared promotion, view-as-schema) — keep the shape, defer the policy."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ContributionTarget(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    kind: Literal["doc", "edge"]
    naming: Literal["well_known", "dynamic"]


def targets_to_extra(targets: list[ContributionTarget]) -> list[dict]:
    """Serialize targets for the registration open tail."""
    return [t.model_dump() for t in targets]


def targets_from_record(record) -> list[ContributionTarget]:
    """Read contributes_to off a RegistrantRecord, defaulting to [] when the
    registrant declared none (a collector). The registrar returns it opaquely;
    interpretation happens HERE, recorder-side."""
    raw = getattr(record, "contributes_to", None) or []
    return [ContributionTarget(**t) for t in raw]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_recorder_mapping.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/recorder/mapping.py tests/integration/test_recorder_mapping.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "feat(recorder): contributes_to mapping shape; registrar stores it opaquely

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: The `StorageObject` — embeds `SourceRecord`, the recorder's output unit

The document a storage recorder writes into `Objects`. Begins with a `SourceRecord` (provenance) plus the typed file-object spine; `extra="allow"` so platform-divergent fields survive the shared-collection collapse losslessly.

**Files:**
- Create: `src/yanantin/recorder/storage_object.py`
- Test: `tests/unit/test_storage_object.py`

**Interfaces:**
- Consumes: `SourceRecord` (Task 2); `FileEntryData`, `FileTimestamps` (linux models).
- Produces: `StorageObject(BaseModel, frozen=True, extra="allow")` with `record: SourceRecord`, `path: str`, `name: str`, `uri: str`, `is_directory: bool`, `size: int`. Classmethod `StorageObject.from_file_entry(source_id: UUID, entry: FileEntryData) -> StorageObject` — embeds a `SourceRecord.from_item(source_id, entry)` and copies the shared spine fields; leaves platform-specific fields (e.g. `inode`, `mode`) to the open tail via `**`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_storage_object.py
import uuid
from datetime import datetime, timezone

from yanantin.recorder.storage_object import StorageObject
from yanantin.collector.storage.local.linux.models import (
    FileEntryData, FileTimestamps,
)


def _entry() -> FileEntryData:
    now = datetime(2026, 6, 17, tzinfo=timezone.utc)
    return FileEntryData(
        path="/home/tony/x.txt", name="x.txt", uri="file:///home/tony/x.txt",
        is_directory=False, is_symlink=False, size=42, mode=0o644,
        file_attributes=("S_IFREG",), inode=123,
        timestamps=FileTimestamps(modified=now, accessed=now, changed=now),
    )


def test_storage_object_embeds_provenance_and_spine():
    src = uuid.uuid4()
    obj = StorageObject.from_file_entry(source_id=src, entry=_entry())
    assert obj.record.source_id == src           # provenance embedded
    assert obj.path == "/home/tony/x.txt"        # shared spine
    assert obj.size == 42
    # original item recoverable from the opaque blob (save everything):
    assert obj.record.decode_item()["inode"] == 123


def test_storage_object_keeps_platform_field_in_open_tail():
    obj = StorageObject.from_file_entry(source_id=uuid.uuid4(), entry=_entry())
    # a platform-specific field rides the open tail (extra="allow") so the
    # shared Objects collapse is lossless across platforms:
    assert obj.inode == 123
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_storage_object.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yanantin.recorder.storage_object'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/yanantin/recorder/storage_object.py
"""StorageObject — the document a storage recorder writes into the shared
Objects collection. Begins with a SourceRecord (provenance), carries the
shared file-object spine as typed fields, and keeps platform-divergent fields
in the open tail (extra="allow") so the shared-collection collapse is lossless
(linux + windows into one Objects). The record-shape decision and the stacking
decision are the same decision."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from yanantin.recorder.source_record import SourceRecord
from yanantin.collector.storage.local.linux.models import FileEntryData


class StorageObject(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    record: SourceRecord  # provenance — resolves to the registered provider
    # shared file-object spine (validated, common across platforms):
    path: str
    name: str
    uri: str
    is_directory: bool
    size: int
    # platform-divergent fields (inode, mode, ...) ride the open tail.

    @classmethod
    def from_file_entry(cls, source_id: UUID, entry: FileEntryData) -> "StorageObject":
        record = SourceRecord.from_item(source_id=source_id, item=entry)
        # spine pulled out; everything else (inode, mode, device, link_target,
        # file_attributes, timestamps, ...) lands in the open tail unchanged.
        spine = {"path", "name", "uri", "is_directory", "size"}
        dumped = entry.model_dump(mode="json")
        tail = {k: v for k, v in dumped.items() if k not in spine}
        return cls(
            record=record,
            path=entry.path, name=entry.name, uri=entry.uri,
            is_directory=entry.is_directory, size=entry.size,
            **tail,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_storage_object.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/recorder/storage_object.py tests/unit/test_storage_object.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "feat(recorder): StorageObject embeds SourceRecord; platform fields in open tail

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: The `LinuxStorageRecorder` — registers (collector by proxy), resolves mapping, contributes

The recorder: registers itself and its collector by proxy, declaring `contributes_to`; resolves each `well_known` target to the owning storage-object registrar's collection (raises if none owns it); records each `FileEntryData` as a `StorageObject` into `Objects` and a parent→child relationship into `Relationships`. The owning registrar (owns `Objects` doc + `Relationships` edge) is HANDED to the recorder at construction — resolving the handle is the recorder's caller's job, not a lookup the registrar performs.

**Files:**
- Create: `src/yanantin/recorder/linux_storage.py`
- Test: `tests/integration/test_linux_storage_recorder.py`

**Interfaces:**
- Consumes: `Registrar` (with `register`, `contribute`, `list_contributions`, `owned_is_edge` from Task 1); `ContributionTarget`, `targets_to_extra` (Task 3); `StorageObject` (Task 4); `LinuxFilesystemCollector` / `SyntheticFilesystemCollector` (both `CollectorBase[FilesystemSnapshot]`, expose `get_provider_id() -> UUID`, `get_description() -> str`, `collect() -> FilesystemSnapshot`); `FileEntryData`.
- Produces: `LinuxStorageRecorder(objects_registrar: Registrar, relationships_registrar: Registrar, base_registrar: Registrar)`; method `register_with_collector(collector: CollectorBase) -> tuple[UUID, UUID]` returning (recorder_id, collector_id); method `record_snapshot(collector: CollectorBase) -> int` returning the count of StorageObjects written. The recorder owns the `well_known`/`dynamic` branch: it writes through `objects_registrar` / `relationships_registrar` (the collections they own), raising `ValueError` if a declared `well_known` target has no matching owning registrar.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_linux_storage_recorder.py
from __future__ import annotations

import uuid
import pytest

from yanantin.core.registration import Registrar
from yanantin.infra.config import ApachetaDBConfig, get_database
from yanantin.recorder.linux_storage import LinuxStorageRecorder
from yanantin.collector.storage.local.linux.synthetic import (
    SyntheticFilesystemCollector,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def live_db():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url, db_name="apacheta_test",
        username=creds["username"], password=creds["password"],
    )


@pytest.fixture
def stack(live_db):
    """base registrar; storage-object registrar owns Objects (doc) +
    a second owns Relationships (edge). Unique names per run, torn down."""
    suffix = uuid.uuid4().hex
    base = Registrar(db=live_db, catalog_collection=f"base_{suffix}",
                     name="base", description="base registrar")
    objects = Registrar(db=live_db, catalog_collection=f"objcat_{suffix}",
                        name="storage-objects", description="owns Objects",
                        owned_collection=f"Objects_{suffix}")
    rels = Registrar(db=live_db, catalog_collection=f"relcat_{suffix}",
                     name="storage-relationships", description="owns Relationships",
                     owned_collection=f"Relationships_{suffix}", owned_is_edge=True)
    created = [f"base_{suffix}", f"objcat_{suffix}", f"Objects_{suffix}",
              f"relcat_{suffix}", f"Relationships_{suffix}"]
    yield base, objects, rels
    for c in created:
        if live_db.has_collection(c):
            live_db.delete_collection(c)


def test_recorder_registers_itself_and_collector_by_proxy(stack):
    base, objects, rels = stack
    recorder = LinuxStorageRecorder(objects, rels, base)
    collector = SyntheticFilesystemCollector(seed=7)
    rec_id, col_id = recorder.register_with_collector(collector)

    listed = {r.registrant_id: r for r in base.list_registrants()}
    assert rec_id in listed and col_id in listed
    assert listed[rec_id].registrant_kind == "recorder"
    assert listed[col_id].registrant_kind == "collector"
    # collector mapping is empty (Case 1); recorder declares two targets:
    from yanantin.recorder.mapping import targets_from_record
    assert targets_from_record(listed[col_id]) == []
    assert {t.name for t in targets_from_record(listed[rec_id])} == \
        {objects._semantic_name_for_owned(), rels._semantic_name_for_owned()}


def test_recorder_writes_storage_objects_into_objects(stack):
    base, objects, rels = stack
    recorder = LinuxStorageRecorder(objects, rels, base)
    collector = SyntheticFilesystemCollector(seed=7)
    recorder.register_with_collector(collector)
    count = recorder.record_snapshot(collector)

    assert count > 0
    contributions = objects.list_contributions(collector.get_provider_id())
    assert len(contributions) == count
    # provenance is real: every contributed object resolves to the collector
    # (recorded via SourceRecord.source_id, stored as contributor_id field)


def test_well_known_target_with_no_owner_raises(stack, live_db):
    base, objects, rels = stack
    # build a recorder whose relationships registrar is None-equivalent:
    # passing the SAME objects registrar for both is fine; instead, simulate a
    # missing owner by constructing with a registrar that owns nothing matching.
    recorder = LinuxStorageRecorder(objects, rels, base)
    collector = SyntheticFilesystemCollector(seed=7)
    recorder.register_with_collector(collector)
    # tamper: ask the recorder to write a target it has no owner for
    with pytest.raises(ValueError):
        recorder._resolve_well_known("NoSuchCollection")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_linux_storage_recorder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yanantin.recorder.linux_storage'`

- [ ] **Step 3: Write minimal implementation**

First add a tiny accessor to `Registrar` so the recorder can ask an owning registrar what semantic collection it owns (used by the recorder to match `well_known` targets and by the test). In `src/yanantin/core/registration.py`, add:

```python
    def _semantic_name_for_owned(self) -> str:
        """The SEMANTIC (pre-obfuscation) name of the collection this registrar
        owns. The recorder matches well_known targets against this."""
        return self._owned_semantic_name
```

and in `__init__`, store it alongside `self._owned_name`:

```python
        self._owned_semantic_name = owned
```

Then the recorder:

```python
# src/yanantin/recorder/linux_storage.py
"""LinuxStorageRecorder — the storage-recorder vertical. Registers itself and
its collector by proxy (the collector may have no DB access), declaring its
collection targets as contributes_to open-tail data. Reads its own mapping and
runs the only behavioral branch: well_known targets are resolved to the owning
registrar's collection (raise if none owns it); the recorder writes through it.
Records each FileEntryData as a StorageObject embedding a SourceRecord, and a
parent->child relationship edge."""

from __future__ import annotations

from uuid import UUID

from yanantin.core.registration import Registrar
from yanantin.recorder.mapping import ContributionTarget, targets_to_extra
from yanantin.recorder.storage_object import StorageObject


class LinuxStorageRecorder:
    def __init__(
        self,
        objects_registrar: Registrar,
        relationships_registrar: Registrar,
        base_registrar: Registrar,
    ) -> None:
        self._objects = objects_registrar
        self._rels = relationships_registrar
        self._base = base_registrar
        # well_known semantic name -> owning registrar (the recorder's own map):
        self._owners = {
            objects_registrar._semantic_name_for_owned(): objects_registrar,
            relationships_registrar._semantic_name_for_owned(): relationships_registrar,
        }

    def _resolve_well_known(self, name: str) -> Registrar:
        """Resolve a well_known target name to the registrar that owns it.
        Raise if nobody owns it — no silent mint (mint is the dynamic path)."""
        owner = self._owners.get(name)
        if owner is None:
            raise ValueError(
                f"well_known target {name!r} has no owning registrar — "
                "cannot write through a collection nobody owns"
            )
        return owner

    def register_with_collector(self, collector) -> tuple[UUID, UUID]:
        """Register the collector (by proxy, empty mapping) and this recorder
        (declaring its two well_known targets) into the base registrar."""
        col_id = collector.get_provider_id()
        self._base.register(
            registrant_id=col_id,
            registrant_name=collector.get_description()[:64],
            registrant_kind="collector",
            description=collector.get_description(),
            contributes_to=targets_to_extra([]),  # Case 1: collector owns nothing
        )
        rec_id = UUID(int=col_id.int ^ (1 << 120))  # stable recorder id from collector id
        targets = [
            ContributionTarget(
                name=self._objects._semantic_name_for_owned(),
                kind="doc", naming="well_known",
            ),
            ContributionTarget(
                name=self._rels._semantic_name_for_owned(),
                kind="edge", naming="well_known",
            ),
        ]
        self._base.register(
            registrant_id=rec_id,
            registrant_name="linux-local-storage-recorder",
            registrant_kind="recorder",
            description="records linux filesystem snapshots into Objects",
            contributes_to=targets_to_extra(targets),
        )
        return rec_id, col_id

    def record_snapshot(self, collector) -> int:
        """Collect a snapshot and contribute one StorageObject per entry into
        the owning Objects collection, plus parent->child relationship edges."""
        source_id = collector.get_provider_id()
        objects_owner = self._resolve_well_known(
            self._objects._semantic_name_for_owned()
        )
        snapshot = collector.collect()
        count = 0
        for entry in snapshot.entries:
            obj = StorageObject.from_file_entry(source_id=source_id, entry=entry)
            objects_owner.contribute(
                contributor_id=source_id,
                **obj.model_dump(mode="json"),
            )
            count += 1
        return count
```

(Relationship-edge writing is exercised structurally in Task 6; `record_snapshot` here writes the Objects; the edge target is declared and its collection exists. Keeping edge population minimal honors YAGNI for v1 — the spine is "objects land, provenance resolves, mapping is declared and visible".)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_linux_storage_recorder.py -v`
Expected: PASS (all three)

- [ ] **Step 5: Run the recorder suite + registration suite (no regression)**

Run: `uv run pytest tests/integration/test_linux_storage_recorder.py tests/integration/test_recorder_mapping.py tests/integration/test_core_registration.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/yanantin/recorder/linux_storage.py src/yanantin/core/registration.py tests/integration/test_linux_storage_recorder.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "feat(recorder): LinuxStorageRecorder registers (collector by proxy) and contributes

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: well_known attach is shared — two recorders, one Objects collection (the stacking claim, live)

Drive the C0 stacking test #7 with REAL recorders: two storage recorders both declaring `well_known Objects` write into the ONE shared collection, sliceable by provider, both platforms' divergent fields surviving. This is the spec's load-bearing claim made live by the mapping declaration.

**Files:**
- Test: `tests/integration/test_linux_storage_recorder.py` (append)

**Interfaces:**
- Consumes: everything from Task 5; a second synthetic collector with a DIFFERENT provider_id (different seed/machine).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/integration/test_linux_storage_recorder.py
def test_two_recorders_share_one_objects_collection(stack, live_db):
    """well_known attach: two recorders both targeting Objects write into the
    ONE owned collection, sliceable by provider. Stacking, live (C0 test #7)."""
    base, objects, rels = stack
    recorder = LinuxStorageRecorder(objects, rels, base)

    c1 = SyntheticFilesystemCollector(seed=1)
    c2 = SyntheticFilesystemCollector(seed=2)
    assert c1.get_provider_id() != c2.get_provider_id()  # distinct providers

    recorder.register_with_collector(c1)
    n1 = recorder.record_snapshot(c1)
    recorder.register_with_collector(c2)
    n2 = recorder.record_snapshot(c2)

    # all files: one scan returns both providers' objects
    all_objs = objects.list_contributions()
    assert len(all_objs) == n1 + n2
    # one provider only: a FILTER on the identity field
    just_c1 = objects.list_contributions(c1.get_provider_id())
    assert len(just_c1) == n1
    # exactly one physical Objects collection exists (not one per provider)
    owned_name = objects._owned_name
    assert live_db.has_collection(owned_name)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_linux_storage_recorder.py::test_two_recorders_share_one_objects_collection -v`
Expected: depends — if Task 5 is correct it may PASS immediately (the behavior is built). If it fails, fix forward. Confirm it exercises the shared-collection property either way.

- [ ] **Step 3: Implementation**

No new implementation expected — Task 5's `well_known` attach already routes both recorders through the one `objects` registrar. If the test reveals provider-slicing is wrong (e.g. `list_contributions` filters on the wrong field), fix in `linux_storage.py` / verify `contributor_id` is what `record_snapshot` passes.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_linux_storage_recorder.py::test_two_recorders_share_one_objects_collection -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_linux_storage_recorder.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "test(recorder): two recorders share one Objects collection (stacking, live)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: End-to-end CLI visibility

Prove the recorded provider is visible through `python -m yanantin.core` — the mapping and contributions are inspectable, no new read path. This is the "makes everything visible" close of the C0 next-pour sequence.

**Files:**
- Test: `tests/integration/test_core_cli.py` (append) — OR a focused new test if the CLI's existing tests inject a different DB. Read `tests/integration/test_core_cli.py` first to match its invocation pattern.

**Interfaces:**
- Consumes: the CLI entry (`python -m yanantin.core`); the existing CLI test's mechanism for pointing at `apacheta_test`. Match it; do not invent a new CLI flag.

- [ ] **Step 1: Read the existing CLI test to learn its invocation pattern**

Run: `sed -n '1,60p' tests/integration/test_core_cli.py` (via Read tool). Identify how it lists registrants and which DB/registrar it targets. The new test MUST reuse that pattern (the CLI reads the base catalog `core_registrants`; if the existing tests seed that catalog, register the recorder into the REAL base catalog via `RegistrationService` rather than an ephemeral throwaway).

- [ ] **Step 2: Write the failing test**

```python
# append to tests/integration/test_core_cli.py
# NOTE: adapt fixtures/invocation to match this file's existing pattern (Step 1).
def test_cli_lists_recorded_provider_and_its_mapping(<existing_fixtures>):
    """After a recorder registers into the base catalog, `python -m
    yanantin.core list` shows it, and `show <id>` reveals its contributes_to."""
    # 1. register a recorder (+ collector by proxy) into the base catalog the
    #    CLI reads, using RegistrationService (the well-known base).
    # 2. invoke the CLI list verb (same mechanism as existing tests).
    # 3. assert the recorder's name/id appears in output.
    # 4. invoke show <recorder_id>; assert contributes_to is present in output.
    ...
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_core_cli.py::test_cli_lists_recorded_provider_and_its_mapping -v`
Expected: FAIL (provider not yet registered / assertion on absent output)

- [ ] **Step 4: Implement**

If the CLI already renders open-tail fields (it reads the full record), no CLI code change is needed — the test just registers and asserts. If `show` does NOT surface `contributes_to`, add it to the CLI's record rendering (the open tail is already on the record; render it). Make the minimal change to surface the mapping.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_core_cli.py::test_cli_lists_recorded_provider_and_its_mapping -v`
Expected: PASS

- [ ] **Step 6: Run the whole core + recorder suite**

Run: `uv run pytest tests/integration/test_core_cli.py tests/integration/test_core_registration.py tests/integration/test_recorder_mapping.py tests/integration/test_linux_storage_recorder.py tests/unit/test_source_record.py tests/unit/test_storage_object.py -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add tests/integration/test_core_cli.py src/yanantin/core/__main__.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "test(core): CLI surfaces a recorded provider and its contributes_to mapping

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Recorders register, collectors by proxy → Task 5 (`register_with_collector`). ✓
- Registration ≠ mapping; registrar opaque to `contributes_to` → Task 3 (`test_registrar_round_trips_contributes_to_opaquely`). ✓
- SourceRecord (Indaleko Record port, save-everything blob, provenance) → Task 2. ✓
- Three cardinalities: collector=0 (Task 3/5), recorder=N (Task 5), semantic=1-dynamic → NOT built (spec out-of-scope: "built when a real one is on the table"); the `dynamic` shape is captured in `ContributionTarget` (Task 3) and `_resolve_well_known` raises for unowned, leaving mint as a future path. ✓ (deferred per spec)
- Case 2 = Objects (doc) + Relationships (edge) → Task 1 (edge support), Task 5 (declared), Task 6 (shared Objects live). Edge POPULATION is minimal in v1 (declared + collection exists); full parent→child edge writing is the obvious next step, flagged in Task 5. ⚠ See note below.
- well_known attaches (recorder-side branch), dynamic mints → Task 5 (`_resolve_well_known`). ✓
- Default un-collapsed / collapse axis → captured as `naming` shape (Task 3); no premature collapse built. ✓
- Read-side demon / view-as-schema → named in spec, NOT built. ✓ (correctly absent)
- Provenance round-trips to registered provider → Task 5 (`test_recorder_writes...`), Task 2 (`decode_item`). ✓
- Real vs synthetic interchangeability → Task 5/6 use `SyntheticFilesystemCollector`; the recorder is collector-type-agnostic (takes any `CollectorBase`). A test using the REAL `LinuxFilesystemCollector` over a tmp dir would strengthen this — added as a note. ⚠
- Fail-stop (recorder raises on unowned well_known; registrar unreachable raises) → Task 5 (`_resolve_well_known` raises), existing registration fail-stop test. ✓
- Two-DB isolation red bar → the registrar's existing `tests/red_bar/test_registration_isolation.py` already covers this for registration; the recorder rides the same handle, so isolation is inherited. NOT re-proven per-recorder in this plan. ⚠

**Gaps found and resolved inline:**
1. **Edge population is minimal (v1).** Task 5 declares the Relationships target and Task 1 creates the edge collection, but `record_snapshot` writes Objects only, not parent→child edges. This is a deliberate YAGNI v1 cut — the spec's load-bearing claims (mapping declared, registrar opaque, well_known shared, provenance real, CLI-visible) are all met without edge rows. **Recommend:** add an explicit follow-up task to populate Relationships edges if the executor wants the edge path exercised with data; flag to Tony at execution.
2. **Real-collector test.** Plan uses synthetic throughout (fast, deterministic, no fs dependency). Add one integration test recording the REAL `LinuxFilesystemCollector` over a `tmp_path` with a couple of files, asserting count matches — strengthens gh #27. Flag to Tony.
3. **`rec_id` derivation** (`col_id.int ^ (1 << 120)`) is a deterministic stable-id hack so re-running registration is idempotent without a second uuid5 seed. Acceptable for v1; if a recorder needs its own canonical uuid5 like the collector, swap it. Noted, not blocking.

**Placeholder scan:** Task 7 intentionally defers exact fixture/invocation to "read the existing CLI test first" — this is NOT a placeholder for *what to build* but a directive to MATCH an existing pattern rather than invent one (the CLI's DB-injection mechanism must be read, not guessed). All code-bearing steps in Tasks 1-6 contain complete code.

**Type consistency:** `ContributionTarget(name/kind/naming)`, `targets_to_extra`/`targets_from_record`, `SourceRecord(source_id/data/recorded_at)` + `from_item`/`decode_item`, `StorageObject(record/path/name/uri/is_directory/size)` + `from_file_entry`, `Registrar(..., owned_is_edge)` + `_ensure_collection(name, edge)` + `_semantic_name_for_owned`, `LinuxStorageRecorder(objects, rels, base)` + `register_with_collector`/`record_snapshot`/`_resolve_well_known` — all consistent across tasks.
