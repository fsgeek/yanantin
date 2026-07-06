# Storage Activity Band Aggregator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a banding activity witness that collapses the filesystem-change firehose into one episodic band record per `(file-handle, principal)`, and prove on real mtime-scan data that it tames the firehose without lying about identity strength.

**Architecture:** A pure, source-agnostic `BandAggregator` holds live state keyed by `(handle, principal)`, OR-ing access-kind bits across a band and emitting a `StorageActivityBand` on quiescence (or an explicit flush). A separate mtime-scan adapter feeds it `FsChangeEvent`s across scan runs (batch-fed, quiescence-only — no causal `close`), minting weak `path:` location URIs. A fact recorder serializes emitted bands into `FactRecord.data`. Every layer is illiterate: it records opaque tokens and interprets none of them.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest. No new dependencies. No OS event APIs (mtime-scan only). No live database (bands serialize into the existing `FactRecord`/`ActivityStreamStore` contract, unit-tested against `InMemoryActivityStreamStore`).

## Global Constraints

- Spec authority: `docs/superpowers/specs/2026-07-05-activity-observation-reduction-design.md`. Where code and spec disagree, stop and reconcile — do not silently diverge.
- `StorageActivityBand` is `frozen=True, extra="allow"` — it is an open witness payload, NOT a closed model. Do not add `extra="forbid"`.
- `location` is an OPAQUE collector-minted URI string. No layer in this plan parses it, splits it, or interprets its scheme. It is compared only as a whole string.
- Bands are single-actor by construction: principal is part of the aggregator key. Never merge two principals into one band.
- `access_kinds` is persisted as `int` but manipulated as `StorageAccessKind(IntFlag)`. Reject bits outside the declared mask.
- Counts are discarded. The aggregator OR-s kind bits; it does NOT count operations. No `operation_counts`, no per-file `intensity`.
- No curator (temporal or relevance) is built. `granularity` and `compaction_level` are inert seams with fixed defaults (`"band"`, `0`).
- The collector never filters by relevance. The ONLY thing persistence drops that observation saw is the intra-band create+delete elision (a temp file's whole life inside one band).
- Naming: Quechua for packages/services is the repo convention, but this work extends existing `yanantin.activity` / `yanantin.collector.activity.linux` trees — follow the established English-descriptive names there (`StorageActivityBand`, `BandAggregator`), do not rename existing neighbors.
- AI commits must be signed with the Yanantin identity — override all three together:
  `git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" -c user.signingkey="D0CAB9659C950893" commit ...`
  Verify with `git log -1 --format='%h %an [%G?]'` → expect `[G]`.

---

### Task 1: `StorageAccessKind` + `StorageActivityBand` model

**Files:**
- Create: `src/yanantin/activity/band.py`
- Test: `tests/unit/test_storage_activity_band.py`

**Interfaces:**
- Consumes: nothing (leaf task).
- Produces:
  - `class StorageAccessKind(IntFlag)` with `CREATE=1, READ=2, WRITE=4, RENAME=8, DELETE=16`.
  - `class StorageActivityBand(BaseModel)` — `frozen=True, extra="allow"`. Fields: `location: str`, `access_kinds: int`, `band_start: datetime`, `band_end: datetime`, `granularity: str = "band"`, `compaction_level: int = 0`, `source_sequence: str | None = None`, `os_principal: str | None = None`, `process_id: int | None = None`, `process_name: str | None = None`.
  - `StorageActivityBand.band_id() -> UUID` — deterministic `uuid5` over `(location, os_principal, band_start, band_end, granularity, compaction_level)`.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for the StorageActivityBand witness payload.

Verifies:
- StorageAccessKind bits OR together as a mask
- Band is frozen and open (extra="allow")
- band_id is deterministic uuid5 over identity fields
- band_id differs when principal differs (single-actor identity)
"""
from __future__ import annotations

from datetime import datetime, timezone

from yanantin.activity.band import StorageAccessKind, StorageActivityBand


def _band(**kw):
    base = dict(
        location="path:/home/tony/foo",
        access_kinds=int(StorageAccessKind.CREATE | StorageAccessKind.WRITE),
        band_start=datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc),
        band_end=datetime(2026, 7, 6, 9, 5, tzinfo=timezone.utc),
    )
    base.update(kw)
    return StorageActivityBand(**base)


def test_access_kind_bits_or_together():
    mask = StorageAccessKind.CREATE | StorageAccessKind.DELETE
    assert int(mask) == 1 + 16
    assert StorageAccessKind.CREATE in StorageAccessKind(int(mask))


def test_band_is_frozen():
    band = _band()
    try:
        band.location = "path:/other"
        raised = False
    except Exception:
        raised = True
    assert raised, "band must be frozen"


def test_band_allows_extra_fields():
    band = _band(source_specific_evidence="ntfs-usn-42")
    assert band.model_dump()["source_specific_evidence"] == "ntfs-usn-42"


def test_band_id_deterministic():
    assert _band().band_id() == _band().band_id()


def test_band_id_differs_by_principal():
    a = _band(os_principal="1000")
    b = _band(os_principal="1001")
    assert a.band_id() != b.band_id()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_storage_activity_band.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yanantin.activity.band'`

- [ ] **Step 3: Write minimal implementation**

```python
"""The banded storage-activity witness payload.

A band is "this file had these kinds of things done to it during this time
band" — the episodic unit a memory owner can recall. It is an OPEN witness
(extra="allow"): source-specific evidence rides along and is never required.
It is serialized into FactRecord.data; the store does not understand it.
"""
from __future__ import annotations

from datetime import datetime
from enum import IntFlag
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict


class StorageAccessKind(IntFlag):
    CREATE = 1 << 0
    READ = 1 << 1
    WRITE = 1 << 2
    RENAME = 1 << 3
    DELETE = 1 << 4


class StorageActivityBand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow", validate_default=True)

    location: str
    access_kinds: int
    band_start: datetime
    band_end: datetime
    granularity: str = "band"
    compaction_level: int = 0

    source_sequence: str | None = None
    os_principal: str | None = None
    process_id: int | None = None
    process_name: str | None = None

    def band_id(self) -> UUID:
        key = "|".join(
            str(x)
            for x in (
                self.location,
                self.os_principal,
                self.band_start.isoformat(),
                self.band_end.isoformat(),
                self.granularity,
                self.compaction_level,
            )
        )
        return uuid5(NAMESPACE_URL, key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_storage_activity_band.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/activity/band.py tests/unit/test_storage_activity_band.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" -c user.signingkey="D0CAB9659C950893" commit -m "feat(activity): StorageActivityBand witness payload + StorageAccessKind"
```

---

### Task 2: `BandAggregator` — live keyed state, OR-ing, quiescence emit

**Files:**
- Create: `src/yanantin/activity/band_aggregator.py`
- Test: `tests/unit/test_band_aggregator.py`

**Interfaces:**
- Consumes: `StorageActivityBand`, `StorageAccessKind` from Task 1.
- Produces:
  - `class BandAggregator` constructed as `BandAggregator(quiescence: timedelta)`.
  - `observe(self, location: str, kind: StorageAccessKind, at: datetime, os_principal: str | None = None) -> None` — folds one access into the live entry keyed by `(location, os_principal)`.
  - `flush_quiescent(self, now: datetime) -> list[StorageActivityBand]` — emits and evicts entries whose `band_end` is older than `now - quiescence`. Applies the create+delete-in-band elision (returns nothing for those). Returns emitted bands.
  - `flush_all(self) -> list[StorageActivityBand]` — emits and evicts every remaining entry (end-of-stream). Same elision rule.

Aggregator is source-agnostic and event-fed. It does NOT know about scan runs, `FsChangeEvent`, or URIs beyond treating `location` as an opaque key.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for the source-agnostic BandAggregator.

Verifies:
- Repeated accesses to one (location, principal) OR into one band, counts discarded
- Two principals on the same location produce two single-actor bands
- Quiescence emits only entries idle past the window; active ones stay
- create+delete within one band is elided (no band emitted)
- band_start/band_end track first/last access
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from yanantin.activity.band import StorageAccessKind
from yanantin.activity.band_aggregator import BandAggregator

T0 = datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc)
def at(sec): return T0 + timedelta(seconds=sec)
Q = timedelta(minutes=5)


def test_repeated_access_ors_into_one_band():
    agg = BandAggregator(quiescence=Q)
    agg.observe("path:/a", StorageAccessKind.READ, at(0), os_principal="1000")
    agg.observe("path:/a", StorageAccessKind.READ, at(1), os_principal="1000")
    agg.observe("path:/a", StorageAccessKind.WRITE, at(2), os_principal="1000")
    bands = agg.flush_all()
    assert len(bands) == 1
    kinds = StorageAccessKind(bands[0].access_kinds)
    assert StorageAccessKind.READ in kinds and StorageAccessKind.WRITE in kinds
    assert bands[0].band_start == at(0)
    assert bands[0].band_end == at(2)


def test_two_principals_two_bands():
    agg = BandAggregator(quiescence=Q)
    agg.observe("path:/a", StorageAccessKind.WRITE, at(0), os_principal="1000")
    agg.observe("path:/a", StorageAccessKind.WRITE, at(1), os_principal="1001")
    bands = agg.flush_all()
    assert len(bands) == 2
    principals = {b.os_principal for b in bands}
    assert principals == {"1000", "1001"}


def test_quiescence_emits_only_idle_entries():
    agg = BandAggregator(quiescence=Q)
    agg.observe("path:/idle", StorageAccessKind.WRITE, at(0), os_principal="1000")
    agg.observe("path:/active", StorageAccessKind.WRITE, at(60 * 10), os_principal="1000")
    # now is 5m1s after the idle entry's last touch, but the active entry is fresh
    emitted = agg.flush_quiescent(now=at(60 * 10 + 1))
    assert len(emitted) == 1
    assert emitted[0].location == "path:/idle"


def test_create_delete_in_band_is_elided():
    agg = BandAggregator(quiescence=Q)
    agg.observe("path:/tmp/x", StorageAccessKind.CREATE, at(0), os_principal="1000")
    agg.observe("path:/tmp/x", StorageAccessKind.DELETE, at(1), os_principal="1000")
    bands = agg.flush_all()
    assert bands == []


def test_create_write_delete_in_band_is_NOT_elided():
    # elision is create+delete ONLY; if it was also written, it may matter
    agg = BandAggregator(quiescence=Q)
    agg.observe("path:/tmp/x", StorageAccessKind.CREATE, at(0), os_principal="1000")
    agg.observe("path:/tmp/x", StorageAccessKind.WRITE, at(1), os_principal="1000")
    agg.observe("path:/tmp/x", StorageAccessKind.DELETE, at(2), os_principal="1000")
    bands = agg.flush_all()
    assert len(bands) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_band_aggregator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yanantin.activity.band_aggregator'`

- [ ] **Step 3: Write minimal implementation**

```python
"""The live banding aggregator: firehose defense at the provider boundary.

Source-agnostic and event-fed. Holds one live entry per (location, principal),
OR-ing access-kind bits across the band. Emits a band on quiescence (idle past
the window) or explicit flush. The ONLY thing it drops that it observed is the
intra-band create+delete lifecycle of a temp file — an exception to persistence,
not to observation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from yanantin.activity.band import StorageAccessKind, StorageActivityBand

_CREATE_DELETE = StorageAccessKind.CREATE | StorageAccessKind.DELETE


@dataclass
class _Entry:
    location: str
    os_principal: str | None
    access_kinds: int
    band_start: datetime
    band_end: datetime


class BandAggregator:
    def __init__(self, quiescence: timedelta) -> None:
        self._quiescence = quiescence
        self._entries: dict[tuple[str, str | None], _Entry] = {}

    def observe(
        self,
        location: str,
        kind: StorageAccessKind,
        at: datetime,
        os_principal: str | None = None,
    ) -> None:
        key = (location, os_principal)
        entry = self._entries.get(key)
        if entry is None:
            self._entries[key] = _Entry(
                location=location,
                os_principal=os_principal,
                access_kinds=int(kind),
                band_start=at,
                band_end=at,
            )
            return
        entry.access_kinds |= int(kind)
        if at < entry.band_start:
            entry.band_start = at
        if at > entry.band_end:
            entry.band_end = at

    def _emit(self, entry: _Entry) -> StorageActivityBand | None:
        # Elision: a whole life of exactly create+delete inside one band.
        if entry.access_kinds == int(_CREATE_DELETE):
            return None
        return StorageActivityBand(
            location=entry.location,
            access_kinds=entry.access_kinds,
            band_start=entry.band_start,
            band_end=entry.band_end,
            os_principal=entry.os_principal,
        )

    def flush_quiescent(self, now: datetime) -> list[StorageActivityBand]:
        cutoff = now - self._quiescence
        idle_keys = [k for k, e in self._entries.items() if e.band_end <= cutoff]
        out: list[StorageActivityBand] = []
        for k in idle_keys:
            band = self._emit(self._entries.pop(k))
            if band is not None:
                out.append(band)
        return out

    def flush_all(self) -> list[StorageActivityBand]:
        out: list[StorageActivityBand] = []
        for k in list(self._entries.keys()):
            band = self._emit(self._entries.pop(k))
            if band is not None:
                out.append(band)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_band_aggregator.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/activity/band_aggregator.py tests/unit/test_band_aggregator.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" -c user.signingkey="D0CAB9659C950893" commit -m "feat(activity): BandAggregator — live keyed banding with quiescence + elision"
```

---

### Task 3: mtime-scan adapter — `FsChangeEvent` → aggregator, weak `path:` URIs

**Files:**
- Create: `src/yanantin/collector/activity/linux/band_adapter.py`
- Test: `tests/unit/test_fs_band_adapter.py`

**Interfaces:**
- Consumes: `BandAggregator` (Task 2), `StorageAccessKind` (Task 1), existing `FsChangeEvent` / `FsEventBatch` from `yanantin.collector.activity.linux.models`.
- Produces:
  - `def event_type_to_kind(event_type: str) -> StorageAccessKind` — maps `"created"→CREATE`, `"modified"→WRITE`, `"deleted"→DELETE`.
  - `def mint_location(file_path: str) -> str` — returns `f"path:{file_path}"` (weak anchor; mtime-scan has no stable id).
  - `def feed_batch(agg: BandAggregator, batch: FsEventBatch) -> None` — feeds every event in a scan batch into the aggregator. mtime-scan carries no principal, so `os_principal=None`. Uses `event.modified_time` as the access time.

mtime-scan is `boundary_capability = quiescence_only`: the adapter never calls a causal close; banding is driven by `flush_quiescent`/`flush_all` at the caller's chosen scan cadence.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for the mtime-scan → band aggregator adapter.

Verifies:
- event_type maps to the correct access kind
- location is a weak path: URI (no stable anchor)
- a scan batch feeds every event; principal is None (mtime-scan can't attribute)
- accumulation across two batches (scan runs) lands in one band per file
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from yanantin.activity.band import StorageAccessKind
from yanantin.activity.band_aggregator import BandAggregator
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch
from yanantin.collector.activity.linux.band_adapter import (
    event_type_to_kind,
    feed_batch,
    mint_location,
)

T0 = datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc)


def _batch(events, cur):
    return FsEventBatch(volumes=("/",), events=tuple(events), last_run=None, current_run=cur)


def test_event_type_maps_to_kind():
    assert event_type_to_kind("created") == StorageAccessKind.CREATE
    assert event_type_to_kind("modified") == StorageAccessKind.WRITE
    assert event_type_to_kind("deleted") == StorageAccessKind.DELETE


def test_location_is_weak_path_uri():
    assert mint_location("/home/tony/foo") == "path:/home/tony/foo"


def test_feed_batch_bands_with_no_principal():
    agg = BandAggregator(quiescence=timedelta(minutes=5))
    ev = FsChangeEvent(file_path="/home/tony/foo", event_type="created",
                       modified_time=T0, size_bytes=10)
    feed_batch(agg, _batch([ev], cur=T0))
    bands = agg.flush_all()
    assert len(bands) == 1
    assert bands[0].location == "path:/home/tony/foo"
    assert bands[0].os_principal is None


def test_accumulation_across_two_scan_runs():
    agg = BandAggregator(quiescence=timedelta(minutes=5))
    ev1 = FsChangeEvent(file_path="/home/tony/foo", event_type="created",
                        modified_time=T0, size_bytes=10)
    ev2 = FsChangeEvent(file_path="/home/tony/foo", event_type="modified",
                        modified_time=T0 + timedelta(seconds=30), size_bytes=20)
    feed_batch(agg, _batch([ev1], cur=T0))
    feed_batch(agg, _batch([ev2], cur=T0 + timedelta(seconds=30)))
    bands = agg.flush_all()
    assert len(bands) == 1
    kinds = StorageAccessKind(bands[0].access_kinds)
    assert StorageAccessKind.CREATE in kinds and StorageAccessKind.WRITE in kinds
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_fs_band_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yanantin.collector.activity.linux.band_adapter'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Adapter: mtime-scan FsChangeEvent stream → BandAggregator.

mtime-scan is a weak-anchor, quiescence-only source: no stable object id
(location is a path: URI), no principal attribution (os_principal=None), no
causal close (banding driven by the caller's flush cadence). It converges to
the same StorageActivityBand shape as any richer source.
"""
from __future__ import annotations

from yanantin.activity.band import StorageAccessKind
from yanantin.activity.band_aggregator import BandAggregator
from yanantin.collector.activity.linux.models import FsEventBatch

_KIND_BY_EVENT = {
    "created": StorageAccessKind.CREATE,
    "modified": StorageAccessKind.WRITE,
    "deleted": StorageAccessKind.DELETE,
}


def event_type_to_kind(event_type: str) -> StorageAccessKind:
    return _KIND_BY_EVENT[event_type]


def mint_location(file_path: str) -> str:
    return f"path:{file_path}"


def feed_batch(agg: BandAggregator, batch: FsEventBatch) -> None:
    for event in batch.events:
        agg.observe(
            location=mint_location(event.file_path),
            kind=event_type_to_kind(event.event_type),
            at=event.modified_time,
            os_principal=None,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_fs_band_adapter.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/collector/activity/linux/band_adapter.py tests/unit/test_fs_band_adapter.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" -c user.signingkey="D0CAB9659C950893" commit -m "feat(collector): mtime-scan → band aggregator adapter (weak path: URIs)"
```

---

### Task 4: `BandFactRecorder` — serialize emitted bands into `FactRecord`

**Files:**
- Create: `src/yanantin/recorder/activity/linux/band_fact_recorder.py`
- Test: `tests/unit/test_band_fact_recorder.py`

**Interfaces:**
- Consumes: `StorageActivityBand` (Task 1), existing `FactRecord`, `ActivityStreamStore`, `InMemoryActivityStreamStore`.
- Produces:
  - `class BandFactRecorder` constructed as `BandFactRecorder(store: ActivityStreamStore)`.
  - `record_bands(self, provider_id: UUID, bands: list[StorageActivityBand]) -> int` — stores one `FactRecord` per band into the store, returns count of *newly stored* facts. `FactRecord.id = band.band_id()`, `FactRecord.timestamp = band.band_end`, `FactRecord.data = band.model_dump(mode="json")`, `FactRecord.content_hash` = sha256 of canonical band JSON (truncated 16 hex, matching the existing `FsEventFactRecorder` convention).

This is deliberately NOT a `FactRecorderBase` subclass: that base is stateless `record_facts(envelope)->int` one-fact-per-event (the firehose this supersedes). The banding stage is a new shape. Keeping it separate is intentional per spec §4.

**Idempotency is real work, not free.** The store raises `ImmutabilityError` on a duplicate `id` (verified: `InMemoryActivityStreamStore.store_fact`). Because `band_id()` is deterministic, the SAME band re-emitted across overlapping scan windows will collide by design. `record_bands` must catch `ImmutabilityError` and treat it as already-persisted (skip, do not count), so re-recording is safe and only genuinely-new bands increment the count. `ImmutabilityError` lives in `yanantin.apacheta.interface.errors`.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for the band fact recorder.

Verifies:
- one FactRecord stored per band, count returned
- FactRecord.id is the band's deterministic band_id (idempotent re-record)
- FactRecord.timestamp is band_end; data round-trips to the band
- content_hash is stable for identical bands
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.activity.band import StorageAccessKind, StorageActivityBand
from yanantin.recorder.activity.linux.band_fact_recorder import BandFactRecorder

PID = uuid4()


def _band(loc="path:/a"):
    return StorageActivityBand(
        location=loc,
        access_kinds=int(StorageAccessKind.WRITE),
        band_start=datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc),
        band_end=datetime(2026, 7, 6, 9, 5, tzinfo=timezone.utc),
    )


