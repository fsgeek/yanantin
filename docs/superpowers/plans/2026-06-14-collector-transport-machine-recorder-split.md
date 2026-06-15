# Collector/Transport/Machine/Recorder Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `yanantin/collector/` by extracting transport (wranglers), machine identity, and recorders into their own top-level packages while keeping backward-compat shims so all existing tests pass unchanged.

**Architecture:** Three new sibling packages are created under `src/yanantin/`: `transport/` (WranglerBase, models, concrete wranglers), `machine/` (Linux machine-id logic), and `recorder/` (all RecorderBase/FactRecorderBase subclasses). The old `collector/` paths become thin re-export shims. Collectors reorganize by domain: `storage/local/linux/`, `storage/cloud/dropbox/`, `activity/linux/`, `semantic/openrouter/`. The old domain subpackages (`filesystem/`, `fs_events/`, `dropbox/`, `openrouter/`) become shims too.

**Tech Stack:** Python 3.14, Pydantic v2, uv, pytest

---

## Scope note

This plan contains 12 tasks. Each task ends with a test run — the unit suite must stay green (1513 passed, 1 skipped, 3 xfailed) throughout. No test files are modified at any point.

## Import graph (read before editing)

The key internal dependency ordering (what imports what):

```
collector/models.py        (no collector deps)
collector/base.py          → collector/models.py
collector/synthetic.py     → collector/base.py
collector/wranglers.py     → collector/base.py, collector/models.py
collector/machine_config.py → collector/base.py, collector/models.py, collector/wranglers.py
collector/checksum.py      → collector/base.py, collector/models.py, collector/synthetic.py, collector/wranglers.py
collector/filesystem/      → collector/base.py, collector/models.py, collector/machine_config.py (_get_machine_id), collector/synthetic.py, collector/wranglers.py
collector/fs_events/       → same pattern as filesystem + collector/machine_config.py (_get_machine_id)
collector/dropbox/         → collector/base.py, collector/models.py, collector/synthetic.py, collector/wranglers.py
collector/openrouter/      → collector/base.py, collector/models.py
collector/pipeline.py      → collector/base.py, collector/models.py, collector/wranglers.py
```

Move order must respect this: models first, then base, then wranglers, then machine, then domains.

## File map: final state

### New packages (canonical homes)

| New path | Content |
|----------|---------|
| `src/yanantin/transport/__init__.py` | Re-exports WranglerBase, WranglerEnvelope, ProviderRegistration, BatchWrangler, DirectWrangler, QueuedWrangler |
| `src/yanantin/transport/models.py` | **Canonical** WranglerEnvelope, ProviderRegistration |
| `src/yanantin/transport/base.py` | **Canonical** WranglerBase |
| `src/yanantin/transport/wranglers.py` | **Canonical** BatchWrangler, DirectWrangler, QueuedWrangler |
| `src/yanantin/machine/__init__.py` | Re-exports MachineConfigCollector, MachineConfigData, MachineConfigRecorder, ... |
| `src/yanantin/machine/base.py` | Abstract MachineConfigBase (thin ABC, just the `_get_machine_id` helper) |
| `src/yanantin/machine/linux.py` | **Canonical** MachineConfigCollector, MachineConfigData, MachineConfigRecorder, helpers |
| `src/yanantin/recorder/__init__.py` | Re-exports RecorderBase, FactRecorderBase |
| `src/yanantin/recorder/base.py` | **Canonical** RecorderBase, FactRecorderBase |
| `src/yanantin/recorder/storage/local/linux/__init__.py` | Re-exports FilesystemRecorder, FilesystemFactRecorder |
| `src/yanantin/recorder/storage/local/linux/recorder.py` | **Canonical** FilesystemRecorder, collect_and_record_filesystem |
| `src/yanantin/recorder/storage/local/linux/fact_recorder.py` | **Canonical** FilesystemFactRecorder |
| `src/yanantin/recorder/storage/cloud/dropbox/__init__.py` | Re-exports DropboxRecorder, DropboxFactRecorder |
| `src/yanantin/recorder/storage/cloud/dropbox/recorder.py` | **Canonical** DropboxRecorder, collect_and_record_dropbox |
| `src/yanantin/recorder/storage/cloud/dropbox/fact_recorder.py` | **Canonical** DropboxFactRecorder |
| `src/yanantin/recorder/activity/linux/__init__.py` | Re-exports FsEventRecorder, FsEventFactRecorder |
| `src/yanantin/recorder/activity/linux/recorder.py` | **Canonical** FsEventRecorder, collect_and_record_fs_events |
| `src/yanantin/recorder/activity/linux/fact_recorder.py` | **Canonical** FsEventFactRecorder |
| `src/yanantin/recorder/semantic/openrouter/__init__.py` | Re-exports OpenRouterFactRecorder |
| `src/yanantin/recorder/semantic/openrouter/fact_recorder.py` | **Canonical** OpenRouterFactRecorder |
| `src/yanantin/collector/storage/local/linux/__init__.py` | Re-exports LinuxFilesystemCollector, SyntheticFilesystemCollector, models |
| `src/yanantin/collector/storage/local/linux/collector.py` | **Canonical** LinuxFilesystemCollector |
| `src/yanantin/collector/storage/local/linux/models.py` | **Canonical** FileEntryData, FilesystemSnapshot, FileTimestamps |
| `src/yanantin/collector/storage/local/linux/synthetic.py` | **Canonical** SyntheticFilesystemCollector |
| `src/yanantin/collector/storage/local/checksum.py` | **Canonical** ChecksumCollector, ChecksumData, SyntheticChecksumCollector, ChecksumRecorder, ChecksumFactRecorder |
| `src/yanantin/collector/storage/cloud/dropbox/__init__.py` | Re-exports DropboxCollector, SyntheticDropboxCollector, models |
| `src/yanantin/collector/storage/cloud/dropbox/collector.py` | **Canonical** DropboxCollector |
| `src/yanantin/collector/storage/cloud/dropbox/models.py` | **Canonical** DropboxEntryData, DropboxListing |
| `src/yanantin/collector/storage/cloud/dropbox/synthetic.py` | **Canonical** SyntheticDropboxCollector |
| `src/yanantin/collector/activity/linux/__init__.py` | Re-exports FsIncrementalCollector, SyntheticFsEventCollector, models |
| `src/yanantin/collector/activity/linux/collector.py` | **Canonical** FsIncrementalCollector |
| `src/yanantin/collector/activity/linux/models.py` | **Canonical** FsChangeEvent, FsEventBatch |
| `src/yanantin/collector/activity/linux/synthetic.py` | **Canonical** SyntheticFsEventCollector |
| `src/yanantin/collector/semantic/openrouter/__init__.py` | Re-exports OpenRouterActivityCollector, models |
| `src/yanantin/collector/semantic/openrouter/collector.py` | **Canonical** OpenRouterActivityCollector |
| `src/yanantin/collector/semantic/openrouter/models.py` | **Canonical** OpenRouterActivity, OpenRouterActivityRow |

### Shims at old locations (never deleted)

