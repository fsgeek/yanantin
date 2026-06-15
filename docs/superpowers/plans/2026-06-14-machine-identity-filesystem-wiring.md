# Machine Identity + Filesystem Collector Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record machines as persistent `EntityResolution` entities in ArangoDB, wire `LinuxFilesystemCollector` to use a stable `machine_id`, and have `FilesystemFactRecorder` write `provenance_edges` (machine→fact, collector→fact) for every file entry it stores.

**Architecture:** A new `ProvenanceEdge` model (local to yanantin, not in tiksi) carries native ArangoDB `_from`/`_to` edge fields and lives in a new `provenance_edges` collection. `MachineConfigRecorder` is extended to write an `EntityResolution` (keyed by `machine_id`) before writing its tensor. `FilesystemFactRecorder` gains an `ApachetaInterface` dependency and writes two edges per fact.

**Tech Stack:** Python 3.14, Pydantic v2, ArangoDB via python-arango, pytest, uv. All tests run via `python -m pytest`. Integration tests hit `apacheta_test` DB.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/yanantin/apacheta/models/provenance_edge.py` | **Create** | `ProvenanceEdge` model with `_from`/`_to` ArangoDB edge fields |
| `src/yanantin/apacheta/models/__init__.py` | **Modify** | re-export `ProvenanceEdge` |
| `src/yanantin/apacheta/interface/abstract.py` | **Modify** | add `store_provenance_edge` abstract method |
| `src/yanantin/apacheta/backends/memory.py` | **Modify** | implement `store_provenance_edge` in-memory |
| `src/yanantin/apacheta/backends/arango.py` | **Modify** | implement `store_provenance_edge` with native edge insert |
| `src/yanantin/apacheta/backends/duckdb.py` | **Modify** | stub `store_provenance_edge` (raises `NotImplementedError`) |
| `src/yanantin/machine/linux.py` | **Modify** | `MachineConfigRecorder.record()` writes `EntityResolution` (upsert) + `has_snapshot` edge |
| `src/yanantin/collector/storage/local/linux/collector.py` | **Modify** | `LinuxFilesystemCollector.__init__` accepts `machine_id: str \| None = None` |
| `src/yanantin/recorder/storage/local/linux/fact_recorder.py` | **Modify** | `FilesystemFactRecorder.__init__` accepts `ApachetaInterface`; writes two edges per fact |
| `tests/unit/test_machine_identity.py` | **Create** | `EntityResolution` shape, `machine_id` as `entity.id`, idempotent upsert |
| `tests/unit/test_provenance_edge.py` | **Create** | `ProvenanceEdge` model validation, `store_provenance_edge` in-memory |
| `tests/unit/test_filesystem_edges.py` | **Create** | two edges per fact, correct `_from`/`_to`/`relation_type` |
| `tests/integration/test_machine_and_edges.py` | **Create** | full pipeline against `apacheta_test`: entity + tensor + edges present |

---

## Task 1: ProvenanceEdge model

**Files:**
- Create: `src/yanantin/apacheta/models/provenance_edge.py`
- Modify: `src/yanantin/apacheta/models/__init__.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_provenance_edge.py`:

```python
"""Tests for ProvenanceEdge model."""
from uuid import uuid4
import pytest
from yanantin.apacheta.models.provenance_edge import ProvenanceEdge


def test_provenance_edge_fields():
    edge = ProvenanceEdge(
        _from="entities/abc123",
        _to="records/def456",
        relation_type="contains",
    )
    assert edge._from == "entities/abc123"
    assert edge._to == "records/def456"
    assert edge.relation_type == "contains"
    assert edge.id is not None


def test_provenance_edge_requires_from_and_to():
    with pytest.raises(Exception):
        ProvenanceEdge(relation_type="contains")


def test_provenance_edge_from_must_include_collection():
    with pytest.raises(ValueError, match="must be collection/key"):
        ProvenanceEdge(_from="abc123", _to="records/def456", relation_type="contains")


def test_provenance_edge_to_must_include_collection():
    with pytest.raises(ValueError, match="must be collection/key"):
        ProvenanceEdge(_from="entities/abc123", _to="def456", relation_type="contains")


def test_provenance_edge_frozen():
    edge = ProvenanceEdge(
        _from="entities/abc123",
        _to="records/def456",
        relation_type="contains",
    )
    with pytest.raises(Exception):
        edge.relation_type = "other"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/unit/test_provenance_edge.py -v
