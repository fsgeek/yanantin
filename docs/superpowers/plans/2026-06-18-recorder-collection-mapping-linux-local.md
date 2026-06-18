# Recorder → Collection Mapping (linux-local vertical) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the linux-local-storage recorder to `core.Registrar` so it registers itself + its collector (by proxy), declares a `contributes_to` mapping in the registrar's open tail, and contributes provenance-bearing documents into a registrar-owned `Objects` (doc) collection and `Relationships` (edge) collection — making C0 stacking test #7 live with real (or synthetic) recorder data.

**Architecture:** The mechanism is one declared property (`contributes_to`) carried in the registration record's existing `extra="allow"` tail, plus one coding branch in the **recorder** (`well_known` → write through an owned collection; `dynamic` → mint own). The registrar stays **opaque** to `contributes_to` (no registrar change for the mapping itself). The registrar gains ONE capability it lacks today: owning an **edge** collection alongside its document collection (Case 2: one recorder → `Objects` doc + `Relationships` edge). The contributed shape is a **thin provenance-bearing document** — NOT the full uniform StorageObject (#17, explicitly out of scope); field names are not frozen by the spec, so we choose the minimal shape whose `source` resolves to a registered `provider_id`. The existing tensor write path (`FilesystemRecorder.record()` → `store_tensor`) is **left untouched**; this adds a parallel contribution capability.

**Tech Stack:** Python 3.14, uv, pydantic v2, ArangoDB (python-arango `StandardDatabase`), pytest against live `apacheta_test`.

## Global Constraints