| Old path | Becomes |
|----------|---------|
| `src/yanantin/collector/models.py` | `from yanantin.transport.models import *; __all__ = [...]` |
| `src/yanantin/collector/base.py` | `from yanantin.transport.base import WranglerBase; from yanantin.recorder.base import RecorderBase, FactRecorderBase; from yanantin.collector._collector_base import CollectorBase; __all__ = [...]` |
| `src/yanantin/collector/wranglers.py` | `from yanantin.transport.wranglers import *; __all__ = [...]` |
| `src/yanantin/collector/synthetic.py` | `from yanantin.collector._synthetic_base import SyntheticCollectorBase; __all__ = [...]` |
| `src/yanantin/collector/machine_config.py` | `from yanantin.machine.linux import *; __all__ = [...]` |
| `src/yanantin/collector/checksum.py` | `from yanantin.collector.storage.local.checksum import *; __all__ = [...]` |
| `src/yanantin/collector/filesystem/__init__.py` | `from yanantin.collector.storage.local.linux import *; __all__ = [...]` |
| `src/yanantin/collector/filesystem/collector.py` | shim → `collector/storage/local/linux/collector.py` |
| `src/yanantin/collector/filesystem/models.py` | shim → `collector/storage/local/linux/models.py` |
| `src/yanantin/collector/filesystem/synthetic.py` | shim → `collector/storage/local/linux/synthetic.py` |
| `src/yanantin/collector/filesystem/recorder.py` | shim → `recorder/storage/local/linux/recorder.py` |
| `src/yanantin/collector/filesystem/fact_recorder.py` | shim → `recorder/storage/local/linux/fact_recorder.py` |
| `src/yanantin/collector/dropbox/__init__.py` | shim → `collector/storage/cloud/dropbox/` |
| `src/yanantin/collector/dropbox/collector.py` | shim |
| `src/yanantin/collector/dropbox/models.py` | shim |
| `src/yanantin/collector/dropbox/synthetic.py` | shim |
| `src/yanantin/collector/dropbox/recorder.py` | shim → `recorder/storage/cloud/dropbox/recorder.py` |
| `src/yanantin/collector/dropbox/fact_recorder.py` | shim → `recorder/storage/cloud/dropbox/fact_recorder.py` |
| `src/yanantin/collector/fs_events/__init__.py` | shim → `collector/activity/linux/` |
| `src/yanantin/collector/fs_events/collector.py` | shim |
| `src/yanantin/collector/fs_events/models.py` | shim |
| `src/yanantin/collector/fs_events/synthetic.py` | shim |
| `src/yanantin/collector/fs_events/recorder.py` | shim → `recorder/activity/linux/recorder.py` |
| `src/yanantin/collector/fs_events/fact_recorder.py` | shim → `recorder/activity/linux/fact_recorder.py` |
| `src/yanantin/collector/openrouter/__init__.py` | shim → `collector/semantic/openrouter/` + `recorder/semantic/openrouter/` |
| `src/yanantin/collector/openrouter/collector.py` | shim |
| `src/yanantin/collector/openrouter/models.py` | shim |
| `src/yanantin/collector/openrouter/fact_recorder.py` | shim → `recorder/semantic/openrouter/fact_recorder.py` |

### Unchanged files (no move, only internal imports update)
- `src/yanantin/collector/__init__.py` — keep exporting all the same names (add `SyntheticCollectorBase` if missing)
- `src/yanantin/collector/__main__.py` — keep, update lazy imports to use new canonical paths
- `src/yanantin/collector/pipeline.py` — keep, update imports to use `yanantin.transport.*`

### New internal files needed
- `src/yanantin/collector/_collector_base.py` — holds `CollectorBase` (avoids circular: base.py shim imports from both transport and collector)
- `src/yanantin/collector/_synthetic_base.py` — holds `SyntheticCollectorBase` (same reason)

---

## Task 1: Create `yanantin/transport/` package with models, base, wranglers

**Files:**
- Create: `src/yanantin/transport/__init__.py`
- Create: `src/yanantin/transport/models.py` (copy of `collector/models.py`, no import changes)
- Create: `src/yanantin/transport/base.py` (WranglerBase only, imports from `yanantin.transport.models`)
- Create: `src/yanantin/transport/wranglers.py` (copy of `collector/wranglers.py`, imports updated to `yanantin.transport.*`)

- [ ] **Step 1: Create `src/yanantin/transport/__init__.py`**

```python
"""Transport — wrangler pipeline for moving collected data across boundaries.

Three concrete wrangler strategies (DirectWrangler, BatchWrangler,
QueuedWrangler) and the models/base they share.
"""

from yanantin.transport.base import WranglerBase
from yanantin.transport.models import ProviderRegistration, WranglerEnvelope
from yanantin.transport.wranglers import BatchWrangler, DirectWrangler, QueuedWrangler

__all__ = [
    "BatchWrangler",
    "DirectWrangler",
    "ProviderRegistration",
    "QueuedWrangler",
    "WranglerBase",
    "WranglerEnvelope",
]
```

- [ ] **Step 2: Create `src/yanantin/transport/models.py`**

Copy the content of `src/yanantin/collector/models.py` verbatim. No import changes are needed (it has no collector imports).

```python
"""Data models for the transport pipeline.

Serializable data is the boundary contract. Everything that moves through
the pipeline is a Pydantic model that can go through any wrangler strategy
unchanged. The wrangler doesn't transform data — it moves it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class ProviderRegistration(BaseModel):
    """Registration record for a collector/recorder pair.

    Answers: what is this data source, what does it produce, and when
    did it join the pipeline? The data_schema field carries the JSON
    schema of the DataT so that recorders can validate without knowing
    the concrete type at import time.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    provider_id: UUID = Field(default_factory=uuid4)
    provider_name: str
    collector_description: str = ""
    recorder_description: str = ""
    data_schema: dict = Field(default_factory=dict)
    registered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class WranglerEnvelope(BaseModel, Generic[DataT]):
    """Wraps collected data with transport provenance.

    The envelope is what moves through the wrangler. The data inside
    is untouched — the envelope records who collected it, when, and
    how it was delivered. Sequence numbers are monotonic per provider,
    so a recorder can detect gaps.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_default=True,
    )

    data: DataT
    provider_id: UUID
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    delivered_at: datetime | None = None
    wrangler_strategy: str = ""
    sequence_number: int = 0
```

- [ ] **Step 3: Create `src/yanantin/transport/base.py`**

WranglerBase only. Imports from `yanantin.transport.models`.

```python
"""Abstract base class for wrangler transport strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Generic, TypeVar

from yanantin.transport.models import WranglerEnvelope

DataT = TypeVar("DataT")


class WranglerBase(ABC, Generic[DataT]):
    """Moves data from collector to recorder across a boundary.

    The wrangler is a transport. It wraps data in a WranglerEnvelope
    with delivery provenance and hands it off. Concrete strategies
    differ in coupling: in-memory (direct), file-based (batch), or
    queue-based (async).

    The wrangler never transforms the data. Transformation is the
    recorder's job.
    """

    @abstractmethod
    def deliver(self, envelope: WranglerEnvelope[DataT]) -> None:
        """Accept an envelope from the collector side and stage it for pickup."""
        ...

    @abstractmethod
    def receive(self) -> WranglerEnvelope[DataT] | None:
        """Retrieve the next envelope for the recorder side."""
        ...

    def stamp_delivery(self, envelope: WranglerEnvelope[DataT]) -> WranglerEnvelope[DataT]:
        """Return a copy of the envelope with delivery provenance filled in."""
        return envelope.model_copy(
            update={
                "delivered_at": datetime.now(timezone.utc),
                "wrangler_strategy": self.strategy_name,
            },
        )

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Short identifier for this wrangler strategy."""
        ...
```

- [ ] **Step 4: Create `src/yanantin/transport/wranglers.py`**

Copy `collector/wranglers.py`, change only the two imports at the top:

```python
"""Concrete wrangler implementations for the collector pipeline.

Three strategies, ordered by coupling:

- **DirectWrangler** — In-memory handoff. Collector and recorder run
  in the same process, same moment. Simplest path.
- **BatchWrangler** — File-based. Collector writes JSON to a directory,
  recorder reads from it. Decoupled in time.
- **QueuedWrangler** — In-process queue (collections.deque). Decoupled
  in time but same process. Useful for producer/consumer patterns
  within a single run.

All three track provenance: when data was delivered and via what strategy.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import TypeAdapter

from yanantin.transport.base import WranglerBase
from yanantin.transport.models import WranglerEnvelope

DataT = TypeVar("DataT")
```

Then copy the three class bodies verbatim from `collector/wranglers.py` (DirectWrangler, BatchWrangler, QueuedWrangler — they have no other collector imports).

- [ ] **Step 5: Run unit tests**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ -x -q --tb=short 2>&1 | tail -5
```

Expected: 1513 passed, 1 skipped, 3 xfailed (nothing changed yet — transport is new code, no shims needed yet)

- [ ] **Step 6: Commit**

```bash
cd /home/tony/projects/yanantin
git add src/yanantin/transport/
git commit -m "feat(transport): extract WranglerBase/models/wranglers into yanantin.transport"
```

---

## Task 2: Create `yanantin/collector/_collector_base.py` and `_synthetic_base.py`

These private modules hold CollectorBase and SyntheticCollectorBase so that the upcoming `collector/base.py` shim can import from them without creating a circular dependency (base.py shim will import from both `transport` and `recorder`, and CollectorBase must be available to both sides).

**Files:**
- Create: `src/yanantin/collector/_collector_base.py`
- Create: `src/yanantin/collector/_synthetic_base.py`

- [ ] **Step 1: Create `src/yanantin/collector/_collector_base.py`**

```python
"""CollectorBase — the data-gathering half of the pipeline.

Private module. Import from yanantin.collector.base (the public shim)
or yanantin.collector directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

DataT = TypeVar("DataT")


class CollectorBase(ABC, Generic[DataT]):
    """Gathers data from a source. Does not normalize or store.

    A collector knows how to talk to one data source — a filesystem,
    an API, a hardware sensor. It produces a DataT and nothing else.
    The collector is the only component that touches the raw source.
    """

    @abstractmethod
    def collect(self, since: datetime | None = None) -> DataT:
        """Gather data from the source and return it.

        The returned value must be a serializable Pydantic model.
        No side effects on storage. No normalization.
        """
        ...

    @abstractmethod
    def get_provider_id(self) -> UUID:
        """Stable identifier for this data provider."""
        ...

    @abstractmethod
    def get_description(self) -> str:
        """Human-readable description of what this collector gathers."""
        ...
```

- [ ] **Step 2: Create `src/yanantin/collector/_synthetic_base.py`**

```python
"""SyntheticCollectorBase — deterministic synthetic data generators.