```
Expected: `ImportError` — module does not exist yet.

- [ ] **Step 3: Create the model**

Create `src/yanantin/apacheta/models/provenance_edge.py`:

```python
"""ProvenanceEdge — cross-collection directed edge for ArangoDB graph traversal.

CompositionEdge (from tiksi) connects tensors to tensors with a closed
RelationType enum. ProvenanceEdge connects any two collections with a
free-string relation_type, enabling machine→fact and collector→fact edges.

ArangoDB requires native _from and _to fields in the format
"collection/key" for a collection to be traversable as a graph edge.
"""

from __future__ import annotations

from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from yanantin.apacheta.models.provenance import ProvenanceEnvelope


class ProvenanceEdge(BaseModel):
    """A directed edge between any two ArangoDB documents.

    _from and _to use ArangoDB's native edge format: "collection/key".
    The document _key is set to str(id) by the backend's store method.
    relation_type is a free string — no enum — to avoid premature
    vocabulary lock-in.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
        populate_by_name=True,
    )

    id: UUID = Field(default_factory=uuid4)
    from_ref: str = Field(alias="_from")
    to_ref: str = Field(alias="_to")
    relation_type: str
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)

    @model_validator(mode="after")
    def _check_ref_format(self) -> Self:
        for field_name, value in (("_from", self.from_ref), ("_to", self.to_ref)):
            if "/" not in value:
                raise ValueError(
                    f"{field_name}={value!r} must be collection/key format, "
                    "e.g. 'entities/8ae0edf526f3453ab1abaf04e1c75a4a'"
                )
        return self
```

- [ ] **Step 4: Add re-export to models `__init__.py`**

In `src/yanantin/apacheta/models/__init__.py`, add after the existing imports:

```python
from yanantin.apacheta.models.provenance_edge import ProvenanceEdge
```

And add `"ProvenanceEdge"` to `__all__`.

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/unit/test_provenance_edge.py -v
```
Expected: all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/yanantin/apacheta/models/provenance_edge.py \
        src/yanantin/apacheta/models/__init__.py \
        tests/unit/test_provenance_edge.py
git commit -m "feat(models): ProvenanceEdge — cross-collection ArangoDB edge model"
```

---

## Task 2: `store_provenance_edge` on interface and backends

**Files:**
- Modify: `src/yanantin/apacheta/interface/abstract.py`
- Modify: `src/yanantin/apacheta/backends/memory.py`
- Modify: `src/yanantin/apacheta/backends/arango.py`
- Modify: `src/yanantin/apacheta/backends/duckdb.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_provenance_edge.py`:

```python
from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.interface.errors import ImmutabilityError


def test_store_provenance_edge_in_memory():
    backend = InMemoryBackend()
    edge = ProvenanceEdge(
        _from="entities/abc123",
        _to="records/def456",
        relation_type="contains",
    )
    backend.store_provenance_edge(edge)
    edges = backend.list_provenance_edges()
    assert len(edges) == 1
    assert edges[0].relation_type == "contains"


def test_store_provenance_edge_immutable():
    backend = InMemoryBackend()
    edge = ProvenanceEdge(
        _from="entities/abc123",
        _to="records/def456",
        relation_type="contains",
    )
    backend.store_provenance_edge(edge)
    with pytest.raises(ImmutabilityError):
        backend.store_provenance_edge(edge)


def test_list_provenance_edges_empty():
    backend = InMemoryBackend()
    assert backend.list_provenance_edges() == []
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/unit/test_provenance_edge.py::test_store_provenance_edge_in_memory -v
```
Expected: `AttributeError` — method does not exist.

- [ ] **Step 3: Add abstract method to interface**

In `src/yanantin/apacheta/interface/abstract.py`, add import and two abstract methods after `store_entity`:

```python
from yanantin.apacheta.models.provenance_edge import ProvenanceEdge
```

After `store_entity`:

```python
@abstractmethod
def store_provenance_edge(self, edge: ProvenanceEdge) -> None: ...

@abstractmethod
def list_provenance_edges(self) -> list[ProvenanceEdge]: ...
```

- [ ] **Step 4: Implement in InMemoryBackend**

In `src/yanantin/apacheta/backends/memory.py`:

Add import at top:
```python
from yanantin.apacheta.models.provenance_edge import ProvenanceEdge
```

Add to `__init__`:
```python
self._provenance_edges: dict[UUID, ProvenanceEdge] = {}
```

Add methods after `store_entity`:
```python
def store_provenance_edge(self, edge: ProvenanceEdge) -> None:
    with self._lock:
        self._enforce_access("system", "store_provenance_edge", edge.id)
        if edge.id in self._provenance_edges:
            raise ImmutabilityError(f"ProvenanceEdge {edge.id} already exists.")
        self._provenance_edges[edge.id] = self._deep_copy(edge)

def list_provenance_edges(self) -> list[ProvenanceEdge]:
    with self._lock:
        return [self._deep_copy(e) for e in self._provenance_edges.values()]
```

- [ ] **Step 5: Stub in DuckDB backend**

In `src/yanantin/apacheta/backends/duckdb.py`, add after `store_entity`:

```python
def store_provenance_edge(self, edge) -> None:
    raise NotImplementedError("provenance_edges not implemented for DuckDB backend")

def list_provenance_edges(self) -> list:
    raise NotImplementedError("provenance_edges not implemented for DuckDB backend")
```

- [ ] **Step 6: Implement in ArangoDB backend**

In `src/yanantin/apacheta/backends/arango.py`:

Add import at top with other model imports:
```python
from yanantin.apacheta.models.provenance_edge import ProvenanceEdge
```

Add `"provenance_edges"` to the collection list (find where `"composition_edges"` is listed and add alongside it).

Add methods after `store_entity`:
```python
def store_provenance_edge(self, edge: ProvenanceEdge) -> None:
    with self._lock:
        self._enforce_access("system", "store_provenance_edge", edge.id)
        col = self._db.collection("provenance_edges")
        doc = edge.model_dump(mode="json", by_alias=True)
        doc["_key"] = str(doc.pop("id"))
        # _from and _to are already set correctly by by_alias=True
        try:
            col.insert(doc)
        except Exception as e:
            if "unique constraint" in str(e).lower() or "1210" in str(e):
                from yanantin.apacheta.interface.errors import ImmutabilityError
                raise ImmutabilityError(f"ProvenanceEdge {edge.id} already exists.") from e
            raise

def list_provenance_edges(self) -> list[ProvenanceEdge]:
    with self._lock:
        col = self._db.collection("provenance_edges")
        results = []
        for doc in col.all():
            doc["id"] = doc.pop("_key")
            doc.pop("_id", None)
            doc.pop("_rev", None)
            results.append(ProvenanceEdge.model_validate(doc))
        return results
```

- [ ] **Step 7: Run tests**

```bash
python -m pytest tests/unit/test_provenance_edge.py -v
```
Expected: all 8 tests pass.

- [ ] **Step 8: Run full unit suite to check nothing broke**

```bash
python -m pytest tests/unit/ -q
```
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add src/yanantin/apacheta/interface/abstract.py \
        src/yanantin/apacheta/backends/memory.py \
        src/yanantin/apacheta/backends/arango.py \
        src/yanantin/apacheta/backends/duckdb.py \
        tests/unit/test_provenance_edge.py
git commit -m "feat(interface): store_provenance_edge + list_provenance_edges on all backends"
```

---

## Task 3: MachineConfigRecorder writes EntityResolution + has_snapshot edge

**Files:**
- Modify: `src/yanantin/machine/linux.py`
- Create: `tests/unit/test_machine_identity.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_machine_identity.py`:

```python
"""Tests for machine identity persistence via MachineConfigRecorder."""
from unittest.mock import patch
from uuid import UUID

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.models.entities import EntityResolution
from yanantin.machine.linux import MachineConfigCollector, MachineConfigRecorder
from yanantin.transport.models import WranglerEnvelope

FAKE_MACHINE_ID = "8ae0edf526f3453ab1abaf04e1c75a4a"


def _make_envelope():
    collector = MachineConfigCollector()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        with patch("yanantin.machine.base._get_machine_id", return_value=FAKE_MACHINE_ID):
            data = collector.collect()
    return WranglerEnvelope(data=data, provider_id=collector.get_provider_id())


def test_record_writes_entity_resolution():
    backend = InMemoryBackend()
    recorder = MachineConfigRecorder(backend)
    envelope = _make_envelope()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        recorder.record(envelope)
    entity = backend.get_entity(UUID(FAKE_MACHINE_ID))
    assert isinstance(entity, EntityResolution)
    assert entity.identity_type == "machine.linux"
    assert entity.identity_data == {}
    assert not entity.redacted


def test_entity_id_equals_machine_id():
    backend = InMemoryBackend()
    recorder = MachineConfigRecorder(backend)
    envelope = _make_envelope()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        recorder.record(envelope)
    entity = backend.get_entity(UUID(FAKE_MACHINE_ID))
    assert entity.id == UUID(FAKE_MACHINE_ID)


def test_record_is_idempotent():
    """Second call must not raise — entity already exists, skip write."""
    backend = InMemoryBackend()
    recorder = MachineConfigRecorder(backend)
    envelope = _make_envelope()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        recorder.record(envelope)
        recorder.record(envelope)  # must not raise ImmutabilityError


def test_record_writes_has_snapshot_edge():
    backend = InMemoryBackend()
    recorder = MachineConfigRecorder(backend)
    envelope = _make_envelope()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        tensor_id = recorder.record(envelope)
    edges = backend.list_provenance_edges()
    assert len(edges) == 1
    assert edges[0].relation_type == "has_snapshot"
    assert edges[0].from_ref == f"entities/{FAKE_MACHINE_ID}"
    assert edges[0].to_ref == f"tensors/{tensor_id}"


def test_record_writes_tensor():
    backend = InMemoryBackend()
    recorder = MachineConfigRecorder(backend)
    envelope = _make_envelope()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        tensor_id = recorder.record(envelope)
    tensor = backend.get_tensor(tensor_id)
    assert tensor is not None
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/unit/test_machine_identity.py -v
```
Expected: tests fail — `MachineConfigRecorder.record()` does not write entity or edge yet.

- [ ] **Step 3: Modify `MachineConfigRecorder.record()` in `src/yanantin/machine/linux.py`**

Add imports at the top of `linux.py`:
```python
from uuid import UUID, uuid4, uuid5, NAMESPACE_DNS
from yanantin.apacheta.models.entities import EntityResolution
from yanantin.apacheta.models.provenance_edge import ProvenanceEdge
```

Replace the `record()` method body (keep the existing tensor-building logic, add entity + edge around it):

```python
def record(self, envelope: WranglerEnvelope[MachineConfigData]) -> UUID:
    """Write EntityResolution (upsert), tensor, and has_snapshot edge."""
    data = envelope.data
    machine_uuid = UUID(data.machine_id)

    # 1. Write machine entity (idempotent — skip if already exists)
    try:
        self.interface.get_entity(machine_uuid)
    except Exception:
        entity = EntityResolution(
            id=machine_uuid,
            entity_uuid=machine_uuid,
            identity_type="machine.linux",
            identity_data={},
            redacted=False,
        )
        self.interface.store_entity(entity)

    # 2. Write snapshot tensor (existing logic unchanged)
    identity_strand = StrandRecord(
        strand_index=0,
        title="Platform Identity",
        content=(
            f"hostname: {data.hostname}\n"
            f"fqdn: {data.fqdn}\n"
            f"machine_id: {data.machine_id}"
        ),
        topics=("machine-config", "identity"),
    )
    system_strand = StrandRecord(
        strand_index=1,
        title="System Configuration",
        content=(
            f"os: {data.os_name} {data.os_release}\n"
            f"kernel: {data.os_version}\n"
            f"architecture: {data.architecture}\n"
            f"cpu_count: {data.cpu_count}\n"
            f"python: {data.python_version}"
        ),
        topics=("machine-config", "system"),
    )
    content_tag = f"content:{self._content_hash(data)}"
    tensor = TensorRecord(
        provenance=ProvenanceEnvelope(
            source=SourceIdentifier(
                identifier=envelope.provider_id,
                description="Machine configuration collector",
            ),
            author_model_family="collector",
        ),
        preamble=f"Machine configuration snapshot from {data.hostname}",
        strands=(identity_strand, system_strand),
        lineage_tags=("machine-config", content_tag),
    )
    self.interface.store_tensor(tensor)

    # 3. Write has_snapshot edge: machine entity → tensor
    edge = ProvenanceEdge(
        **{
            "_from": f"entities/{machine_uuid}",
            "_to": f"tensors/{tensor.id}",
        },
        relation_type="has_snapshot",
    )
    self.interface.store_provenance_edge(edge)

    return tensor.id
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/unit/test_machine_identity.py -v
```
Expected: all 5 tests pass.

- [ ] **Step 5: Run full unit suite**

```bash
python -m pytest tests/unit/ -q
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/yanantin/machine/linux.py \
        tests/unit/test_machine_identity.py
git commit -m "feat(machine): MachineConfigRecorder writes EntityResolution + has_snapshot edge"
```

---

## Task 4: LinuxFilesystemCollector accepts explicit machine_id

**Files:**
- Modify: `src/yanantin/collector/storage/local/linux/collector.py`

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_collector_filesystem.py` (the existing test file):

```python
from unittest.mock import patch

FAKE_MACHINE_ID = "8ae0edf526f3453ab1abaf04e1c75a4a"


def test_explicit_machine_id_used_for_provider_id(tmp_path):
    """Explicit machine_id produces deterministic provider_id across runs."""
    from uuid import uuid5, NAMESPACE_DNS
    from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector

    collector = LinuxFilesystemCollector(tmp_path, machine_id=FAKE_MACHINE_ID)
    expected = uuid5(NAMESPACE_DNS, f"yanantin.collector.filesystem.{FAKE_MACHINE_ID}")
    assert collector.get_provider_id() == expected


def test_default_machine_id_falls_back_to_etc_machine_id(tmp_path):
    """When no machine_id passed, reads /etc/machine-id."""
    from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
    with patch("yanantin.collector.storage.local.linux.collector._get_machine_id",
               return_value=FAKE_MACHINE_ID):
        collector = LinuxFilesystemCollector(tmp_path)
    from uuid import uuid5, NAMESPACE_DNS
    expected = uuid5(NAMESPACE_DNS, f"yanantin.collector.filesystem.{FAKE_MACHINE_ID}")
    assert collector.get_provider_id() == expected


def test_provider_id_stable_across_instances(tmp_path):
    """Two collectors with same machine_id and path get same provider_id."""
    from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
    c1 = LinuxFilesystemCollector(tmp_path, machine_id=FAKE_MACHINE_ID)
    c2 = LinuxFilesystemCollector(tmp_path, machine_id=FAKE_MACHINE_ID)
    assert c1.get_provider_id() == c2.get_provider_id()
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/unit/test_collector_filesystem.py::test_explicit_machine_id_used_for_provider_id -v
```
Expected: `TypeError` — `machine_id` is not a valid parameter yet.

- [ ] **Step 3: Modify the collector**

In `src/yanantin/collector/storage/local/linux/collector.py`, update `__init__`:

```python
def __init__(self, root_path: Path, machine_id: str | None = None) -> None:
    self._root_path = root_path.resolve()
    resolved_machine_id = machine_id if machine_id is not None else _get_machine_id()
    self._machine_id = resolved_machine_id
    self._provider_id = uuid5(
        NAMESPACE_DNS,
        f"yanantin.collector.filesystem.{resolved_machine_id}",
    )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/unit/test_collector_filesystem.py -v
```
Expected: all pass (existing 23 + 3 new = 26).

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/collector/storage/local/linux/collector.py \
        tests/unit/test_collector_filesystem.py
git commit -m "feat(collector): LinuxFilesystemCollector accepts explicit machine_id"
```

---

## Task 5: FilesystemFactRecorder writes provenance edges

**Files:**
- Modify: `src/yanantin/recorder/storage/local/linux/fact_recorder.py`
- Create: `tests/unit/test_filesystem_edges.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_filesystem_edges.py`:

```python
"""Tests for provenance edges written by FilesystemFactRecorder."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.recorder.storage.local.linux.fact_recorder import FilesystemFactRecorder
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler

FAKE_MACHINE_ID = "8ae0edf526f3453ab1abaf04e1c75a4a"


def _run_pipeline(tmp_path):
    """Collect a small real directory tree and record facts + edges."""
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.py").write_text("x = 1")

    store = InMemoryActivityStreamStore()
    backend = InMemoryBackend()

    with patch(
        "yanantin.collector.storage.local.linux.collector._get_machine_id",
        return_value=FAKE_MACHINE_ID,
    ):
        collector = LinuxFilesystemCollector(tmp_path, machine_id=FAKE_MACHINE_ID)

    recorder = FilesystemFactRecorder(store, backend, machine_id=FAKE_MACHINE_ID)

    snapshot = collector.collect()
    envelope = WranglerEnvelope(data=snapshot, provider_id=collector.get_provider_id())

    wrangler = DirectWrangler()
    wrangler.deliver(envelope)
    received = wrangler.receive()
    fact_count = recorder.record_facts(received)
    return fact_count, store, backend, collector


def test_two_edges_per_fact(tmp_path):
    fact_count, store, backend, collector = _run_pipeline(tmp_path)
    edges = backend.list_provenance_edges()
    assert len(edges) == fact_count * 2


def test_contains_edges_from_machine(tmp_path):
    fact_count, store, backend, collector = _run_pipeline(tmp_path)
    edges = backend.list_provenance_edges()
    contains = [e for e in edges if e.relation_type == "contains"]
    assert len(contains) == fact_count
    for edge in contains:
        assert edge.from_ref == f"entities/{FAKE_MACHINE_ID}"
        assert edge.to_ref.startswith("records/")