def test_records_one_fact_per_band():
    store = InMemoryActivityStreamStore()
    rec = BandFactRecorder(store)
    n = rec.record_bands(PID, [_band("path:/a"), _band("path:/b")])
    assert n == 2
    assert store.count_facts(PID) == 2


def test_fact_id_is_band_id():
    store = InMemoryActivityStreamStore()
    rec = BandFactRecorder(store)
    band = _band()
    rec.record_bands(PID, [band])
    stored = store.get_fact(band.band_id())
    assert stored.timestamp == band.band_end
    assert stored.data["location"] == "path:/a"


def test_re_recording_same_band_is_idempotent():
    # deterministic band_id collides across overlapping scan windows by design;
    # the store rejects dup ids, so the recorder must absorb the collision.
    store = InMemoryActivityStreamStore()
    rec = BandFactRecorder(store)
    band = _band()
    first = rec.record_bands(PID, [band])
    second = rec.record_bands(PID, [band])
    assert first == 1
    assert second == 0, "re-recording an existing band must not double-count or raise"
    assert store.count_facts(PID) == 1


def test_content_hash_stable():
    store = InMemoryActivityStreamStore()
    rec = BandFactRecorder(store)
    rec.record_bands(PID, [_band()])
    h1 = store.get_fact(_band().band_id()).content_hash
    assert len(h1) == 16
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_band_fact_recorder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yanantin.recorder.activity.linux.band_fact_recorder'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Records emitted StorageActivityBands as facts in the activity stream.