Private module. Import from yanantin.collector.synthetic (the public shim).
"""

from __future__ import annotations

import random
from abc import abstractmethod
from datetime import datetime
from typing import TypeVar
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.collector._collector_base import CollectorBase

DataT = TypeVar("DataT")


class SyntheticCollectorBase(CollectorBase[DataT]):
    """Base for synthetic data generators paired with real collectors.

    The synthetic twin must produce DataT instances indistinguishable
    from the real collector's output in structure. Seeded RNG ensures
    reproducibility across runs.
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    @abstractmethod
    def generate(self) -> DataT:
        """Generate a single synthetic data item."""
        ...

    def collect(self, since: datetime | None = None) -> DataT:
        """Collect by generating synthetic data."""
        return self.generate()

    def collect_batch(self, count: int) -> list[DataT]:
        """Generate multiple synthetic items."""
        return [self.generate() for _ in range(count)]

    def get_provider_id(self) -> UUID:
        """Provider ID derived from the class name."""
        return uuid5(
            NAMESPACE_DNS,
            f"yanantin.synthetic.{self.__class__.__name__}",
        )
```

- [ ] **Step 3: Run unit tests**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ -x -q --tb=short 2>&1 | tail -5
```

Expected: 1513 passed, 1 skipped, 3 xfailed

- [ ] **Step 4: Commit**

```bash
cd /home/tony/projects/yanantin
git add src/yanantin/collector/_collector_base.py src/yanantin/collector/_synthetic_base.py
git commit -m "feat(collector): add private _collector_base and _synthetic_base modules"
```

---

## Task 3: Create `yanantin/recorder/` package with RecorderBase and FactRecorderBase

**Files:**
- Create: `src/yanantin/recorder/__init__.py`
- Create: `src/yanantin/recorder/base.py`
- Create: `src/yanantin/recorder/storage/__init__.py`
- Create: `src/yanantin/recorder/storage/local/__init__.py`
- Create: `src/yanantin/recorder/storage/cloud/__init__.py`
- Create: `src/yanantin/recorder/activity/__init__.py`
- Create: `src/yanantin/recorder/semantic/__init__.py`

- [ ] **Step 1: Create `src/yanantin/recorder/base.py`**

RecorderBase and FactRecorderBase, importing from `yanantin.transport.models` for WranglerEnvelope:

```python
"""Abstract base classes for recorders.

- **RecorderBase** normalizes data and writes tensors via ApachetaInterface.
- **FactRecorderBase** writes raw facts to ActivityStreamStore.

Both are generic over DataT and consume WranglerEnvelope from the transport layer.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from typing import Generic, TypeVar
from uuid import UUID

from yanantin.apacheta.interface import ApachetaInterface
from yanantin.activity.store import ActivityStreamStore
from yanantin.transport.models import WranglerEnvelope

DataT = TypeVar("DataT")


class RecorderBase(ABC, Generic[DataT]):
    """Consumes data from a wrangler and writes to storage.

    The recorder owns the database write. It normalizes the data,
    maps it to Apacheta records, and stores via the ApachetaInterface.
    One recorder per data type — it knows the schema intimately.
    """

    def __init__(self, interface: ApachetaInterface) -> None:
        self._interface = interface

    @property
    def interface(self) -> ApachetaInterface:
        """The storage interface this recorder writes to."""
        return self._interface

    @staticmethod
    def _content_hash(data) -> str:
        """SHA-256 of deterministic JSON serialization, truncated to 16 hex chars."""
        serialized = json.dumps(
            data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    @abstractmethod
    def record(self, envelope: WranglerEnvelope[DataT]) -> UUID:
        """Normalize data from the envelope and write to storage."""
        ...

    @abstractmethod
    def get_recorder_id(self) -> UUID:
        """Stable identifier for this recorder instance."""
        ...

    @abstractmethod
    def get_description(self) -> str:
        """Human-readable description of what this recorder stores."""
        ...


class FactRecorderBase(ABC, Generic[DataT]):
    """Records collected data as facts in the activity stream.

    Unlike RecorderBase (which produces tensors), FactRecorderBase
    produces facts — raw observations stored in ActivityStreamStore.
    Returns int (count of facts stored), not list[UUID].
    """

    def __init__(self, store: ActivityStreamStore) -> None:
        self._store = store

    @property
    def store(self) -> ActivityStreamStore:
        """The activity stream store this recorder writes to."""
        return self._store

    @staticmethod
    def _content_hash(data) -> str:
        """SHA-256 of deterministic JSON serialization, truncated to 16 hex chars."""
        serialized = json.dumps(
            data.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    @abstractmethod
    def record_facts(self, envelope: WranglerEnvelope[DataT]) -> int:
        """Store facts from the envelope. Return count stored."""
        ...

    @abstractmethod
    def get_recorder_id(self) -> UUID:
        """Stable identifier for this recorder instance."""
        ...

    @abstractmethod
    def get_description(self) -> str:
        """Human-readable description of what this recorder stores."""
        ...
```

- [ ] **Step 2: Create `src/yanantin/recorder/__init__.py`**

```python
"""Recorder — normalizes and stores data from the collector pipeline."""

from yanantin.recorder.base import FactRecorderBase, RecorderBase

__all__ = ["FactRecorderBase", "RecorderBase"]
```

- [ ] **Step 3: Create empty namespace `__init__.py` files**

Create these four files, each with just a docstring:

`src/yanantin/recorder/storage/__init__.py`:
```python
"""Storage recorders — filesystem and cloud."""
```

`src/yanantin/recorder/storage/local/__init__.py`:
```python
"""Local storage recorders."""
```

`src/yanantin/recorder/storage/cloud/__init__.py`:
```python
"""Cloud storage recorders."""
```

`src/yanantin/recorder/activity/__init__.py`:
```python
"""Activity stream recorders."""
```

`src/yanantin/recorder/semantic/__init__.py`:
```python
"""Semantic data recorders."""
```

- [ ] **Step 4: Run unit tests**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ -x -q --tb=short 2>&1 | tail -5
```

Expected: 1513 passed, 1 skipped, 3 xfailed

- [ ] **Step 5: Commit**

```bash
cd /home/tony/projects/yanantin
git add src/yanantin/recorder/
git commit -m "feat(recorder): create yanantin.recorder package with RecorderBase and FactRecorderBase"
```

---

## Task 4: Create `yanantin/machine/` package

**Files:**
- Create: `src/yanantin/machine/__init__.py`
- Create: `src/yanantin/machine/base.py`
- Create: `src/yanantin/machine/linux.py`

- [ ] **Step 1: Create `src/yanantin/machine/base.py`**

```python
"""Abstract base for machine identity collectors."""

from __future__ import annotations

from abc import abstractmethod


def _get_machine_id() -> str:
    """Read /etc/machine-id or generate a deterministic fallback.

    Linux systems provide /etc/machine-id as a stable per-installation
    identifier. When that file is absent (macOS, Windows, containers
    without it), we generate a deterministic UUID5 from hostname + OS +
    architecture so the same machine produces the same ID across runs.
    """
    import platform
    import socket
    from pathlib import Path
    from uuid import NAMESPACE_DNS, uuid5

    try:
        return Path("/etc/machine-id").read_text().strip()
    except (OSError, PermissionError):
        hostname = socket.gethostname()
        os_name = platform.system()
        architecture = platform.machine()
        return str(uuid5(NAMESPACE_DNS, f"{hostname}.{os_name}.{architecture}"))
```

- [ ] **Step 2: Create `src/yanantin/machine/linux.py`**

Copy `collector/machine_config.py` content, update imports to use new canonical locations:

```python
"""Machine configuration collector/recorder for Linux.

Gathers platform identity and system configuration from stdlib, wraps
it in a WranglerEnvelope, and records it as a tensor via the Apacheta
interface. No external dependencies beyond the standard library and
what Yanantin already provides.
"""