def test_collected_by_edges_from_provider(tmp_path):
    fact_count, store, backend, collector = _run_pipeline(tmp_path)
    edges = backend.list_provenance_edges()
    collected = [e for e in edges if e.relation_type == "collected_by"]
    assert len(collected) == fact_count
    provider_id = str(collector.get_provider_id())
    for edge in collected:
        assert edge.from_ref == f"entities/{provider_id}"
        assert edge.to_ref.startswith("records/")


def test_edge_to_ref_matches_stored_fact_id(tmp_path):
    """Edge _to UUIDs must match the IDs of stored facts.

    ActivityStreamStore has no get_all_facts; query_range over a wide
    window returns every fact. The window must bracket the synthetic
    file mtimes (real files in tmp_path, so 'now' minus a margin).
    """
    from datetime import datetime, timedelta, timezone

    fact_count, store, backend, collector = _run_pipeline(tmp_path)
    start = datetime(2000, 1, 1, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    facts = store.query_range(collector.get_provider_id(), start=start, end=end)
    fact_ids = {str(f.id) for f in facts}
    edge_targets = {e.to_ref.split("/")[1] for e in backend.list_provenance_edges()}
    assert edge_targets == fact_ids


def test_backward_compat_no_backend(tmp_path):
    """FilesystemFactRecorder still works without backend — no edges written."""
    (tmp_path / "x.txt").write_text("hi")
    store = InMemoryActivityStreamStore()
    collector = LinuxFilesystemCollector(tmp_path, machine_id=FAKE_MACHINE_ID)
    recorder = FilesystemFactRecorder(store)  # no backend arg
    snapshot = collector.collect()
    envelope = WranglerEnvelope(data=snapshot, provider_id=collector.get_provider_id())
    wrangler = DirectWrangler()
    wrangler.deliver(envelope)
    received = wrangler.receive()
    count = recorder.record_facts(received)
    assert count > 0  # facts stored, no crash
```

- [ ] **Step 2: Run to verify failure**

```bash
python -m pytest tests/unit/test_filesystem_edges.py -v
```
Expected: `TypeError` — `FilesystemFactRecorder` does not accept `backend` or `machine_id` yet.

- [ ] **Step 3: Check what `get_all_facts` is on InMemoryActivityStreamStore**

```bash
python -c "
from yanantin.activity.backends.memory import InMemoryActivityStreamStore
s = InMemoryActivityStreamStore()
print([m for m in dir(s) if 'fact' in m.lower()])
"
```

If `get_all_facts` does not exist, use whatever method lists stored facts and adjust the test in step 1 accordingly before continuing.

- [ ] **Step 4: Modify `FilesystemFactRecorder`**

Replace `src/yanantin/recorder/storage/local/linux/fact_recorder.py` entirely:

```python
"""Filesystem fact recorder — stores directory walk results as facts.

Unlike FilesystemRecorder (which stores a whole snapshot as one tensor),
this decomposes the snapshot into individual facts — one per file entry.
Each fact carries the full FileEntryData as its data dict, timestamped
by the entry's modified time.

Optionally writes provenance edges (machine→fact, collector→fact) when
an ApachetaInterface backend and machine_id are supplied.
"""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.apacheta.interface import ApachetaInterface
from yanantin.apacheta.models.provenance_edge import ProvenanceEdge
from yanantin.collector.storage.local.linux.models import FilesystemSnapshot
from yanantin.recorder.base import FactRecorderBase
from yanantin.transport.models import WranglerEnvelope


class FilesystemFactRecorder(FactRecorderBase[FilesystemSnapshot]):
    """Decomposes a filesystem snapshot into individual facts.

    One fact per FileEntryData entry. The fact's timestamp is the
    entry's modified time. The fact's data is the full entry as a dict.

    If backend and machine_id are provided, writes two provenance edges
    per fact: machine→fact ("contains") and collector→fact ("collected_by").
    """

    def __init__(
        self,
        store: ActivityStreamStore,
        backend: ApachetaInterface | None = None,
        machine_id: str | None = None,
    ) -> None:
        super().__init__(store)
        self._backend = backend
        self._machine_id = machine_id
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.fact_recorder.filesystem",
        )

    def record_facts(self, envelope: WranglerEnvelope[FilesystemSnapshot]) -> int:
        """Store one fact per file entry. Return count stored."""
        data = envelope.data
        count = 0

        for entry in data.entries:
            entry_dict = entry.model_dump(mode="json")
            content_hash = self._entry_content_hash(entry_dict)

            fact = FactRecord(
                provider_id=envelope.provider_id,
                timestamp=entry.timestamps.modified,
                data=entry_dict,
                content_hash=content_hash,
            )
            self.store.store_fact(fact)

            if self._backend is not None and self._machine_id is not None:
                self._write_edges(fact, envelope.provider_id)

            count += 1

        return count

    def _write_edges(self, fact: FactRecord, provider_id: UUID) -> None:
        """Write machine→fact and collector→fact provenance edges."""
        to_ref = f"records/{fact.id}"

        machine_edge = ProvenanceEdge(
            **{
                "_from": f"entities/{self._machine_id}",
                "_to": to_ref,
            },
            relation_type="contains",
        )
        self._backend.store_provenance_edge(machine_edge)

        collector_edge = ProvenanceEdge(
            **{
                "_from": f"entities/{provider_id}",
                "_to": to_ref,
            },
            relation_type="collected_by",
        )
        self._backend.store_provenance_edge(collector_edge)

    @staticmethod
    def _entry_content_hash(entry_dict: dict) -> str:
        """SHA-256 of deterministic JSON, truncated to 16 hex chars."""
        serialized = json.dumps(entry_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def get_recorder_id(self) -> UUID:
        return self._recorder_id

    def get_description(self) -> str:
        return "Filesystem fact recorder — stores one fact per file entry"
```

- [ ] **Step 5: Run new tests**

```bash
python -m pytest tests/unit/test_filesystem_edges.py -v
```
Expected: all pass (or fix `get_all_facts` if step 3 found a different method name).

- [ ] **Step 6: Run full unit suite**

```bash
python -m pytest tests/unit/ -q
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/yanantin/recorder/storage/local/linux/fact_recorder.py \
        tests/unit/test_filesystem_edges.py
git commit -m "feat(recorder): FilesystemFactRecorder writes contains + collected_by edges"
```

---

## Task 6: Integration test — full pipeline against apacheta_test

**Files:**
- Create: `tests/integration/test_machine_and_edges.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_machine_and_edges.py`:

```python
"""Integration test: machine entity + filesystem edges in apacheta_test.

Requires ArangoDB running with apacheta_test database accessible.
Marked with @pytest.mark.integration — skipped unless --integration flag passed.
"""

import pytest
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.machine.linux import MachineConfigCollector, MachineConfigRecorder
from yanantin.recorder.storage.local.linux.fact_recorder import FilesystemFactRecorder
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler

FAKE_MACHINE_ID = "8ae0edf526f3453ab1abaf04e1c75a4a"

pytestmark = pytest.mark.integration


@pytest.fixture
def arango_backend():
    backend = ArangoDBBackend()  # uses apacheta_test credentials from env/config
    yield backend
    # Cleanup: remove test entity and edges written during test
    try:
        db = backend._db
        db.collection("entities").delete(FAKE_MACHINE_ID, ignore_missing=True)
        db.aql.execute(
            "FOR e IN provenance_edges FILTER e._from == @from OR e._to LIKE @prefix REMOVE e IN provenance_edges",
            bind_vars={
                "from": f"entities/{FAKE_MACHINE_ID}",
                "prefix": "records/%",
            },
        )
    except Exception:
        pass


def test_machine_entity_written_to_db(arango_backend, tmp_path):
    (tmp_path / "test.txt").write_text("hello")

    # Step 1: record machine config
    mc_collector = MachineConfigCollector()
    mc_recorder = MachineConfigRecorder(arango_backend)
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        with patch("yanantin.machine.base._get_machine_id", return_value=FAKE_MACHINE_ID):
            data = mc_collector.collect()
    envelope = WranglerEnvelope(data=data, provider_id=mc_collector.get_provider_id())
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        mc_recorder.record(envelope)

    # Verify entity exists in DB
    entity = arango_backend.get_entity(UUID(FAKE_MACHINE_ID))
    assert entity.identity_type == "machine.linux"
    assert entity.id == UUID(FAKE_MACHINE_ID)

    # Verify has_snapshot edge exists
    edges = arango_backend.list_provenance_edges()
    snapshot_edges = [e for e in edges if e.relation_type == "has_snapshot"
                      and e.from_ref == f"entities/{FAKE_MACHINE_ID}"]
    assert len(snapshot_edges) >= 1


def test_filesystem_edges_written_to_db(arango_backend, tmp_path):
    (tmp_path / "alpha.txt").write_text("a")
    (tmp_path / "beta.py").write_text("b = 1")

    activity_store = ArangoDBActivityStreamStore()

    collector = LinuxFilesystemCollector(tmp_path, machine_id=FAKE_MACHINE_ID)
    recorder = FilesystemFactRecorder(
        activity_store, arango_backend, machine_id=FAKE_MACHINE_ID
    )

    snapshot = collector.collect()
    envelope = WranglerEnvelope(data=snapshot, provider_id=collector.get_provider_id())
    wrangler = DirectWrangler()
    wrangler.deliver(envelope)
    received = wrangler.receive()
    fact_count = recorder.record_facts(received)

    assert fact_count > 0

    edges = arango_backend.list_provenance_edges()
    contains = [e for e in edges
                if e.relation_type == "contains"
                and e.from_ref == f"entities/{FAKE_MACHINE_ID}"]
    collected = [e for e in edges
                 if e.relation_type == "collected_by"]

    assert len(contains) >= fact_count
    assert len(collected) >= fact_count
```

- [ ] **Step 2: Run integration test**

```bash
python -m pytest tests/integration/test_machine_and_edges.py -v -m integration
```
Expected: both tests pass against live `apacheta_test` DB.

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest tests/unit/ tests/red_bar/ -q
```
Expected: all pass.

- [ ] **Step 4: Commit and sweep OTS**

```bash
git add tests/integration/test_machine_and_edges.py
git commit -m "test(integration): machine entity + filesystem provenance edges in apacheta_test"
git add docs/ots/*.ots
git commit -m "ots: sweep trailing stamp"
```

---

## Self-Review

**Spec coverage check:**
- ✓ EntityResolution written with `entity.id = machine_id` (Task 3)
- ✓ `entity_uuid`, `identity_type = "machine.linux"`, `identity_data = {}` (Task 3)
- ✓ Idempotent upsert — skip if exists (Task 3, `test_record_is_idempotent`)
- ✓ Snapshot tensor written per run, shape unchanged (Task 3)
- ✓ `has_snapshot` edge: machine entity → tensor (Task 3)
- ✓ `LinuxFilesystemCollector` accepts `machine_id: str | None` (Task 4)
- ✓ `provider_id` derivation unchanged (Task 4)
- ✓ `FilesystemFactRecorder` writes two edges per fact (Task 5)
- ✓ `contains`: machine → fact (Task 5)
- ✓ `collected_by`: provider → fact (Task 5)
- ✓ Backward compat: works without backend (Task 5, `test_backward_compat_no_backend`)
- ✓ `ProvenanceEdge` with native `_from`/`_to` ArangoDB fields (Task 1)
- ✓ `provenance_edges` collection, not `composition_edges` (Task 2)
- ✓ `store_provenance_edge` on interface + all backends (Task 2)
- ✓ Integration test against `apacheta_test` (Task 6)
- ✓ Privilege separation: not needed in this plan — `MachineConfigData` already collects only unprivileged fields

**Type consistency:** `ProvenanceEdge` uses `from_ref`/`to_ref` as Python attribute names (with `alias="_from"`/`"_to"`). All tasks reference `edge.from_ref` and `edge.to_ref` consistently. The `**{"_from": ..., "_to": ...}` construction pattern is used in Tasks 3 and 5 consistently.

**`get_all_facts` caveat:** Task 5 step 3 explicitly checks whether `InMemoryActivityStreamStore` has `get_all_facts` before relying on it. If it doesn't, adjust `test_edge_to_ref_matches_stored_fact_id` to use whatever method exists.