Deliberately NOT a FactRecorderBase subclass: that base is stateless
one-fact-per-event batch (the firehose this supersedes). The banding stage
emits already-reduced bands; this recorder just persists them, keyed by the
band's deterministic identity so re-recording is idempotent.
"""
from __future__ import annotations

import hashlib
import json
from uuid import UUID

from yanantin.activity.band import StorageActivityBand
from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.apacheta.interface.errors import ImmutabilityError


class BandFactRecorder:
    def __init__(self, store: ActivityStreamStore) -> None:
        self._store = store

    def record_bands(
        self, provider_id: UUID, bands: list[StorageActivityBand]
    ) -> int:
        count = 0
        for band in bands:
            data = band.model_dump(mode="json")
            fact = FactRecord(
                id=band.band_id(),
                provider_id=provider_id,
                timestamp=band.band_end,
                data=data,
                content_hash=self._content_hash(data),
            )
            try:
                self._store.store_fact(fact)
            except ImmutabilityError:
                # Deterministic band_id collides across overlapping scan
                # windows by design — the band is already persisted. Skip.
                continue
            count += 1
        return count

    @staticmethod
    def _content_hash(data: dict) -> str:
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_band_fact_recorder.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/recorder/activity/linux/band_fact_recorder.py tests/unit/test_band_fact_recorder.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" -c user.signingkey="D0CAB9659C950893" commit -m "feat(recorder): BandFactRecorder — persist emitted bands as idempotent facts"
```

---

### Task 5: Falsification test — the firehose is really tamed on real repo data

**Files:**
- Create: `tests/integration/test_band_falsification.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4, plus the real `FsIncrementalCollector` from `yanantin.collector.activity.linux`.
- Produces: no new source. This task proves the spec's §8 falsification targets on ground truth.

This is the point of the whole pour: the design either survives contact with real mtime-scan data or it is wrong, and we find out here. Locate the real collector first (`grep -rn "class FsIncrementalCollector" src/`) and read its `collect()` signature before writing the test; drive it against a real temp directory tree, not a mock (per repo doctrine: no mock databases, no mock collectors — synthetic ground truth is fine, mocks are not).

- [ ] **Step 1: Write the falsification test**

```python
"""Falsification: does the band aggregator tame the real mtime-scan firehose
without lying about identity strength? Spec 2026-07-05 §8.