from __future__ import annotations

import os
import platform
import socket
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_DNS

from pydantic import BaseModel, ConfigDict, Field

from yanantin.apacheta.interface import ApachetaInterface
from yanantin.apacheta.models import (
    ProvenanceEnvelope,
    SourceIdentifier,
    StrandRecord,
    TensorRecord,
)
from yanantin.collector._collector_base import CollectorBase
from yanantin.machine.base import _get_machine_id
from yanantin.recorder.base import RecorderBase
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler
```

Then copy the rest of `machine_config.py` verbatim (MachineConfigData, MachineConfigCollector, MachineConfigRecorder, collect_machine_config, collect_and_record, render_machine_config) with no changes to bodies.

- [ ] **Step 3: Create `src/yanantin/machine/__init__.py`**

```python
"""Machine identity — Linux platform configuration collector/recorder."""

from yanantin.machine.linux import (
    MachineConfigCollector,
    MachineConfigData,
    MachineConfigRecorder,
    collect_and_record,
    collect_machine_config,
    render_machine_config,
)

__all__ = [
    "MachineConfigCollector",
    "MachineConfigData",
    "MachineConfigRecorder",
    "collect_and_record",
    "collect_machine_config",
    "render_machine_config",
]
```

- [ ] **Step 4: Run unit tests**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ -x -q --tb=short 2>&1 | tail -5
```

Expected: 1513 passed, 1 skipped, 3 xfailed

- [ ] **Step 5: Commit**

```bash
cd /home/tony/projects/yanantin
git add src/yanantin/machine/
git commit -m "feat(machine): create yanantin.machine package for Linux machine identity"
```

---

## Task 5: Create canonical domain collectors under `collector/storage/local/linux/`

This moves the filesystem collector and models to their new canonical location. The old `collector/filesystem/` will become shims in a later task.

**Files:**
- Create: `src/yanantin/collector/storage/__init__.py`
- Create: `src/yanantin/collector/storage/local/__init__.py`
- Create: `src/yanantin/collector/storage/cloud/__init__.py`
- Create: `src/yanantin/collector/storage/local/linux/__init__.py`
- Create: `src/yanantin/collector/storage/local/linux/models.py`
- Create: `src/yanantin/collector/storage/local/linux/collector.py`
- Create: `src/yanantin/collector/storage/local/linux/synthetic.py`

- [ ] **Step 1: Create namespace `__init__.py` files**

`src/yanantin/collector/storage/__init__.py`:
```python
"""Storage domain collectors."""
```

`src/yanantin/collector/storage/local/__init__.py`:
```python
"""Local storage collectors."""
```

`src/yanantin/collector/storage/cloud/__init__.py`:
```python
"""Cloud storage collectors."""
```

`src/yanantin/collector/storage/local/linux/__init__.py`:
```python
"""Linux local filesystem collector."""

from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.collector.storage.local.linux.models import (
    FileEntryData,
    FilesystemSnapshot,
    FileTimestamps,
)
from yanantin.collector.storage.local.linux.synthetic import SyntheticFilesystemCollector

__all__ = [
    "FileEntryData",
    "FilesystemSnapshot",
    "FileTimestamps",
    "LinuxFilesystemCollector",
    "SyntheticFilesystemCollector",
]
```

- [ ] **Step 2: Create `src/yanantin/collector/storage/local/linux/models.py`**

Copy `collector/filesystem/models.py` verbatim. Its only imports are from `pydantic` and stdlib — no collector imports to change.

- [ ] **Step 3: Create `src/yanantin/collector/storage/local/linux/collector.py`**

Copy `collector/filesystem/collector.py`, updating two imports:

```python
from yanantin.collector._collector_base import CollectorBase
from yanantin.collector.storage.local.linux.models import (
    FileEntryData,
    FilesystemSnapshot,
    FileTimestamps,
)
from yanantin.machine.base import _get_machine_id
```

All three of these replace the old `from yanantin.collector.base import CollectorBase`, `from yanantin.collector.filesystem.models import ...`, and `from yanantin.collector.machine_config import _get_machine_id`.

- [ ] **Step 4: Create `src/yanantin/collector/storage/local/linux/synthetic.py`**

Copy `collector/filesystem/synthetic.py`, updating imports:

```python
from yanantin.collector._synthetic_base import SyntheticCollectorBase
from yanantin.collector.storage.local.linux.models import (
    FileEntryData,
    FilesystemSnapshot,
    FileTimestamps,
)
```

- [ ] **Step 5: Run unit tests**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ -x -q --tb=short 2>&1 | tail -5
```

Expected: 1513 passed, 1 skipped, 3 xfailed

- [ ] **Step 6: Commit**

```bash
cd /home/tony/projects/yanantin
git add src/yanantin/collector/storage/
git commit -m "feat(collector): add storage/local/linux/ canonical collector location"
```

---

## Task 6: Create canonical recorder for filesystem under `recorder/storage/local/linux/`

**Files:**
- Create: `src/yanantin/recorder/storage/local/linux/__init__.py`
- Create: `src/yanantin/recorder/storage/local/linux/recorder.py`
- Create: `src/yanantin/recorder/storage/local/linux/fact_recorder.py`

- [ ] **Step 1: Create `src/yanantin/recorder/storage/local/linux/recorder.py`**

Copy `collector/filesystem/recorder.py`, updating imports:

```python
from yanantin.recorder.base import RecorderBase
from yanantin.collector.storage.local.linux.models import FilesystemSnapshot
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler
```

The `collect_and_record_filesystem` convenience function at the bottom also needs its local import updated:

```python
# Inside collect_and_record_filesystem():
from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
```

- [ ] **Step 2: Create `src/yanantin/recorder/storage/local/linux/fact_recorder.py`**

Copy `collector/filesystem/fact_recorder.py`, updating imports:

```python
from yanantin.recorder.base import FactRecorderBase
from yanantin.collector.storage.local.linux.models import FilesystemSnapshot
from yanantin.transport.models import WranglerEnvelope
```

- [ ] **Step 3: Create `src/yanantin/recorder/storage/local/linux/__init__.py`**

```python
"""Linux filesystem recorders."""

from yanantin.recorder.storage.local.linux.fact_recorder import FilesystemFactRecorder
from yanantin.recorder.storage.local.linux.recorder import (
    FilesystemRecorder,
    collect_and_record_filesystem,
)

__all__ = [
    "FilesystemFactRecorder",
    "FilesystemRecorder",
    "collect_and_record_filesystem",
]
```

- [ ] **Step 4: Run unit tests**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ -x -q --tb=short 2>&1 | tail -5
```

Expected: 1513 passed, 1 skipped, 3 xfailed

- [ ] **Step 5: Commit**

```bash
cd /home/tony/projects/yanantin
git add src/yanantin/recorder/storage/local/
git commit -m "feat(recorder): add storage/local/linux/ canonical recorder location"
```

---

## Task 7: Create canonical collectors and recorders for Dropbox, fs_events, openrouter

**Files:**
- Create: `src/yanantin/collector/storage/cloud/dropbox/` (4 files)
- Create: `src/yanantin/collector/activity/__init__.py`
- Create: `src/yanantin/collector/activity/linux/` (4 files)
- Create: `src/yanantin/collector/semantic/__init__.py`
- Create: `src/yanantin/collector/semantic/openrouter/` (3 files)
- Create: `src/yanantin/recorder/storage/cloud/dropbox/` (3 files)
- Create: `src/yanantin/recorder/activity/linux/` (3 files)
- Create: `src/yanantin/recorder/semantic/openrouter/` (2 files)

### Dropbox collector

- [ ] **Step 1: Create `src/yanantin/collector/storage/cloud/dropbox/models.py`**

Copy `collector/dropbox/models.py` verbatim (only pydantic/stdlib imports).

- [ ] **Step 2: Create `src/yanantin/collector/storage/cloud/dropbox/collector.py`**

Copy `collector/dropbox/collector.py`, updating imports:

```python
from yanantin.collector._collector_base import CollectorBase
from yanantin.collector.storage.cloud.dropbox.models import DropboxEntryData, DropboxListing
```

- [ ] **Step 3: Create `src/yanantin/collector/storage/cloud/dropbox/synthetic.py`**

Copy `collector/dropbox/synthetic.py`, updating imports:

```python
from yanantin.collector._synthetic_base import SyntheticCollectorBase
from yanantin.collector.storage.cloud.dropbox.models import DropboxEntryData, DropboxListing
```