- Python 3.14, uv-managed (`uv run pytest ...`). One line each, copied from project memory/CLAUDE.md:
- **No mock databases for storage behavior** — tests run against live `apacheta_test` (creds in `~/.yanantin/config/db.ini`, loaded by `ApachetaDBConfig`). Mocking for error-discrimination/control-flow only.
- **Builder/tester separation is CI-enforced** (`.github/workflows/separation.yml`). **Test files in this plan are authored by GPT-5 Codex**, not the builder. The builder writes implementation to make Codex's tests pass. Each task names the Codex prompt.
- **Red-bar floor must actually run.** Do not turn any existing red-bar feature-gate green as a side effect (esp. `tests/red_bar/test_uniform_storage_object.py` — #17 stays red; this pour does NOT build the uniform StorageObject).
- **Fail-stop, inherited from `core.Registrar`:** no storage ⇒ raise, never a false-empty. The recorder (not the registrar) enforces the mapping: a `well_known` target with no owning collection is an error the recorder raises (no silent mint).
- **Obfuscator-correct at rest:** field NAMES obfuscated, values not. Edge `_from`/`_to` are reference values, pass through unchanged; canonical-key form (`str(UUID)`, hyphenated) is mandatory or traversal dangles.
- **Registrar stays opaque to `contributes_to`:** it stores/returns it as open-tail extra; it never parses or branches on it. A red-bar-style test asserts the round-trip-unchanged property.
- **AI commits** use per-command git config overrides with the Yanantin signing identity (`1E416B1FB63AF88179EE0F38D0CAB9659C950893` / `Yanantin AI (Claude Opus) <yanantin@wamason.com>`), NOT repo-level config. Commit-message footer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. After the final task, sweep the trailing OTS stamp(s) per the OTS rule.

---

## File Structure

**New files:**
- `src/yanantin/recorder/storage/local/linux/registration.py` — the contribution-mapping leaf: `LinuxStorageRegistration` (the recorder-side object that registers via `core.Registrar`, declares `contributes_to`, and contributes thin provenance docs + relationship edges). Modeled on Indaleko's leaf decomposition (mechanism-in-base, `normalize_*` + `find_*` in the leaf).
- `src/yanantin/core/contribution.py` — the small shared shape vocabulary: `ContributionTarget` (the `{name, kind, naming}` mapping entry) + `ContributedRecord` (the thin provenance-bearing doc: `source` → provider, `timestamp`, `raw` opaque payload, open tail). Lives in `core/` because it is the contract both recorder and CLI read; it is NOT the #17 StorageObject.
- `tests/integration/test_recorder_collection_mapping.py` — the 8 spec tests (Codex-authored), live `apacheta_test`.
- `tests/red_bar/test_registrar_opacity.py` — the separation guard: registrar round-trips `contributes_to` unchanged, never branches on it (Codex-authored).

**Modified files:**
- `src/yanantin/core/registration.py` — add edge-owned-collection capability to `Registrar` (`owned_edge_collection` param + `contribute_edge`/`list_edge_contributions`). This is the ONE registrar change, and it is about owning an edge collection (a storage capability), NOT about interpreting `contributes_to` (which stays opaque).

**Untouched (explicitly):**
- `src/yanantin/recorder/storage/local/linux/recorder.py` — `FilesystemRecorder.record()` → `store_tensor` stays as-is.
- `tests/red_bar/test_uniform_storage_object.py` — stays red (#17).

---

### Task 1: `ContributionTarget` + `ContributedRecord` shapes

**Files:**
- Create: `src/yanantin/core/contribution.py`
- Test: `tests/integration/test_recorder_collection_mapping.py` (Test 1 of the suite — Case-1 empty mapping uses these shapes)

**Interfaces:**
- Consumes: nothing (leaf shape module).
- Produces:
  - `ContributionTarget(BaseModel, frozen=True, extra="forbid")` with fields `name: str`, `kind: Literal["doc", "edge"]`, `naming: Literal["well_known", "dynamic"]`. Method `model_dump(mode="json")` for storage in the open tail.
  - `ContributedRecord(BaseModel, frozen=True, extra="allow")` with typed spine `source: UUID` (the registered provider_id), `timestamp: datetime` (default UTC now), `raw: dict` (opaque save-everything payload). Open tail carries the normalized file fields. Method `to_contribution_fields() -> dict` returning the `**fields` dict for `Registrar.contribute` (json-mode, `source` rendered `str(UUID)`).

**Codex test-author prompt (for the Case-1 slice of the suite):**
> Write a pytest test in `tests/integration/test_recorder_collection_mapping.py` named `test_collector_mapping_is_empty`. Import `ContributionTarget` and `ContributedRecord` from `yanantin.core.contribution`. Assert: (a) a `ContributionTarget(name="X", kind="doc", naming="well_known")` round-trips through `.model_dump(mode="json")` to `{"name":"X","kind":"doc","naming":"well_known"}`; (b) `ContributionTarget` rejects an unknown `kind` value (pydantic ValidationError); (c) a `ContributedRecord(source=<some uuid4>, raw={"a":1})` has a populated `timestamp`, and `.to_contribution_fields()` renders `source` as the canonical str(UUID) and includes `raw`; (d) `ContributedRecord` ACCEPTS an extra field `path="/data/x"` (extra="allow") and keeps it in `to_contribution_fields()`. Do not touch the database. `< /dev/null` on the codex invocation.

- [ ] **Step 1: Codex authors the test** (prompt above). Verify the file exists and the test names match.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py::test_collector_mapping_is_empty -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'yanantin.core.contribution'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/yanantin/core/contribution.py
"""The contribution-mapping vocabulary: how a recorder declares WHERE its
output lands (ContributionTarget) and the thin provenance-bearing shape it
contributes (ContributedRecord). NOT the #17 uniform StorageObject — that is
a separate, deferred pour. Field names are deliberately minimal; the spec
does not freeze them (2026-06-17-recorder-collection-mapping-design.md)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContributionTarget(BaseModel):
    """One entry in a recorder's `contributes_to` declaration: a collection
    its output lands in. `kind` doc vs edge; `naming` well_known (attach to a
    shared owned collection) vs dynamic (mint own). The registrar stores this
    OPAQUELY in its open tail; only the recorder acts on it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    kind: Literal["doc", "edge"]
    naming: Literal["well_known", "dynamic"]


class ContributedRecord(BaseModel):
    """A thin provenance-bearing document a recorder contributes into an owned
    collection. The typed spine resolves provenance to a registered provider
    (`source`); `raw` is the opaque save-everything payload; the open tail
    carries normalized fields. This embeds provenance whose source resolves to
    a registered provider_id — the spec's frozen requirement — without building
    the uniform StorageObject (#17)."""

    model_config = ConfigDict(frozen=True, extra="allow")

    source: UUID
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw: dict = Field(default_factory=dict)

    def to_contribution_fields(self) -> dict:
        """Render to the **fields dict for Registrar.contribute: json mode so
        source/timestamp are storage-ready, open-tail fields included."""
        return self.model_dump(mode="json")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py::test_collector_mapping_is_empty -v`
Expected: PASS

- [ ] **Step 5: Commit** (Yanantin-signed)

```bash
git add src/yanantin/core/contribution.py tests/integration/test_recorder_collection_mapping.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "feat(core): ContributionTarget + thin ContributedRecord shapes (#30 Task 1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `Registrar` owns an edge collection (the ONE registrar change)

**Files:**
- Modify: `src/yanantin/core/registration.py` (add `owned_edge_collection` param to `__init__`; add `_ensure_edge_collection`, `contribute_edge`, `list_edge_contributions`)
- Test: `tests/integration/test_recorder_collection_mapping.py` (Test: recorder declares N targets / edge collection is edge-typed)

**Interfaces:**
- Consumes: existing `Registrar.__init__(db, catalog_collection, name, description, obfuscator=None, owned_collection=None)`; existing `_ensure_collection`, `contribute`, obfuscator.
- Produces:
  - `Registrar.__init__(..., owned_edge_collection: str | None = None)` — when given, ensures an **edge** collection (`create_collection(edge=True)`) under the obfuscated name, stored as `self._owned_edge_name`.
  - `Registrar.contribute_edge(contributor_id: UUID, from_ref: str, to_ref: str, relation_type: str, **fields) -> dict` — inserts an edge doc (`_from`/`_to` canonical, `contributor_id` field) into the owned edge collection via the obfuscator. Raises if no edge collection is owned.
  - `Registrar.list_edge_contributions(contributor_id: UUID | None = None) -> list[dict]` — same filter-by-provider shape as `list_contributions`, over the edge collection.
  - `Registrar.owned_collection_name` (property) → the obfuscated owned doc-collection name (`self._owned_name`), and `Registrar.owns_owned_collection` (property, bool) → True iff this registrar owns a doc collection DISTINCT from its catalog. Public accessors so a recorder building canonical edge endpoints does NOT reach into `_owned_name`/`_catalog_name` (spec line 197: "resolving that handle is an implementation-plan detail" — make it a public seam, not a private-attr reach).

**Codex test-author prompt:**
> In `tests/integration/test_recorder_collection_mapping.py`, write `test_registrar_owns_doc_and_edge_collections(live_db)` using the existing `ApachetaDBConfig().get_test_credentials()` fixture pattern (see `tests/integration/test_core_registration.py` for the live_db fixture and cleanup idiom — copy it). Create a `Registrar` with both `owned_collection="Objects_t<unique>"` and `owned_edge_collection="Relationships_t<unique>"`. Assert via the python-arango driver that the Objects collection exists and is a DOCUMENT collection (`collection.properties()["type"] == 2`) and the Relationships collection exists and is an EDGE collection (`type == 3`). Then `contribute_edge(provider, from_ref="entities/<uuid>", to_ref="records/<uuid>", relation_type="contains")` and assert `list_edge_contributions(provider)` returns exactly one edge whose `_from`/`_to` survived. Clean up all three collections in teardown. No mocks. `< /dev/null`.

- [ ] **Step 1: Codex authors the test** (prompt above).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py::test_registrar_owns_doc_and_edge_collections -v`
Expected: FAIL — `__init__() got an unexpected keyword argument 'owned_edge_collection'`

- [ ] **Step 3: Write minimal implementation**

In `src/yanantin/core/registration.py`, extend `__init__` (after the existing owned-collection block, around line 104):

```python
        # Optional OWNED EDGE collection (Case 2: one recorder → Objects doc
        # AND Relationships edge). Edge collections need create_collection(
        # edge=True) so native OUTBOUND traversal works on _from/_to — the
        # generic doc path cannot host edges (mirrors arango.py
        # _provenance_edge_collection). None ⇒ this registrar owns no edges.
        self._owned_edge_name = None
        if owned_edge_collection is not None:
            self._owned_edge_name = self._obfuscator.collection_name(
                owned_edge_collection
            )
            self._ensure_edge_collection(self._owned_edge_name)
```

Add the param to the signature: `owned_edge_collection: str | None = None,`.

Add the methods after `_ensure_collection`:

```python
    def _ensure_edge_collection(self, name: str):
        """Ensure an EDGE collection exists under its obfuscated name. Edge
        type is load-bearing: native graph traversal requires create_collection
        (edge=True). Fail-stop inherited from the driver."""
        if not self._db.has_collection(name):
            self._db.create_collection(name, edge=True)
        return self._db.collection(name)

    @property
    def owned_collection_name(self) -> str:
        """The obfuscated owned doc-collection name. A recorder writing through
        this registrar uses it to build canonical edge endpoints WITHOUT
        reaching into private attrs (the spec's 'resolve the handle' seam)."""
        return self._owned_name

    @property
    def owns_owned_collection(self) -> bool:
        """True iff this registrar owns a doc collection distinct from its
        catalog (i.e. it can host shared-collection contributions)."""
        return self._owned_name != self._catalog_name

    @property
    def owns_edge_collection(self) -> bool:
        """True iff this registrar owns an edge collection."""
        return self._owned_edge_name is not None
```

Add after `list_contributions`:

```python
    def contribute_edge(
        self,
        contributor_id: UUID,
        from_ref: str,
        to_ref: str,
        relation_type: str,
        **fields,
    ) -> dict:
        """Write an edge into the owned edge collection on behalf of a
        registrant. _from/_to are reference VALUES (canonical collection/key
        form) — they pass through the obfuscator unchanged; only labels map.
        Raises if this registrar owns no edge collection (fail-stop, not a
        silent doc-insert)."""
        if self._owned_edge_name is None:
            raise ValueError(
                "this registrar owns no edge collection; "
                "construct it with owned_edge_collection=..."
            )
        doc = {
            "_from": from_ref,
            "_to": to_ref,
            "relation_type": relation_type,
            "contributor_id": str(contributor_id),
            **fields,
        }
        self._db.collection(self._owned_edge_name).insert(
            self._obfuscator.obfuscate_document(doc)
        )
        return doc

    def list_edge_contributions(
        self, contributor_id: UUID | None = None
    ) -> list[dict]:
        """Edges in the owned edge collection, optionally filtered by provider.
        _from/_to are restored verbatim (reference values, not labels)."""
        if self._owned_edge_name is None:
            raise ValueError("this registrar owns no edge collection")
        if contributor_id is None:
            cursor = self._db.aql.execute(
                "FOR d IN @@coll RETURN d",
                bind_vars={"@coll": self._owned_edge_name},
            )
        else:
            id_field = self._obfuscator.field_name("contributor_id")
            cursor = self._db.aql.execute(
                "FOR d IN @@coll FILTER d[@field] == @cid RETURN d",
                bind_vars={
                    "@coll": self._owned_edge_name,
                    "field": id_field,
                    "cid": str(contributor_id),
                },
            )
        out = []
        for doc in cursor:
            readable = self._obfuscator.deobfuscate_document(doc)
            clean = {k: v for k, v in readable.items() if not k.startswith("_")}
            clean["_from"] = readable["_from"]
            clean["_to"] = readable["_to"]
            out.append(clean)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py::test_registrar_owns_doc_and_edge_collections -v`
Expected: PASS

- [ ] **Step 5: Run the full existing registration suite — no regression**

Run: `uv run pytest tests/integration/test_core_registration.py -v`
Expected: PASS (all existing stacking/contribution tests still green — the edge param is additive, default None)

- [ ] **Step 6: Commit** (Yanantin-signed, message `feat(core): Registrar can own an edge collection (Relationships) — #30 Task 2`)

---

### Task 3: Registrar opacity red-bar (the separation guard)

**Files:**
- Create: `tests/red_bar/test_registrar_opacity.py`
- Test: itself (this task's deliverable IS a guard test that must pass — proving the registrar never interprets `contributes_to`)

**Interfaces:**
- Consumes: `Registrar.register(..., **extra)` and `lookup_by_identifier` from Task 2's registration.py (unchanged register path).
- Produces: a passing guard. If a future change makes the registrar branch on `contributes_to`, this test goes red.

**Codex test-author prompt:**
> Write `tests/red_bar/test_registrar_opacity.py::test_registrar_round_trips_contributes_to_unchanged(live_db)`. Register a registrant with `contributes_to=[{"name":"Objects","kind":"doc","naming":"well_known"},{"name":"Relationships","kind":"edge","naming":"well_known"}]` passed as an **extra** kwarg to `Registrar.register`. Look it up via `lookup_by_identifier` and assert the returned `RegistrantRecord`'s `contributes_to` (read from `.model_extra` or attribute) equals the input list EXACTLY — same order, same dict contents — proving the registrar stored it opaquely and did not normalize, reorder, or interpret it. Second assertion: grep the registrar SOURCE (`src/yanantin/core/registration.py`) text for the literal `contributes_to`, `well_known`, and `dynamic` and assert NONE appear — the registrar code must not know these tokens exist (the separation made structural). Use the live_db fixture; clean up the catalog collection. `< /dev/null`.

- [ ] **Step 1: Codex authors the guard** (prompt above).

- [ ] **Step 2: Run it — verify it PASSES** (this guard should be green now; it asserts the property Task 2 preserved)

Run: `uv run pytest tests/red_bar/test_registrar_opacity.py -v`
Expected: PASS. (If it fails on the source-grep, the registrar leaked mapping vocabulary — fix registration.py, do not weaken the test.)

- [ ] **Step 3: Commit** (Yanantin-signed, `test(red_bar): registrar stays opaque to contributes_to — #30 Task 3`)

---

### Task 4: `LinuxStorageRegistration` — register + declare mapping (Case 2)

**Files:**
- Create: `src/yanantin/recorder/storage/local/linux/registration.py`
- Test: `tests/integration/test_recorder_collection_mapping.py` (Test: recorder declares N targets, end-to-end visibility skeleton)

**Interfaces:**
- Consumes: `Registrar` (Task 2), `ContributionTarget`/`ContributedRecord` (Task 1), `LinuxFilesystemCollector` / `SyntheticFilesystemCollector` (existing, for `get_provider_id`/`get_description`), `FilesystemRecorder.get_recorder_id`/`get_description` (existing).
- Produces:
  - `STORAGE_OBJECTS = "Objects"`, `STORAGE_RELATIONSHIPS = "Relationships"` (semantic names).
  - `LinuxStorageRegistration` with:
    - `__init__(self, registrar: Registrar, collector: CollectorBase)` — holds the registrar (which must own `Objects`/`Relationships`) and the collector to declare by proxy.
    - `CONTRIBUTES_TO: list[ContributionTarget]` (class attr) = `[{Objects, doc, well_known}, {Relationships, edge, well_known}]`.
    - `register(self) -> tuple[RegistrantRecord, RegistrantRecord]` — registers the recorder (kind `"provider"`, `contributes_to=[t.model_dump() ...]` in extra) AND the collector by proxy (kind `"provider"`, `contributes_to=[]`). Returns both records.

**Codex test-author prompt:**
> In `tests/integration/test_recorder_collection_mapping.py`, write `test_recorder_declares_two_well_known_targets(live_db)`. Build a `Registrar` owning `Objects_t<uniq>` (doc) and `Relationships_t<uniq>` (edge). Construct `LinuxStorageRegistration(registrar, SyntheticFilesystemCollector(seed=7))` and call `.register()`. Assert: (a) two registrants now appear in the catalog (the recorder and the collector-by-proxy); (b) the recorder's record carries `contributes_to` with exactly two entries — one `{kind:"doc", naming:"well_known"}` and one `{kind:"edge", naming:"well_known"}`; (c) the collector-by-proxy's `contributes_to == []`. Look the records up via the registrar, not the in-memory return value, to prove they persisted. Clean up. `< /dev/null`.

- [ ] **Step 1: Codex authors the test.**

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py::test_recorder_declares_two_well_known_targets -v`
Expected: FAIL — `ModuleNotFoundError: yanantin.recorder.storage.local.linux.registration`

- [ ] **Step 3: Write minimal implementation**

```python
# src/yanantin/recorder/storage/local/linux/registration.py
"""Linux-local-storage recorder ↔ registration leaf. The recorder registers
itself AND its collector (by proxy — the collector may have no DB access), and
declares its contributes_to mapping into the registrar's open tail. Mechanism
lives in core (Registrar); this leaf supplies the linux-storage specifics, the
way Indaleko's storage recorders carry normalize_*/find_* over a base."""

from __future__ import annotations

from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.collector._collector_base import CollectorBase
from yanantin.core.contribution import ContributionTarget
from yanantin.core.registration import Registrar, RegistrantRecord

STORAGE_OBJECTS = "Objects"
STORAGE_RELATIONSHIPS = "Relationships"

RECORDER_ID = uuid5(NAMESPACE_DNS, "yanantin.recorder.filesystem")


class LinuxStorageRegistration:
    """Registers the linux-local-storage recorder + its collector, declaring a
    two-target well_known mapping (Objects doc + Relationships edge)."""

    CONTRIBUTES_TO: list[ContributionTarget] = [
        ContributionTarget(name=STORAGE_OBJECTS, kind="doc", naming="well_known"),
        ContributionTarget(
            name=STORAGE_RELATIONSHIPS, kind="edge", naming="well_known"
        ),
    ]

    def __init__(self, registrar: Registrar, collector: CollectorBase) -> None:
        self._registrar = registrar
        self._collector = collector

    @property
    def recorder_id(self) -> UUID:
        return RECORDER_ID

    def register(self) -> tuple[RegistrantRecord, RegistrantRecord]:
        """Register recorder (with the mapping) and collector (by proxy, empty
        mapping). The collector supplies its identity; the recorder declares."""
        recorder_rec = self._registrar.register(
            registrant_id=RECORDER_ID,
            registrant_name="linux-local-storage recorder",
            registrant_kind="provider",
            description="records linux filesystem snapshots into Objects",
            contributes_to=[t.model_dump(mode="json") for t in self.CONTRIBUTES_TO],
        )
        collector_rec = self._registrar.register(
            registrant_id=self._collector.get_provider_id(),
            registrant_name="linux-local-storage collector",
            registrant_kind="provider",
            description=self._collector.get_description(),
            contributes_to=[],
        )
        return recorder_rec, collector_rec
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py::test_recorder_declares_two_well_known_targets -v`
Expected: PASS

- [ ] **Step 5: Commit** (Yanantin-signed, `feat(recorder): LinuxStorageRegistration declares Objects+Relationships mapping — #30 Task 4`)

---

### Task 5: Contribute thin provenance docs + relationship edges (the data path)

**Files:**
- Modify: `src/yanantin/recorder/storage/local/linux/registration.py` (add `contribute_snapshot`)
- Test: `tests/integration/test_recorder_collection_mapping.py` (Tests: provenance round-trips; real-vs-synthetic interchangeability)

**Interfaces:**
- Consumes: `Registrar.contribute` + `Registrar.contribute_edge` (Task 2), `ContributedRecord` (Task 1), `FilesystemSnapshot`/`FileEntryData` (existing collector models), `RECORDER_ID` (Task 4).
- Produces:
  - `LinuxStorageRegistration.contribute_snapshot(self, snapshot: FilesystemSnapshot, provider_id: UUID) -> int` — for each `FileEntryData` in the snapshot: build a `ContributedRecord(source=provider_id, raw=<the entry as dict>, **normalized_fields)`, `registrar.contribute(provider_id, **rec.to_contribution_fields())` into `Objects`; and write a `Relationships` edge (recorder→object, canonical `str(UUID)` endpoints) via `registrar.contribute_edge`. Returns the count of objects contributed.

**Codex test-author prompt:**
> In `tests/integration/test_recorder_collection_mapping.py`, write two tests. (1) `test_contributed_record_provenance_round_trips(live_db)`: register + `contribute_snapshot` from `SyntheticFilesystemCollector(seed=7).collect()`; assert `registrar.list_contributions(provider_id)` returns N docs each whose `source` field equals `str(provider_id)` (provenance resolves to the registered provider, not asserted), and `raw` is present and non-empty. Assert `list_edge_contributions(RECORDER_ID)` returns N edges whose `_to` start with the Objects-key form and resolve via an OUTBOUND AQL traversal from the recorder node (model on `tests/integration/test_machine_and_edges.py::test_filesystem_edges_resolve_in_db`). (2) `test_real_and_synthetic_interchangeable(live_db)`: run `contribute_snapshot` once from a `LinuxFilesystemCollector(root_path=tmp_path)` over a couple of real temp files and once from the synthetic twin; assert BOTH produce schema-valid docs in Objects (same field shape), differing only in values. Clean up all collections. No mocks. `< /dev/null`.

- [ ] **Step 1: Codex authors both tests.**

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py -k "provenance_round_trips or interchangeable" -v`
Expected: FAIL — `AttributeError: 'LinuxStorageRegistration' object has no attribute 'contribute_snapshot'`

- [ ] **Step 3: Write minimal implementation** (add to `registration.py`)

```python
    def contribute_snapshot(self, snapshot, provider_id: UUID) -> int:
        """Contribute each file entry as a thin provenance doc into Objects, and
        a recorder→object edge into Relationships. Endpoints use canonical
        str(UUID) form so OUTBOUND traversal resolves (raw hex dangles)."""
        from uuid import uuid4

        objects_name = self._registrar.owned_collection_name  # public seam
        count = 0
        for entry in snapshot.entries:
            obj_key = uuid4()
            rec = ContributedRecord(
                source=provider_id,
                raw=entry.model_dump(mode="json"),
                object_key=str(obj_key),
            )
            self._registrar.contribute(
                provider_id, _key=str(obj_key), **rec.to_contribution_fields()
            )
            self._registrar.contribute_edge(
                contributor_id=self.recorder_id,
                from_ref=f"entities/{self.recorder_id}",
                to_ref=f"{snapshot_objects_ref(objects_name, obj_key)}",
                relation_type="records",
            )
            count += 1
        return count
```

> **Note for the implementer:** `snapshot.entries` is the `FilesystemSnapshot` field holding `FileEntryData` items — confirm the exact attribute name against `src/yanantin/collector/storage/local/linux/models.py` before writing (the Explore map calls it `entries`; verify, don't trust). The edge `_to` must reference the obfuscated Objects collection NAME with the canonical object `_key`; define a tiny local helper `snapshot_objects_ref(objects_name, obj_key) -> f"{objects_name}/{obj_key}"` or inline it. `_key` is passed to `contribute` so the edge endpoint is deterministic; confirm `Registrar.contribute` forwards `_key` through `**fields` into the insert (it does — `**fields` is spread into the doc). The traversal test is the load-bearing check that endpoints resolve.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py -k "provenance_round_trips or interchangeable" -v`
Expected: PASS. If the OUTBOUND traversal returns zero, the endpoint key is non-canonical — fix the ref form, do not weaken the assertion.

- [ ] **Step 5: Commit** (Yanantin-signed, `feat(recorder): contribute thin provenance docs + Relationships edges — #30 Task 5`)

---

### Task 6: `well_known` attaches-not-duplicates (stacking, driven by the mapping)

**Files:**
- Test: `tests/integration/test_recorder_collection_mapping.py` (Test: two recorders, one shared Objects, sliceable by provider — re-uses C0 stacking test #7's assertions, now driven by the mapping declaration)

**Interfaces:**
- Consumes: everything from Tasks 1–5. No new production code expected; this task PROVES the attach-not-mint property holds for two recorders sharing `Objects`. If it fails, the bug is in Task 5's contribution path or Task 2's edge ownership, fixed there.

**Codex test-author prompt:**
> In `tests/integration/test_recorder_collection_mapping.py`, write `test_well_known_attaches_does_not_duplicate(live_db)`. Construct ONE registrar owning `Objects`/`Relationships`. Register TWO storage registrations against it — the linux one and a second `LinuxStorageRegistration` standing in for "windows-local" with a DIFFERENT collector provider_id (use `SyntheticFilesystemCollector` with a distinct seed and override its provider_id, or a second synthetic collector subclass). Both declare `well_known Objects`. `contribute_snapshot` from each. Assert: (a) exactly ONE Objects collection exists (no per-recorder mint) — check the live DB collection list; (b) `list_contributions()` with no filter returns both providers' docs; (c) `list_contributions(provider=linux)` filters to only linux's docs; (d) divergent open-tail fields from each provider survive (extra="allow"). This is the C0 stacking test #7 property, now driven by the mapping. Clean up. `< /dev/null`.

- [ ] **Step 1: Codex authors the test.**

- [ ] **Step 2: Run — it should pass on the Task-5 implementation** (the attach-not-mint property is already implied by writing through the owned collection). If it fails, debug Task 5/2.

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py::test_well_known_attaches_does_not_duplicate -v`
Expected: PASS

- [ ] **Step 3: Commit** (Yanantin-signed, `test(integration): well_known attaches to one shared Objects, sliceable by provider — #30 Task 6`)

---

### Task 7: Fail-stop on a `well_known` target with no owning collection

**Files:**
- Modify: `src/yanantin/recorder/storage/local/linux/registration.py` (guard in `contribute_snapshot` / a `_require_owned` check)
- Test: `tests/integration/test_recorder_collection_mapping.py` (Test: fail-stop, no silent mint)

**Interfaces:**
- Consumes: Tasks 1–5.
- Produces: `LinuxStorageRegistration.contribute_snapshot` raises a clear error (e.g. `RuntimeError`/`ValueError`) when the registrar it was handed does NOT own the `Objects`/`Relationships` collections (no silent mint — the mint path is `dynamic` only, and this recorder is `well_known`).

**Codex test-author prompt:**
> In `tests/integration/test_recorder_collection_mapping.py`, write `test_well_known_fails_stop_without_owning_collection(live_db)`. Construct a `Registrar` that owns ONLY a catalog (no `owned_collection`/`owned_edge_collection`). Construct `LinuxStorageRegistration` against it, register, then call `contribute_snapshot(...)` and assert it RAISES (pytest.raises) with a message indicating the well_known target has no owning collection — NOT a silent mint of a new collection. Assert no stray collection was created. Clean up. `< /dev/null`.

- [ ] **Step 1: Codex authors the test.**

- [ ] **Step 2: Run to verify it fails** (currently `contribute_snapshot` would try to write and get a driver error, not a clear domain error)

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py::test_well_known_fails_stop_without_owning_collection -v`
Expected: FAIL (wrong exception type or a stray collection created)

- [ ] **Step 3: Write minimal implementation** — add an explicit guard at the top of `contribute_snapshot`:

```python
        # well_known means "write through a collection an owning registrar
        # created" — never mint. If the handed registrar owns no Objects
        # collection, that is the caller's error, surfaced loudly (the mint
        # path is `dynamic` only, not chosen here).
        if not self._registrar.owns_owned_collection:
            raise ValueError(
                "well_known Objects target has no owning collection on the "
                "handed registrar; construct it with owned_collection=Objects "
                "(well_known never mints — that is the dynamic path)"
            )
        if not self._registrar.owns_edge_collection:
            raise ValueError(
                "well_known Relationships target has no owning edge collection; "
                "construct the registrar with owned_edge_collection=Relationships"
            )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py::test_well_known_fails_stop_without_owning_collection -v`
Expected: PASS

- [ ] **Step 5: Commit** (Yanantin-signed, `feat(recorder): fail-stop on well_known target with no owning collection — #30 Task 7`)

---

### Task 8: End-to-end CLI visibility

**Files:**
- Test: `tests/integration/test_recorder_collection_mapping.py` (Test: `python -m yanantin.core` lists the registrant, shows `contributes_to`, reports non-zero contribution count)
- Possibly modify: the CLI inspector module if it does not already surface `contributes_to` / contribution counts (verify first — the CLI inspector landed per `project_c0_next_pour_linux_fs_registrar`; check `src/yanantin/core/__main__.py`).

**Interfaces:**
- Consumes: everything; the CLI reads the open tail already (per spec, "the mapping is visible through `python -m yanantin.core` immediately, no new read path").
- Produces: confirmation the mapping + counts are visible end-to-end. If the CLI does not show `contributes_to`, add it minimally to the existing list output (surgical, follow the CLI's existing format).

**Codex test-author prompt:**
> First inspect `src/yanantin/core/__main__.py` to learn the CLI's list verbs and how it connects to the DB. Then in `tests/integration/test_recorder_collection_mapping.py` write `test_end_to_end_visible_through_cli(live_db)`. After registering + `contribute_snapshot`, invoke the core CLI list path (either via `subprocess` running `python -m yanantin.core <list-verb>` against apacheta_test, or by importing and calling the CLI's list function directly — prefer the in-process call for speed) and assert the output (a) lists the linux-local-storage recorder registrant, (b) shows its `contributes_to` (Objects + Relationships), and (c) reports a non-zero contribution count for it. Clean up. `< /dev/null`.

- [ ] **Step 1: Inspect the CLI** — Read `src/yanantin/core/__main__.py`. Determine whether `contributes_to` and contribution counts already surface. Note the exact list verb and connection idiom for the Codex prompt.

- [ ] **Step 2: Codex authors the test** (with the verbs found in Step 1).

- [ ] **Step 3: Run to verify it fails** (if the CLI doesn't yet show `contributes_to`/counts)

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py::test_end_to_end_visible_through_cli -v`
Expected: FAIL (missing `contributes_to` in output, or count not shown)

- [ ] **Step 4: Minimal CLI change** — if needed, add `contributes_to` + contribution count to the existing per-registrant list output, matching the CLI's current format. Do NOT restructure the CLI. (If the CLI already shows them, this step is a no-op and the test passed at Step 3 — record that.)

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/integration/test_recorder_collection_mapping.py::test_end_to_end_visible_through_cli -v`
Expected: PASS

- [ ] **Step 6: Run the WHOLE suite — no regression, red-bar floor intact**

Run: `uv run pytest -q`
Expected: the 13 designed red-bar feature-gates still red (incl. `test_uniform_storage_object` — #17 NOT turned green by this pour), `test_portability` green, everything else green, the 8 new mapping tests green.

- [ ] **Step 7: Commit** (Yanantin-signed, `feat(core): surface contributes_to + contribution count in CLI; #30 vertical end-to-end green`)

- [ ] **Step 8: Sweep the trailing OTS stamp(s)**

```bash
git add docs/ots/*.ots
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "chore: sweep OTS stamp tail after #30 recorder→collection-mapping vertical

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 9: Close the issue** — `gh issue close 30 --comment "linux-local-storage recorder→collection-mapping vertical landed: <commit range>. Recorder registers + declares contributes_to (Objects doc + Relationships edge), contributes thin provenance docs, well_known attaches-not-mints, fail-stop honored, visible through python -m yanantin.core. #17 uniform StorageObject stays out of scope (still red-bar). Remaining: migrate other providers (C0 OPEN ITEM 3), dynamic Case-3 transducers, read-side schema-collapse — all named-and-deferred."`

---

## Self-Review

**1. Spec coverage** (against `2026-06-17-recorder-collection-mapping-design.md` §"Testing" 1–8):
- Test 1 (collector mapping empty) → Task 1 ✓
- Test 2 (recorder declares N targets, doc+edge) → Tasks 2 + 4 ✓
- Test 3 (well_known attaches, not duplicates) → Task 6 ✓
- Test 4 (dynamic mints) → **NOT built** — `dynamic` Case-3 is explicitly out-of-scope for THIS pour (spec §"Out of scope": "spotify / activity-stream Case-3 transducers — designed-by-example here, built when a real one is on the table"). The `naming="dynamic"` *shape* is captured (Task 1) so the joint exists; the mint *behavior* is deferred. Noted, not a gap.
- Test 5 (provenance round-trips) → Task 5 ✓
- Test 6 (real vs synthetic interchangeable) → Task 5 ✓
- Test 7 (end-to-end visibility) → Task 8 ✓
- Test 8 (fail-stop + registrar opacity round-trip) → Task 7 (fail-stop) + Task 3 (opacity) ✓
- Spec §"Scope of THIS pour" (register self + collector by proxy; contribute into owned Objects + Relationships; visible through CLI) → Tasks 4, 5, 8 ✓
- Spec §"registrar treats contributes_to as OPAQUE" → Task 3 red-bar ✓
- Spec §"thin record, NOT #17 StorageObject" → Task 1 + Global Constraint (don't green #17) ✓

**2. Placeholder scan:** No TBD/TODO. Task 5 Step 3 carries an explicit implementer note to verify `snapshot.entries`/`_key`-forwarding against live code rather than trust the map — that is a verification instruction, not a placeholder.

**3. Type consistency:** `ContributionTarget`/`ContributedRecord` (Task 1) used consistently in Tasks 4–5. `Registrar.contribute_edge` signature (Task 2) matches its call in Task 5. `RECORDER_ID`/`recorder_id` (Task 4) used in Task 5 edge `_from`. `contributes_to` token absent from registrar source (Task 3 guard) and present only as register `**extra` (Task 4) — consistent with the opacity property.

**4. One known soft spot, flagged for execution:** Task 5's edge `_to` references `{objects_name}/{obj_key}` where `objects_name` is the *obfuscated* owned-collection name. Under `TransparentObfuscator` (test default) this is identity and resolves; under a keyed obfuscator the edge endpoint must use the same obfuscated collection name the doc was inserted into (it does, since both read `_owned_name`). The traversal test (Task 5) is the live check. If a keyed-obfuscator test is later added, this is the line to watch — recorded here so it isn't rediscovered cold.