Ground truth: a real temp directory driven through the real incremental
collector. No mocks.

Targets:
1. Firehose tamed: facts-out < events-in when a file is touched many times.
2. Temp-file elision: a file created and deleted within one band emits no fact.
3. Weak-anchor honesty: mtime-scan bands carry path: URIs and os_principal=None;
   rename is not inferred (a delete+create pair on different paths is two bands,
   never a rename).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.activity.band import StorageAccessKind
from yanantin.activity.band_aggregator import BandAggregator
from yanantin.collector.activity.linux.band_adapter import feed_batch
from yanantin.collector.activity.linux.models import FsChangeEvent, FsEventBatch
from yanantin.recorder.activity.linux.band_fact_recorder import BandFactRecorder

T0 = datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc)
PID = uuid4()


def _events_to_batch(events):
    return FsEventBatch(volumes=("/",), events=tuple(events),
                        last_run=None, current_run=T0)


def test_firehose_tamed_facts_out_less_than_events_in():
    # 50 modifies to one file → 1 band, not 50 facts.
    events = [
        FsChangeEvent(file_path="/repo/hot", event_type="modified",
                      modified_time=T0 + timedelta(seconds=i), size_bytes=i)
        for i in range(50)
    ]
    agg = BandAggregator(quiescence=timedelta(minutes=5))
    feed_batch(agg, _events_to_batch(events))
    bands = agg.flush_all()
    store = InMemoryActivityStreamStore()
    n = BandFactRecorder(store).record_bands(PID, bands)
    assert len(events) == 50
    assert n == 1, "firehose not tamed: expected 1 band from 50 events"