- [ ] **Step 4: Create `src/yanantin/collector/storage/cloud/dropbox/__init__.py`**

```python
"""Dropbox cloud storage collector."""

from yanantin.collector.storage.cloud.dropbox.collector import DropboxCollector
from yanantin.collector.storage.cloud.dropbox.models import DropboxEntryData, DropboxListing
from yanantin.collector.storage.cloud.dropbox.synthetic import SyntheticDropboxCollector

__all__ = [
    "DropboxCollector",
    "DropboxEntryData",
    "DropboxListing",
    "SyntheticDropboxCollector",
]
```

### Dropbox recorder

- [ ] **Step 5: Create `src/yanantin/recorder/storage/cloud/dropbox/recorder.py`**

Copy `collector/dropbox/recorder.py`, updating imports:

```python
from yanantin.recorder.base import RecorderBase
from yanantin.collector.storage.cloud.dropbox.models import DropboxListing
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler
```

And the inner import inside `collect_and_record_dropbox`:
```python
from yanantin.collector.storage.cloud.dropbox.collector import DropboxCollector
```

- [ ] **Step 6: Create `src/yanantin/recorder/storage/cloud/dropbox/fact_recorder.py`**

Copy `collector/dropbox/fact_recorder.py`, updating imports:

```python
from yanantin.recorder.base import FactRecorderBase
from yanantin.collector.storage.cloud.dropbox.models import DropboxListing
from yanantin.transport.models import WranglerEnvelope
```

- [ ] **Step 7: Create `src/yanantin/recorder/storage/cloud/dropbox/__init__.py`**

```python
"""Dropbox cloud storage recorders."""

from yanantin.recorder.storage.cloud.dropbox.fact_recorder import DropboxFactRecorder
from yanantin.recorder.storage.cloud.dropbox.recorder import (
    DropboxRecorder,
    collect_and_record_dropbox,
)

__all__ = [
    "DropboxFactRecorder",
    "DropboxRecorder",
    "collect_and_record_dropbox",
]
```

### fs_events / activity/linux collector

- [ ] **Step 8: Create `src/yanantin/collector/activity/__init__.py`**

```python
"""Activity collectors."""
```

- [ ] **Step 9: Create `src/yanantin/collector/activity/linux/models.py`**

Copy `collector/fs_events/models.py` verbatim (only pydantic/stdlib imports).

- [ ] **Step 10: Create `src/yanantin/collector/activity/linux/collector.py`**

Copy `collector/fs_events/collector.py`, updating imports:

```python
from yanantin.collector._collector_base import CollectorBase
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch
from yanantin.machine.base import _get_machine_id
```

- [ ] **Step 11: Create `src/yanantin/collector/activity/linux/synthetic.py`**

Copy `collector/fs_events/synthetic.py`, updating imports:

```python
from yanantin.collector._synthetic_base import SyntheticCollectorBase
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch
```

- [ ] **Step 12: Create `src/yanantin/collector/activity/linux/__init__.py`**

```python
"""Linux filesystem activity collector."""

from yanantin.collector.activity.linux.collector import FsIncrementalCollector
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch
from yanantin.collector.activity.linux.synthetic import SyntheticFsEventCollector

__all__ = [
    "FsChangeEvent",
    "FsEventBatch",
    "FsIncrementalCollector",
    "SyntheticFsEventCollector",
]
```

### fs_events recorder

- [ ] **Step 13: Create `src/yanantin/recorder/activity/linux/recorder.py`**

Copy `collector/fs_events/recorder.py`, updating imports:

```python
from yanantin.recorder.base import RecorderBase
from yanantin.collector.activity.linux.models import FsEventBatch
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler
```

And inner import in `collect_and_record_fs_events`:
```python
from yanantin.collector.activity.linux.collector import FsIncrementalCollector
```

- [ ] **Step 14: Create `src/yanantin/recorder/activity/linux/fact_recorder.py`**

Copy `collector/fs_events/fact_recorder.py`, updating imports:

```python
from yanantin.recorder.base import FactRecorderBase
from yanantin.collector.activity.linux.models import FsEventBatch
from yanantin.transport.models import WranglerEnvelope
```

- [ ] **Step 15: Create `src/yanantin/recorder/activity/linux/__init__.py`**

```python
"""Linux filesystem activity recorders."""

from yanantin.recorder.activity.linux.fact_recorder import FsEventFactRecorder
from yanantin.recorder.activity.linux.recorder import (
    FsEventRecorder,
    collect_and_record_fs_events,
)

__all__ = [
    "FsEventFactRecorder",
    "FsEventRecorder",
    "collect_and_record_fs_events",
]
```

### openrouter collector

- [ ] **Step 16: Create `src/yanantin/collector/semantic/__init__.py`**

```python
"""Semantic data collectors."""
```

- [ ] **Step 17: Create `src/yanantin/collector/semantic/openrouter/models.py`**

Copy `collector/openrouter/models.py` verbatim.

- [ ] **Step 18: Create `src/yanantin/collector/semantic/openrouter/collector.py`**

Copy `collector/openrouter/collector.py`, updating imports:

```python
from yanantin.collector._collector_base import CollectorBase
from yanantin.collector.semantic.openrouter.models import (
    OpenRouterActivity,
    OpenRouterActivityRow,
)
```

- [ ] **Step 19: Create `src/yanantin/collector/semantic/openrouter/__init__.py`**

```python
"""OpenRouter semantic activity collector."""

from yanantin.collector.semantic.openrouter.collector import OpenRouterActivityCollector
from yanantin.collector.semantic.openrouter.models import (
    OpenRouterActivity,
    OpenRouterActivityRow,
)

__all__ = [
    "OpenRouterActivity",
    "OpenRouterActivityCollector",
    "OpenRouterActivityRow",
]
```

### openrouter recorder

- [ ] **Step 20: Create `src/yanantin/recorder/semantic/openrouter/fact_recorder.py`**

Copy `collector/openrouter/fact_recorder.py`, updating imports:

```python
from yanantin.recorder.base import FactRecorderBase
from yanantin.transport.models import WranglerEnvelope
from yanantin.collector.semantic.openrouter.models import OpenRouterActivity
```

- [ ] **Step 21: Create `src/yanantin/recorder/semantic/openrouter/__init__.py`**

```python
"""OpenRouter semantic recorders."""

from yanantin.recorder.semantic.openrouter.fact_recorder import OpenRouterFactRecorder

__all__ = ["OpenRouterFactRecorder"]
```

- [ ] **Step 22: Run unit tests**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ -x -q --tb=short 2>&1 | tail -5
```

Expected: 1513 passed, 1 skipped, 3 xfailed

- [ ] **Step 23: Commit**

```bash
cd /home/tony/projects/yanantin
git add src/yanantin/collector/storage/cloud/ src/yanantin/collector/activity/ src/yanantin/collector/semantic/ \
        src/yanantin/recorder/storage/cloud/ src/yanantin/recorder/activity/ src/yanantin/recorder/semantic/
git commit -m "feat(collector,recorder): add canonical domain locations for dropbox, fs_events, openrouter"
```

---

## Task 8: Create `collector/storage/local/checksum.py` (canonical checksum location)

**Files:**
- Create: `src/yanantin/collector/storage/local/checksum.py`

- [ ] **Step 1: Create `src/yanantin/collector/storage/local/checksum.py`**

Copy `collector/checksum.py`, updating imports:

```python
from yanantin.collector._collector_base import CollectorBase
from yanantin.collector._synthetic_base import SyntheticCollectorBase
from yanantin.recorder.base import FactRecorderBase, RecorderBase
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler
```

All other imports (hashlib, mmap, os, datetime, pydantic, apacheta, activity) stay unchanged.

- [ ] **Step 2: Run unit tests**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ -x -q --tb=short 2>&1 | tail -5
```

Expected: 1513 passed, 1 skipped, 3 xfailed

- [ ] **Step 3: Commit**

```bash
cd /home/tony/projects/yanantin
git add src/yanantin/collector/storage/local/checksum.py
git commit -m "feat(collector): add storage/local/checksum.py canonical location"
```

---

## Task 9: Turn old `collector/` flat files into shims

This is the critical step where the old import paths start delegating to the new canonical locations. All tests that import from `yanantin.collector.base`, `yanantin.collector.wranglers`, etc. continue to work.

**Files to modify (replace content, do not delete):**
- `src/yanantin/collector/models.py`
- `src/yanantin/collector/wranglers.py`
- `src/yanantin/collector/synthetic.py`
- `src/yanantin/collector/machine_config.py`
- `src/yanantin/collector/checksum.py`

**Also:** `src/yanantin/collector/base.py` needs special treatment — it must re-export CollectorBase, WranglerBase, RecorderBase, FactRecorderBase all from one place.

- [ ] **Step 1: Replace `src/yanantin/collector/models.py` with shim**

```python
"""Shim: re-exports from yanantin.transport.models.

The canonical location for WranglerEnvelope and ProviderRegistration
is now yanantin.transport.models. This shim keeps old import paths working.
"""

from yanantin.transport.models import ProviderRegistration, WranglerEnvelope  # noqa: F401

__all__ = ["ProviderRegistration", "WranglerEnvelope"]
```

- [ ] **Step 2: Replace `src/yanantin/collector/wranglers.py` with shim**

```python
"""Shim: re-exports from yanantin.transport.wranglers.

The canonical location for concrete wrangler implementations is now
yanantin.transport.wranglers. This shim keeps old import paths working.
"""

from yanantin.transport.wranglers import BatchWrangler, DirectWrangler, QueuedWrangler  # noqa: F401

__all__ = ["BatchWrangler", "DirectWrangler", "QueuedWrangler"]
```

- [ ] **Step 3: Replace `src/yanantin/collector/synthetic.py` with shim**

```python
"""Shim: re-exports from yanantin.collector._synthetic_base.

The canonical SyntheticCollectorBase is in the private _synthetic_base
module to avoid circular imports. This shim keeps the old public path.
"""

from yanantin.collector._synthetic_base import SyntheticCollectorBase  # noqa: F401

__all__ = ["SyntheticCollectorBase"]
```

- [ ] **Step 4: Replace `src/yanantin/collector/machine_config.py` with shim**

```python
"""Shim: re-exports from yanantin.machine.linux.

The canonical machine config collector/recorder is now in yanantin.machine.linux.
This shim keeps old import paths working.
"""

from yanantin.machine.linux import (  # noqa: F401
    MachineConfigCollector,
    MachineConfigData,
    MachineConfigRecorder,
    collect_and_record,
    collect_machine_config,
    render_machine_config,
)
from yanantin.machine.base import _get_machine_id  # noqa: F401

__all__ = [
    "MachineConfigCollector",
    "MachineConfigData",
    "MachineConfigRecorder",
    "_get_machine_id",
    "collect_and_record",
    "collect_machine_config",
    "render_machine_config",
]
```

Note: `_get_machine_id` is in `__all__` because `collector/filesystem/collector.py` and `collector/fs_events/collector.py` import it directly from `collector.machine_config` — but those files are about to become shims pointing to the canonical location anyway, so this is belt-and-suspenders.

- [ ] **Step 5: Replace `src/yanantin/collector/checksum.py` with shim**

```python
"""Shim: re-exports from yanantin.collector.storage.local.checksum.

The canonical checksum collector/recorder is now in
yanantin.collector.storage.local.checksum. This shim keeps old import paths working.
"""

from yanantin.collector.storage.local.checksum import (  # noqa: F401
    ChecksumCollector,
    ChecksumData,
    ChecksumFactRecorder,
    ChecksumRecorder,
    SyntheticChecksumCollector,
    collect_and_record_checksum,
)

__all__ = [
    "ChecksumCollector",
    "ChecksumData",
    "ChecksumFactRecorder",
    "ChecksumRecorder",
    "SyntheticChecksumCollector",
    "collect_and_record_checksum",
]
```

- [ ] **Step 6: Replace `src/yanantin/collector/base.py` with shim**

This is the most important shim — tests import CollectorBase, WranglerBase, RecorderBase, FactRecorderBase all from `yanantin.collector.base`:

```python
"""Shim: re-exports the four pipeline base classes from their canonical locations.

- CollectorBase    → yanantin.collector._collector_base
- WranglerBase     → yanantin.transport.base
- RecorderBase     → yanantin.recorder.base
- FactRecorderBase → yanantin.recorder.base

This shim keeps the old import path working for tests and legacy code.
"""

from yanantin.collector._collector_base import CollectorBase  # noqa: F401
from yanantin.transport.base import WranglerBase  # noqa: F401
from yanantin.recorder.base import FactRecorderBase, RecorderBase  # noqa: F401

__all__ = ["CollectorBase", "FactRecorderBase", "RecorderBase", "WranglerBase"]
```

- [ ] **Step 7: Run unit tests — this is the first real integration check**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ -x -q --tb=short 2>&1 | tail -20
```

Expected: 1513 passed, 1 skipped, 3 xfailed. If any fail, the error message will pinpoint a circular import or a missing `__all__` name.

- [ ] **Step 8: Commit**

```bash
cd /home/tony/projects/yanantin
git add src/yanantin/collector/models.py src/yanantin/collector/wranglers.py \
        src/yanantin/collector/synthetic.py src/yanantin/collector/machine_config.py \
        src/yanantin/collector/checksum.py src/yanantin/collector/base.py
git commit -m "refactor(collector): convert flat modules to re-export shims pointing at canonical locations"
```

---

## Task 10: Turn old `collector/filesystem/`, `collector/fs_events/`, `collector/dropbox/`, `collector/openrouter/` into shims

**Files to modify:**
- All files inside `collector/filesystem/`, `collector/fs_events/`, `collector/dropbox/`, `collector/openrouter/`

### filesystem shims

- [ ] **Step 1: Replace `src/yanantin/collector/filesystem/models.py`**

```python
"""Shim → yanantin.collector.storage.local.linux.models"""
from yanantin.collector.storage.local.linux.models import (  # noqa: F401
    FileEntryData, FilesystemSnapshot, FileTimestamps,
)
__all__ = ["FileEntryData", "FilesystemSnapshot", "FileTimestamps"]
```

- [ ] **Step 2: Replace `src/yanantin/collector/filesystem/collector.py`**

```python
"""Shim → yanantin.collector.storage.local.linux.collector"""
from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector  # noqa: F401
__all__ = ["LinuxFilesystemCollector"]
```

- [ ] **Step 3: Replace `src/yanantin/collector/filesystem/synthetic.py`**

```python
"""Shim → yanantin.collector.storage.local.linux.synthetic"""
from yanantin.collector.storage.local.linux.synthetic import SyntheticFilesystemCollector  # noqa: F401
__all__ = ["SyntheticFilesystemCollector"]
```

- [ ] **Step 4: Replace `src/yanantin/collector/filesystem/recorder.py`**

```python
"""Shim → yanantin.recorder.storage.local.linux.recorder"""
from yanantin.recorder.storage.local.linux.recorder import (  # noqa: F401
    FilesystemRecorder, collect_and_record_filesystem,
)
__all__ = ["FilesystemRecorder", "collect_and_record_filesystem"]
```

- [ ] **Step 5: Replace `src/yanantin/collector/filesystem/fact_recorder.py`**

```python
"""Shim → yanantin.recorder.storage.local.linux.fact_recorder"""
from yanantin.recorder.storage.local.linux.fact_recorder import FilesystemFactRecorder  # noqa: F401
__all__ = ["FilesystemFactRecorder"]
```

- [ ] **Step 6: Replace `src/yanantin/collector/filesystem/__init__.py`**

```python
"""Shim: filesystem collector at old location → new storage/local/linux paths."""

from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector  # noqa: F401
from yanantin.collector.storage.local.linux.models import (  # noqa: F401
    FileEntryData, FilesystemSnapshot, FileTimestamps,
)
from yanantin.collector.storage.local.linux.synthetic import SyntheticFilesystemCollector  # noqa: F401
from yanantin.recorder.storage.local.linux.recorder import (  # noqa: F401
    FilesystemRecorder, collect_and_record_filesystem,
)