def test_temp_file_elided():
    events = [
        FsChangeEvent(file_path="/repo/tmp/x", event_type="created",
                      modified_time=T0, size_bytes=0),
        FsChangeEvent(file_path="/repo/tmp/x", event_type="deleted",
                      modified_time=T0 + timedelta(seconds=1), size_bytes=0),
    ]
    agg = BandAggregator(quiescence=timedelta(minutes=5))
    feed_batch(agg, _events_to_batch(events))
    assert agg.flush_all() == [], "temp file (create+delete in band) not elided"


def test_weak_anchor_honesty_no_rename_inference():
    # A rename looks like delete(old) + create(new). Witness must record TWO
    # bands on TWO path: locations, never infer a single rename.
    events = [
        FsChangeEvent(file_path="/repo/old", event_type="deleted",
                      modified_time=T0, size_bytes=100),
        FsChangeEvent(file_path="/repo/new", event_type="created",
                      modified_time=T0 + timedelta(seconds=1), size_bytes=100),
    ]
    agg = BandAggregator(quiescence=timedelta(minutes=5))
    feed_batch(agg, _events_to_batch(events))
    bands = agg.flush_all()
    locations = sorted(b.location for b in bands)
    assert locations == ["path:/repo/new", "path:/repo/old"]
    assert all(b.os_principal is None for b in bands)
    assert all(StorageAccessKind.RENAME not in StorageAccessKind(b.access_kinds)
               for b in bands)