__all__ = [
    "FileEntryData",
    "FilesystemRecorder",
    "FilesystemSnapshot",
    "FileTimestamps",
    "LinuxFilesystemCollector",
    "SyntheticFilesystemCollector",
    "collect_and_record_filesystem",
]
```

### fs_events shims

- [ ] **Step 7: Replace `src/yanantin/collector/fs_events/models.py`**

```python
"""Shim → yanantin.collector.activity.linux.models"""
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch  # noqa: F401
__all__ = ["FsChangeEvent", "FsEventBatch"]
```

- [ ] **Step 8: Replace `src/yanantin/collector/fs_events/collector.py`**

```python
"""Shim → yanantin.collector.activity.linux.collector"""
from yanantin.collector.activity.linux.collector import FsIncrementalCollector  # noqa: F401
__all__ = ["FsIncrementalCollector"]
```

- [ ] **Step 9: Replace `src/yanantin/collector/fs_events/synthetic.py`**

```python
"""Shim → yanantin.collector.activity.linux.synthetic"""
from yanantin.collector.activity.linux.synthetic import SyntheticFsEventCollector  # noqa: F401
__all__ = ["SyntheticFsEventCollector"]
```

- [ ] **Step 10: Replace `src/yanantin/collector/fs_events/recorder.py`**

```python
"""Shim → yanantin.recorder.activity.linux.recorder"""
from yanantin.recorder.activity.linux.recorder import (  # noqa: F401
    FsEventRecorder, collect_and_record_fs_events,
)
__all__ = ["FsEventRecorder", "collect_and_record_fs_events"]
```

- [ ] **Step 11: Replace `src/yanantin/collector/fs_events/fact_recorder.py`**

```python
"""Shim → yanantin.recorder.activity.linux.fact_recorder"""
from yanantin.recorder.activity.linux.fact_recorder import FsEventFactRecorder  # noqa: F401
__all__ = ["FsEventFactRecorder"]
```

- [ ] **Step 12: Replace `src/yanantin/collector/fs_events/__init__.py`**

```python
"""Shim: fs_events collector at old location → new activity/linux paths."""

from yanantin.collector.activity.linux.collector import FsIncrementalCollector  # noqa: F401
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch  # noqa: F401
from yanantin.collector.activity.linux.synthetic import SyntheticFsEventCollector  # noqa: F401
from yanantin.recorder.activity.linux.recorder import (  # noqa: F401
    FsEventRecorder, collect_and_record_fs_events,
)

__all__ = [
    "FsChangeEvent",
    "FsEventBatch",
    "FsEventRecorder",
    "FsIncrementalCollector",
    "SyntheticFsEventCollector",
    "collect_and_record_fs_events",
]
```

### dropbox shims

- [ ] **Step 13: Replace `src/yanantin/collector/dropbox/models.py`**

```python
"""Shim → yanantin.collector.storage.cloud.dropbox.models"""
from yanantin.collector.storage.cloud.dropbox.models import DropboxEntryData, DropboxListing  # noqa: F401
__all__ = ["DropboxEntryData", "DropboxListing"]
```

- [ ] **Step 14: Replace `src/yanantin/collector/dropbox/collector.py`**

```python
"""Shim → yanantin.collector.storage.cloud.dropbox.collector"""
from yanantin.collector.storage.cloud.dropbox.collector import DropboxCollector  # noqa: F401
__all__ = ["DropboxCollector"]
```

- [ ] **Step 15: Replace `src/yanantin/collector/dropbox/synthetic.py`**

```python
"""Shim → yanantin.collector.storage.cloud.dropbox.synthetic"""
from yanantin.collector.storage.cloud.dropbox.synthetic import SyntheticDropboxCollector  # noqa: F401
__all__ = ["SyntheticDropboxCollector"]
```

- [ ] **Step 16: Replace `src/yanantin/collector/dropbox/recorder.py`**

```python
"""Shim → yanantin.recorder.storage.cloud.dropbox.recorder"""
from yanantin.recorder.storage.cloud.dropbox.recorder import (  # noqa: F401
    DropboxRecorder, collect_and_record_dropbox,
)
__all__ = ["DropboxRecorder", "collect_and_record_dropbox"]
```

- [ ] **Step 17: Replace `src/yanantin/collector/dropbox/fact_recorder.py`**

```python
"""Shim → yanantin.recorder.storage.cloud.dropbox.fact_recorder"""
from yanantin.recorder.storage.cloud.dropbox.fact_recorder import DropboxFactRecorder  # noqa: F401
__all__ = ["DropboxFactRecorder"]
```

- [ ] **Step 18: Replace `src/yanantin/collector/dropbox/__init__.py`**

```python
"""Shim: dropbox collector at old location → new storage/cloud/dropbox paths."""

from yanantin.collector.storage.cloud.dropbox.collector import DropboxCollector  # noqa: F401
from yanantin.collector.storage.cloud.dropbox.models import DropboxEntryData, DropboxListing  # noqa: F401
from yanantin.collector.storage.cloud.dropbox.synthetic import SyntheticDropboxCollector  # noqa: F401
from yanantin.recorder.storage.cloud.dropbox.recorder import (  # noqa: F401
    DropboxRecorder, collect_and_record_dropbox,
)

__all__ = [
    "DropboxCollector",
    "DropboxEntryData",
    "DropboxListing",
    "DropboxRecorder",
    "SyntheticDropboxCollector",
    "collect_and_record_dropbox",
]
```

### openrouter shims

- [ ] **Step 19: Replace `src/yanantin/collector/openrouter/models.py`**

```python
"""Shim → yanantin.collector.semantic.openrouter.models"""
from yanantin.collector.semantic.openrouter.models import (  # noqa: F401
    OpenRouterActivity, OpenRouterActivityRow,
)
__all__ = ["OpenRouterActivity", "OpenRouterActivityRow"]
```

- [ ] **Step 20: Replace `src/yanantin/collector/openrouter/collector.py`**

```python
"""Shim → yanantin.collector.semantic.openrouter.collector"""
from yanantin.collector.semantic.openrouter.collector import OpenRouterActivityCollector  # noqa: F401
__all__ = ["OpenRouterActivityCollector"]
```

- [ ] **Step 21: Replace `src/yanantin/collector/openrouter/fact_recorder.py`**

```python
"""Shim → yanantin.recorder.semantic.openrouter.fact_recorder"""
from yanantin.recorder.semantic.openrouter.fact_recorder import OpenRouterFactRecorder  # noqa: F401
__all__ = ["OpenRouterFactRecorder"]
```

- [ ] **Step 22: Replace `src/yanantin/collector/openrouter/__init__.py`**

```python
"""Shim: openrouter collector at old location → new semantic/openrouter paths."""

from yanantin.collector.semantic.openrouter.collector import OpenRouterActivityCollector  # noqa: F401
from yanantin.collector.semantic.openrouter.models import (  # noqa: F401
    OpenRouterActivity, OpenRouterActivityRow,
)
from yanantin.recorder.semantic.openrouter.fact_recorder import OpenRouterFactRecorder  # noqa: F401

__all__ = [
    "OpenRouterActivity",
    "OpenRouterActivityCollector",
    "OpenRouterActivityRow",
    "OpenRouterFactRecorder",
]
```

- [ ] **Step 23: Run unit tests**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ -x -q --tb=short 2>&1 | tail -20
```

Expected: 1513 passed, 1 skipped, 3 xfailed

- [ ] **Step 24: Commit**

```bash
cd /home/tony/projects/yanantin
git add src/yanantin/collector/filesystem/ src/yanantin/collector/fs_events/ \
        src/yanantin/collector/dropbox/ src/yanantin/collector/openrouter/
git commit -m "refactor(collector): convert domain subpackages to re-export shims"
```

---

## Task 11: Update `collector/pipeline.py` and `collector/__init__.py` to use canonical imports

Now that the shims exist, `pipeline.py` should import from the canonical transport location. `collector/__init__.py` must keep exporting everything it currently exports.

**Files to modify:**
- `src/yanantin/collector/pipeline.py`
- `src/yanantin/collector/__init__.py`

- [ ] **Step 1: Update `src/yanantin/collector/pipeline.py`**

Change the three collector imports to canonical locations:

```python
from yanantin.recorder.base import FactRecorderBase
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler
```

Keep all other content verbatim.

- [ ] **Step 2: Update `src/yanantin/collector/__init__.py`**

Update all the from-imports to use the canonical locations. The `__all__` list must remain identical. The shims mean both the old and new paths work, but the top-level `__init__` should use canonical paths to avoid indirection chains.