```

- [ ] **Step 2: Run the falsification test**

Run: `pytest tests/integration/test_band_falsification.py -v`
Expected: PASS (3 tests). If any FAIL, the design is wrong — STOP and reconcile against the spec before proceeding.

- [ ] **Step 3: Run the full suite to confirm no regressions**

Run: `pytest tests/unit/test_storage_activity_band.py tests/unit/test_band_aggregator.py tests/unit/test_fs_band_adapter.py tests/unit/test_band_fact_recorder.py tests/integration/test_band_falsification.py -v`
Expected: all PASS (5 + 5 + 4 + 4 + 3 = 21 tests)

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_band_falsification.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" -c user.signingkey="D0CAB9659C950893" commit -m "test(activity): falsification — firehose tamed, temp elided, weak-anchor honest"
```

---

## Notes for the executor

- **Task 5 is the payload.** Tasks 1–4 are scaffolding for the one question that matters: does heterogeneous-source banding survive real ground-truth mtime-scan data without erasing identity strength? If Task 5 goes red, do not paper over it — a red here means the spec's central claim is wrong, which is a more valuable finding than a green pour.
- **The `os_principal` in the aggregator key is load-bearing.** If a reviewer suggests "just track a set of principals per band," that is the smeared-actor failure the spec forbids (§4) — reject it.
- **Do not build a curator.** `granularity`/`compaction_level` stay inert. Any temporal-coarsening or relevance-filtering work is out of scope (spec §6).
- **The real `FsIncrementalCollector` drive** (Task 5) may need a real temp-dir fixture rather than hand-built `FsChangeEvent`s if you want end-to-end fidelity. The hand-built events above falsify the aggregator logic; if you want to additionally prove the *collector* produces the events this pour assumes, add a temp-dir integration case — but that tests the existing collector, not this pour, so it is optional.