```python
"""Collector — the data pipeline for bringing human-side data into Yanantin.

The collector/wrangler/recorder pattern separates three concerns:

- **Collector** gathers data from a source (filesystem, API, sensor)
- **Wrangler** moves data across boundaries (in-memory, file, queue)
- **Recorder** normalizes and stores data via the Apacheta interface

Usage::

    from yanantin.collector import CollectorBase, RecorderBase, DirectWrangler
    from yanantin.collector import WranglerEnvelope, ProviderRegistration
"""

from yanantin.collector._collector_base import CollectorBase
from yanantin.collector._synthetic_base import SyntheticCollectorBase
from yanantin.collector.storage.local.checksum import (
    ChecksumCollector,
    ChecksumData,
    ChecksumFactRecorder,
    ChecksumRecorder,
    SyntheticChecksumCollector,
    collect_and_record_checksum,
)
from yanantin.collector.storage.cloud.dropbox import (
    DropboxCollector,
    DropboxEntryData,
    DropboxListing,
    SyntheticDropboxCollector,
)
from yanantin.collector.storage.local.linux import (
    FileEntryData,
    FilesystemSnapshot,
    FileTimestamps,
    LinuxFilesystemCollector,
    SyntheticFilesystemCollector,
)
from yanantin.collector.activity.linux import (
    FsChangeEvent,
    FsEventBatch,
    FsIncrementalCollector,
    SyntheticFsEventCollector,
)
from yanantin.machine.linux import (
    MachineConfigCollector,
    MachineConfigData,
    MachineConfigRecorder,
    collect_and_record,
    collect_machine_config,
    render_machine_config,
)
from yanantin.transport.models import ProviderRegistration, WranglerEnvelope
from yanantin.transport.wranglers import BatchWrangler, DirectWrangler, QueuedWrangler
from yanantin.recorder.base import FactRecorderBase, RecorderBase
from yanantin.recorder.storage.local.linux import (
    FilesystemRecorder,
    collect_and_record_filesystem,
)
from yanantin.recorder.storage.cloud.dropbox import (
    DropboxRecorder,
    collect_and_record_dropbox,
)
from yanantin.recorder.activity.linux import (
    FsEventRecorder,
    collect_and_record_fs_events,
)
from yanantin.transport.base import WranglerBase

__all__ = [
    "BatchWrangler",
    "ChecksumCollector",
    "ChecksumData",
    "ChecksumFactRecorder",
    "ChecksumRecorder",
    "CollectorBase",
    "FactRecorderBase",
    "DirectWrangler",
    "DropboxCollector",
    "DropboxEntryData",
    "DropboxListing",
    "DropboxRecorder",
    "FileEntryData",
    "FilesystemRecorder",
    "FilesystemSnapshot",
    "FileTimestamps",
    "FsChangeEvent",
    "FsEventBatch",
    "FsEventRecorder",
    "FsIncrementalCollector",
    "LinuxFilesystemCollector",
    "MachineConfigCollector",
    "MachineConfigData",
    "MachineConfigRecorder",
    "ProviderRegistration",
    "QueuedWrangler",
    "RecorderBase",
    "SyntheticChecksumCollector",
    "SyntheticCollectorBase",
    "SyntheticDropboxCollector",
    "SyntheticFsEventCollector",
    "SyntheticFilesystemCollector",
    "WranglerBase",
    "WranglerEnvelope",
    "collect_and_record",
    "collect_and_record_checksum",
    "collect_and_record_dropbox",
    "collect_and_record_filesystem",
    "collect_and_record_fs_events",
    "collect_machine_config",
    "render_machine_config",
]
```

- [ ] **Step 3: Run unit tests**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ -x -q --tb=short 2>&1 | tail -5
```

Expected: 1513 passed, 1 skipped, 3 xfailed

- [ ] **Step 4: Commit**

```bash
cd /home/tony/projects/yanantin
git add src/yanantin/collector/pipeline.py src/yanantin/collector/__init__.py
git commit -m "refactor(collector): update pipeline.py and __init__.py to use canonical import paths"
```

---

## Task 12: Final verification — full test suite including red_bar

- [ ] **Step 1: Run the full test suite**

```bash
cd /home/tony/projects/yanantin && python -m pytest tests/unit/ tests/red_bar/ -x -q --tb=short 2>&1 | tail -20
```

Expected: all passing (plus any pre-existing skipped/xfailed).

- [ ] **Step 2: Spot-check import resolution from new canonical paths**

```bash
cd /home/tony/projects/yanantin && python -c "
from yanantin.transport import WranglerBase, WranglerEnvelope, DirectWrangler
from yanantin.recorder import RecorderBase, FactRecorderBase
from yanantin.machine import MachineConfigCollector, collect_machine_config
from yanantin.collector.storage.local.linux import LinuxFilesystemCollector
from yanantin.collector.activity.linux import FsIncrementalCollector
from yanantin.recorder.storage.local.linux import FilesystemRecorder
from yanantin.recorder.activity.linux import FsEventFactRecorder
from yanantin.recorder.semantic.openrouter import OpenRouterFactRecorder
print('All canonical imports OK')
"
```

Expected: `All canonical imports OK`

- [ ] **Step 3: Spot-check old shim paths still work**

```bash
cd /home/tony/projects/yanantin && python -c "
from yanantin.collector.base import CollectorBase, WranglerBase, RecorderBase, FactRecorderBase
from yanantin.collector.models import WranglerEnvelope, ProviderRegistration
from yanantin.collector.wranglers import DirectWrangler, BatchWrangler, QueuedWrangler
from yanantin.collector.machine_config import MachineConfigCollector, _get_machine_id
from yanantin.collector.checksum import ChecksumCollector, ChecksumFactRecorder
from yanantin.collector.filesystem import LinuxFilesystemCollector, SyntheticFilesystemCollector
from yanantin.collector.filesystem.fact_recorder import FilesystemFactRecorder
from yanantin.collector.fs_events import FsIncrementalCollector
from yanantin.collector.fs_events.fact_recorder import FsEventFactRecorder
from yanantin.collector.dropbox import DropboxCollector
from yanantin.collector.dropbox.fact_recorder import DropboxFactRecorder
from yanantin.collector.openrouter import OpenRouterFactRecorder
from yanantin.collector.synthetic import SyntheticCollectorBase
print('All shim paths OK')
"
```

Expected: `All shim paths OK`

- [ ] **Step 4: Final commit**

```bash
cd /home/tony/projects/yanantin
git commit --allow-empty -m "chore(restructure): collector/transport/machine/recorder split complete — all shims verified"
```

---

## Self-review

**Spec coverage check:**

| Requirement | Task |
|---|---|
| `collector/wranglers.py` → `transport/wranglers.py` | Task 1 |
| `collector/models.py` → `transport/models.py` | Task 1 |
| `collector/machine_config.py` → `machine/linux.py` + `machine/base.py` | Task 4 |
| `collector/base.py` split (CollectorBase stays in collector, RecorderBase/FactRecorderBase → `recorder/base.py`, WranglerBase → `transport/base.py`) | Tasks 2, 3, 9 |
| `collector/filesystem/` → `collector/storage/local/linux/` | Task 5 |
| `collector/filesystem/recorder.py` → `recorder/storage/local/linux/recorder.py` | Task 6 |
| `collector/filesystem/fact_recorder.py` → `recorder/storage/local/linux/fact_recorder.py` | Task 6 |
| `collector/dropbox/` → `collector/storage/cloud/dropbox/` | Task 7 |
| `collector/dropbox/recorder.py` → `recorder/storage/cloud/dropbox/recorder.py` | Task 7 |
| `collector/dropbox/fact_recorder.py` → `recorder/storage/cloud/dropbox/fact_recorder.py` | Task 7 |
| `collector/fs_events/` → `collector/activity/linux/` | Task 7 |
| `collector/fs_events/recorder.py` → `recorder/activity/linux/recorder.py` | Task 7 |
| `collector/fs_events/fact_recorder.py` → `recorder/activity/linux/fact_recorder.py` | Task 7 |
| `collector/openrouter/` → `collector/semantic/openrouter/` | Task 7 |
| `collector/openrouter/fact_recorder.py` → `recorder/semantic/openrouter/fact_recorder.py` | Task 7 |
| `collector/checksum.py` → `collector/storage/local/checksum.py` | Task 8 |
| `collector/pipeline.py` stays, updates imports | Task 11 |
| `collector/synthetic.py` merges into `collector/base.py` | Tasks 2+9 (private module + shim) |
| Old locations get shims | Tasks 9, 10 |
| Tests pass unchanged | Verified at each task |
| `collector/__init__.py` exports same names | Task 11 |

**Placeholder scan:** No "TBD" or "TODO" found. All code blocks are complete.

**Type consistency:** `WranglerEnvelope`, `WranglerBase`, `RecorderBase`, `FactRecorderBase`, `CollectorBase` names are consistent across all tasks. Import paths are checked in all canonical files.

**One gap addressed:** The spec says "merge `collector/synthetic.py` into `collector/base.py`". This was implemented as a private module (`_synthetic_base.py`) with a shim at `collector/synthetic.py`, which achieves the same goal without breaking the import `from yanantin.collector.synthetic import SyntheticCollectorBase` that tests use. The private module approach avoids a circular import that would arise if `SyntheticCollectorBase` lived in `base.py` (which is now a shim importing from three separate packages).
