# Finish Collector/Recorder Migration to One Canonical Stack (Phase 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the 06-14 collector/transport/machine/recorder split (which ran Tasks 1–7 and stopped), so the codebase has ONE canonical stack — then DELETE the old stack outright (no compat shims).

**Architecture:** The new stack (`collector/storage|activity|semantic/...`, `recorder/...`, `transport/`, `machine/`) is the canonical target. The old flat stack (`collector/base.py`, `collector/{filesystem,fs_events,dropbox,openrouter}/`, `collector/{synthetic,models,wranglers,machine_config,checksum}.py`) is still the live production path and must be repointed onto canonical, then removed. Migrate the two never-moved domains (checksum, openrouter) into the new tree first, so every consumer CAN be repointed.

**Tech Stack:** Python 3.14, uv-managed, Pydantic v2, pytest.

## Global Constraints

- **Python 3.14, uv-managed.** `uv run pytest`.
- **GREEN BAR IS THE INVARIANT.** Baseline (2026-06-17): `tests/unit/` = **1539 passed, 1 skipped, 3 xfailed**. Every task ends green at this count or higher (count rises only if a task adds tests). A task that drops the count or changes skip/xfail totals without explanation is a FAILURE — stop and investigate (systematic-debugging), do not weaken assertions.
- **DELETE, do not shim** (Tony, 2026-06-17). This DIVERGES from the 06-14 plan's "Shims at old locations (never deleted)" section — deliberately. There is NO external importer of any old `yanantin.collector.*` path (verified across tinkuy/hamutay/pukara/willay/pichay/indaleko). Old code's *why* is absent; git holds the history. No re-export shims — they are new duplicate surface for a path nobody needs.
- **Stable provider-ID strings stay VERBATIM.** Literals like `"yanantin.collector.filesystem.{id}"` (collector.py:124) and `"yanantin.collector.fs_events.{id}"` are uuid5 seeds, NOT import paths. Changing them silently re-mints provider UUIDs. Do NOT "tidy" them to match new module paths.
- **Don't fix the blob-recorder with per-record loops** — the batch model (collector→file→recorder→arangoimport) is intentional at millions-scale (see `project_indaleko_batch_model_and_the_scar`).
- **AI commits use per-command git config overrides** (Yanantin signing key), NOT repo-level config.
- **This plan does NO registration work.** `core.registration` is untouched. Phase 2 (the recorder registration vertical) is a separate plan written after this lands.

## The divergence already reconciled (read before Task 5)

The NEW linux collector/fact_recorder are feature-SUPERSETS of the old:
- new `collector/storage/local/linux/collector.py:118` has `machine_id` param; old `collector/filesystem/collector.py` does not.
- new `recorder/storage/local/linux/fact_recorder.py` writes `ProvenanceEdge` (machine→fact, collector→fact); old `collector/filesystem/fact_recorder.py` does not.

**Decision (Tony, 06-17):** new is strictly better, no user depends on old behavior → callers ADOPT the new behavior when repointed. This is the migration delivering its payload, not a regression. Where a test asserts the OLD (edge-free) shape, the test is updated to the new reality (stronger/more-complete, never weaker) — and flagged in its commit. If repointing makes a test fail because it asserted the *absence* of edges, that is the divergence surfacing; update the assertion to expect edges, do not suppress them.

---

### Task 1: Migrate checksum into the canonical tree

`collector/storage/local/checksum.py` does not exist. The old `collector/checksum.py` holds `ChecksumData`, `ChecksumCollector`, `SyntheticChecksumCollector`, `ChecksumRecorder`, `ChecksumFactRecorder`, `collect_and_record_checksum` (checksum.py:44/85/161/220/286/325). Move them to canonical, rebased onto the new `_collector_base`/`_synthetic_base` and `recorder.base`.

**Files:**
- Read: `src/yanantin/collector/checksum.py` (full), `src/yanantin/collector/storage/local/linux/collector.py` (for the new-base import pattern), `src/yanantin/recorder/storage/local/linux/recorder.py` (for the new recorder import pattern).
- Create: `src/yanantin/collector/storage/local/checksum.py` (collector + synthetic + data model), `src/yanantin/recorder/storage/local/checksum.py` (ChecksumRecorder + ChecksumFactRecorder + collect_and_record_checksum) — OR keep all in the one canonical file if the new tree co-locates recorders with collectors for checksum. Match whatever pattern the linux tree uses (linux SPLITS collector and recorder across `collector/` and `recorder/` packages — follow that).
- Test: existing `tests/unit/test_collector.py`, `tests/unit/test_recorders.py`, `tests/unit/test_fact_recorders.py` reference checksum; they will be repointed in Task 7. For THIS task, add a temporary import-smoke test.

**Interfaces:**
- Consumes: `CollectorBase` from `collector._collector_base`; `SyntheticCollectorBase` from `collector._synthetic_base`; `RecorderBase`, `FactRecorderBase` from `recorder.base`.
- Produces: canonical `ChecksumData`, `ChecksumCollector`, `SyntheticChecksumCollector` (in `collector/storage/local/checksum.py`); canonical `ChecksumRecorder`, `ChecksumFactRecorder`, `collect_and_record_checksum` (in `recorder/storage/local/checksum.py`). Same public names as today.

- [ ] **Step 1: Read the old checksum module and the new linux pattern**

Use Read on `src/yanantin/collector/checksum.py`, `src/yanantin/collector/storage/local/linux/collector.py`, `src/yanantin/recorder/storage/local/linux/recorder.py`. Note: which base classes the new tree imports, and how collector vs recorder are split across packages.

- [ ] **Step 2: Write a failing import-smoke test**

```python
# tests/unit/test_checksum_canonical.py
def test_checksum_canonical_paths_import():
    from yanantin.collector.storage.local.checksum import (
        ChecksumData, ChecksumCollector, SyntheticChecksumCollector,
    )
    from yanantin.recorder.storage.local.checksum import (
        ChecksumRecorder, ChecksumFactRecorder, collect_and_record_checksum,
    )
    # collector self-describes; provider id is stable across instances
    c = ChecksumCollector  # class import is enough for the smoke
    assert ChecksumData is not None
    assert collect_and_record_checksum is not None
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/unit/test_checksum_canonical.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yanantin.collector.storage.local.checksum'`

- [ ] **Step 4: Create the canonical modules**

Copy the class bodies from `collector/checksum.py` VERBATIM into the two new files, changing ONLY the base-class imports to the new paths (`collector._collector_base`, `collector._synthetic_base`, `recorder.base`). Preserve any stable provider-ID seed strings exactly. Add the package `__init__.py` re-exports if the new tree convention uses them (check the linux tree).

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/unit/test_checksum_canonical.py -v`
Expected: PASS

- [ ] **Step 6: Full unit suite — no regression**

Run: `uv run pytest tests/unit/ -q`
Expected: **1540 passed** (1539 + the new smoke), 1 skipped, 3 xfailed. (Old `collector/checksum.py` still exists and still passes — not deleted until Task 6.)

- [ ] **Step 7: Commit**

```bash
git add src/yanantin/collector/storage/local/checksum.py src/yanantin/recorder/storage/local/checksum.py tests/unit/test_checksum_canonical.py
# (+ any __init__.py created)
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "refactor(collector): migrate checksum to canonical tree (Phase 1 Task 1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Migrate openrouter into the canonical tree

`collector/semantic/` and `recorder/semantic/openrouter/` do not exist (only an empty `recorder/semantic/__init__.py`). The old `collector/openrouter/` holds collector + models + fact_recorder. Move to `collector/semantic/openrouter/` (collector, models) and `recorder/semantic/openrouter/fact_recorder.py`.

**Files:**
- Read: `src/yanantin/collector/openrouter/collector.py`, `models.py`, `fact_recorder.py`.
- Create: `src/yanantin/collector/semantic/__init__.py`, `src/yanantin/collector/semantic/openrouter/{__init__,collector,models}.py`, `src/yanantin/recorder/semantic/openrouter/{__init__,fact_recorder}.py`.
- Test: `tests/unit/test_openrouter_canonical.py` (smoke).

**Interfaces:**
- Consumes: `CollectorBase` from `collector._collector_base`; `FactRecorderBase` from `recorder.base`.
- Produces: canonical `OpenRouterActivity`, `OpenRouterActivityRow`, `OpenRouterActivityCollector` (semantic/openrouter); canonical `OpenRouterFactRecorder` (recorder/semantic/openrouter). Same names as today.

- [ ] **Step 1: Read the old openrouter modules**

Read all three files under `src/yanantin/collector/openrouter/`. Note base imports and stable provider-ID strings.

- [ ] **Step 2: Write a failing import-smoke test**

```python
# tests/unit/test_openrouter_canonical.py
def test_openrouter_canonical_paths_import():
    from yanantin.collector.semantic.openrouter.collector import (
        OpenRouterActivityCollector,
    )
    from yanantin.collector.semantic.openrouter.models import OpenRouterActivity
    from yanantin.recorder.semantic.openrouter.fact_recorder import (
        OpenRouterFactRecorder,
    )
    assert OpenRouterActivityCollector is not None
    assert OpenRouterActivity is not None
    assert OpenRouterFactRecorder is not None
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/unit/test_openrouter_canonical.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yanantin.collector.semantic.openrouter'`

- [ ] **Step 4: Create the canonical modules**

Copy class bodies VERBATIM, change only base-class imports to new paths, preserve provider-ID seed strings. Add `__init__.py` re-exports matching the new-tree convention.

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/unit/test_openrouter_canonical.py -v`
Expected: PASS

- [ ] **Step 6: Full unit suite**

Run: `uv run pytest tests/unit/ -q`
Expected: **1541 passed**, 1 skipped, 3 xfailed.

- [ ] **Step 7: Commit**

```bash
git add src/yanantin/collector/semantic/ src/yanantin/recorder/semantic/ tests/unit/test_openrouter_canonical.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "refactor(collector): migrate openrouter to canonical tree (Phase 1 Task 2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Collapse the duplicate ProviderRegistration

`collector/models.py:ProviderRegistration` is BYTE-IDENTICAL to `transport/models.py:ProviderRegistration`. Make `transport/models.py` the sole definition; remove the duplicate. (WranglerEnvelope is also duplicated the same way — collapse it too if identical.)

**Files:**
- Modify: `src/yanantin/collector/models.py`, `src/yanantin/collector/__init__.py`.
- Verify: `src/yanantin/transport/models.py` is the canonical home.
- Test: `tests/unit/test_collector.py` (uses `ProviderRegistration` at lines 16/67/78) — must still pass importing from wherever `collector` re-exports it.

**Interfaces:**
- Consumes: `transport.models.ProviderRegistration`, `transport.models.WranglerEnvelope`.
- Produces: `collector.models` no longer DEFINES `ProviderRegistration`/`WranglerEnvelope`; if anything still imports `from yanantin.collector.models import ProviderRegistration`, it resolves via a single re-export line `from yanantin.transport.models import ProviderRegistration, WranglerEnvelope` (this is NOT a compat shim for an external path — it is the internal `collector` package keeping its own public surface during the transition; `collector/models.py` is deleted entirely in Task 6 once `collector/__init__` imports from transport directly).

- [ ] **Step 1: Confirm byte-identity**

Run: `diff <(sed -n '19,67p' src/yanantin/collector/models.py) <(sed -n '19,67p' src/yanantin/transport/models.py)`
Expected: identical for the `ProviderRegistration` + `WranglerEnvelope` definitions (the file headers/imports may differ — that's fine).

- [ ] **Step 2: Run the test that uses it, confirm green now**

Run: `uv run pytest tests/unit/test_collector.py -q`
Expected: PASS (baseline).

- [ ] **Step 3: Replace the duplicate definitions with a re-export**

In `src/yanantin/collector/models.py`, delete the `class ProviderRegistration` and `class WranglerEnvelope` bodies; replace with:
```python
from yanantin.transport.models import ProviderRegistration, WranglerEnvelope  # noqa: F401
```
Keep `DataT = TypeVar("DataT")` only if other code in `collector` references it from here (grep first; if not, drop it).

- [ ] **Step 4: Run the test + full unit suite**

Run: `uv run pytest tests/unit/test_collector.py -q && uv run pytest tests/unit/ -q`
Expected: PASS; **1541 passed**, 1 skipped, 3 xfailed.

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/collector/models.py src/yanantin/collector/__init__.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "refactor(collector): collapse duplicate ProviderRegistration to transport (Phase 1 Task 3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Repoint `collector/pipeline.py` and `collector/__init__.py` to canonical

`pipeline.py:22-24` imports from `collector.base`/`models`/`wranglers`. `collector/__init__.py:19-63` imports the entire old stack. Repoint both to canonical paths (`transport.*`, `recorder.*`, `collector._collector_base`, `collector._synthetic_base`, and the new domain trees).

**Files:**
- Modify: `src/yanantin/collector/pipeline.py`, `src/yanantin/collector/__init__.py`.
- Test: importing `yanantin.collector` must still expose the same `__all__` names.

**Interfaces:**
- Consumes: every canonical module created/confirmed in Tasks 1–3 plus the existing new domain trees.
- Produces: `yanantin.collector` public API unchanged (same names exported); internals point at canonical.

- [ ] **Step 1: Write a failing test pinning the public surface**

```python
# tests/unit/test_collector_public_surface.py
def test_collector_exports_stable_after_repoint():
    import yanantin.collector as c
    expected = {
        "CollectorBase", "SyntheticCollectorBase", "WranglerBase",
        "WranglerEnvelope", "ProviderRegistration",
        # add the rest of the CURRENT __all__ — read collector/__init__.py:__all__
    }
    assert expected.issubset(set(c.__all__))
```
(Fill `expected` from the ACTUAL current `collector/__init__.py` `__all__` — read it, copy every name. This test pins that repointing doesn't drop a name.)

- [ ] **Step 2: Run — should PASS now (pre-repoint), proving the test captures current truth**

Run: `uv run pytest tests/unit/test_collector_public_surface.py -v`
Expected: PASS (this is a characterization test — it locks current behavior BEFORE the change).

- [ ] **Step 3: Repoint the imports**

In `collector/__init__.py` and `pipeline.py`, change each old-stack import to its canonical path. Map: `collector.base`→`transport.base`(WranglerBase)+`recorder.base`(RecorderBase/FactRecorderBase)+`collector._collector_base`(CollectorBase); `collector.synthetic`→`collector._synthetic_base`; `collector.models`→`transport.models`; `collector.wranglers`→`transport.wranglers`; `collector.machine_config`→`machine.linux`; `collector.checksum`→`collector.storage.local.checksum`+`recorder.storage.local.checksum`; `collector.filesystem`→`collector.storage.local.linux`+`recorder.storage.local.linux`; `collector.fs_events`→`collector.activity.linux`+`recorder.activity.linux`; `collector.dropbox`→`collector.storage.cloud.dropbox`+`recorder.storage.cloud.dropbox`; `collector.openrouter`→`collector.semantic.openrouter`+`recorder.semantic.openrouter`.

- [ ] **Step 4: Run characterization test + full suite**

Run: `uv run pytest tests/unit/test_collector_public_surface.py -v && uv run pytest tests/unit/ -q`
Expected: PASS; **1542 passed**, 1 skipped, 3 xfailed.

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/collector/__init__.py src/yanantin/collector/pipeline.py tests/unit/test_collector_public_surface.py
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "refactor(collector): repoint __init__ and pipeline to canonical paths (Phase 1 Task 4)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Repoint `collector/__main__.py` to canonical (the divergence task)

`__main__.py` lazy-imports the old stack at ~17 sites (lines 74,89,128,162,168,192,198,227,233,258,269,287,291,309,329,333,350). Repoint each to canonical. THIS is where the linux divergence surfaces: the canonical filesystem path writes provenance edges; `__main__` callers now get that behavior.

**Files:**
- Modify: `src/yanantin/collector/__main__.py`.
- Test: a CLI smoke test that runs a command end-to-end on a tmp dir (e.g. `synthetic fs` or `filesystem <tmp>` with `--store memory`).

**Interfaces:**
- Consumes: canonical domain trees.
- Produces: `python -m yanantin.collector <cmd>` behaves as before for collection, with the new (edge-writing, machine_id) behavior where the canonical recorder provides it.

- [ ] **Step 1: Write a failing CLI smoke test**

```python
# tests/integration/test_collector_cli_smoke.py
import subprocess, sys
def test_synthetic_fs_to_memory_store_runs():
    r = subprocess.run(
        [sys.executable, "-m", "yanantin.collector", "synthetic", "fs", "5",
         "--store", "memory"],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stderr
```
(Adapt the exact subcommand/args to what `__main__.py` actually accepts — read its argparse setup first. Pick a command that needs NO live DB: `--store memory` or `synthetic`.)

- [ ] **Step 2: Run — PASS now (pre-repoint), locks current CLI behavior**

Run: `uv run pytest tests/integration/test_collector_cli_smoke.py -v`
Expected: PASS (characterization).

- [ ] **Step 3: Repoint every lazy import in `__main__.py`**

Replace each `from yanantin.collector.filesystem...` / `.checksum` / `.fs_events` / `.dropbox` / `.openrouter` / `.machine_config` import with its canonical path (same mapping as Task 4). Leave stable provider-ID seed strings untouched. Keep the lazy-import structure (don't hoist to module top — dropbox/openrouter have optional deps).

- [ ] **Step 4: Run smoke + full suite (unit + the CLI smoke)**

Run: `uv run pytest tests/integration/test_collector_cli_smoke.py -v && uv run pytest tests/unit/ -q`
Expected: smoke PASS; **1542 passed** (unit count unchanged), 1 skipped, 3 xfailed.

- [ ] **Step 5: If any test asserted edge-FREE filesystem output, update it to expect edges**

Search: `grep -rn "edge\|ProvenanceEdge\|relationship" tests/unit/test_recorders.py tests/unit/test_fact_recorders.py`. If a test asserts the old (no-edge) shape and now sees edges, update the assertion to the new reality (stronger, never weaker) and note it in the commit. If no such test exists, skip this step.

- [ ] **Step 6: Commit**

```bash
git add src/yanantin/collector/__main__.py tests/integration/test_collector_cli_smoke.py
# + any test files updated in step 5
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "refactor(collector): repoint __main__ to canonical; callers adopt edge-writing (Phase 1 Task 5)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Repoint the tests, then DELETE the old stack

Now nothing in `src/` imports the old stack. Repoint the TEST imports onto canonical, then delete the old modules. This is the irreversible step — gated on Tasks 1–5 being green.

**Files:**
- Modify: every test importing an old path. From the investigation: `tests/unit/test_collector.py`, `tests/unit/test_recorders.py`, `tests/unit/test_fact_recorders.py`, `tests/unit/test_collector_synthetic.py`, `tests/unit/test_collector_isomorphism.py`, `tests/red_bar/test_activity_stream.py`, `tests/red_bar/test_query_pipeline.py` (grep to confirm the full set).
- Delete: `collector/base.py`, `collector/synthetic.py`, `collector/models.py`, `collector/wranglers.py`, `collector/machine_config.py`, `collector/checksum.py`, and the directories `collector/filesystem/`, `collector/fs_events/`, `collector/dropbox/`, `collector/openrouter/`.

**Interfaces:**
- Consumes: canonical paths only.
- Produces: a single canonical stack; old paths gone.

- [ ] **Step 1: Find every remaining old-path importer**

Run: `grep -rn "collector\.base\|collector\.synthetic\|collector\.models\|collector\.wranglers\|collector\.machine_config\|collector\.checksum\|collector\.filesystem\|collector\.fs_events\|collector\.dropbox\|collector\.openrouter\b" tests/ src/`
Expected: only `tests/` hits remain (src/ was repointed in Tasks 4–5). Record the full list.

- [ ] **Step 2: Repoint each test import to canonical**

For each test file, change old imports to canonical (same mapping as Task 4). Do NOT change assertions except where Task 5 step 5 already flagged edge-shape. Run each repointed test file immediately after editing it:
Run: `uv run pytest <that_test_file> -q` → PASS before moving to the next.

- [ ] **Step 3: Confirm src/ + tests/ are clean of old paths**

Run: `grep -rn "collector\.base\|collector\.synthetic\|collector\.models\|collector\.wranglers\|collector\.machine_config\|collector\.checksum\|from yanantin\.collector\.filesystem\|from yanantin\.collector\.fs_events\|from yanantin\.collector\.dropbox\|from yanantin\.collector\.openrouter" src/ tests/`
Expected: EMPTY (no importer of any old path anywhere).

- [ ] **Step 4: Delete the old modules**

```bash
git rm src/yanantin/collector/base.py src/yanantin/collector/synthetic.py \
       src/yanantin/collector/models.py src/yanantin/collector/wranglers.py \
       src/yanantin/collector/machine_config.py src/yanantin/collector/checksum.py
git rm -r src/yanantin/collector/filesystem/ src/yanantin/collector/fs_events/ \
          src/yanantin/collector/dropbox/ src/yanantin/collector/openrouter/
```

- [ ] **Step 5: Full suite — unit + red_bar + integration that doesn't need a remote DB**

Run: `uv run pytest tests/unit/ tests/red_bar/ -q`
Expected: **>= 1542 passed**, 1 skipped, 3 xfailed (count may differ if test files were consolidated; skip/xfail unchanged). If anything imports a now-deleted module, it surfaces here as a collection error — repoint it (missed in Step 2) and re-run. Do NOT restore a deleted module to make a test pass; the test's import is what's stale.

- [ ] **Step 6: Commit the deletion**

```bash
git add -A
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "refactor(collector): repoint tests and DELETE old stack — one canonical stack (Phase 1 Task 6)

The old flat collector stack had no external users and was strictly
inferior to the new domain-organized stack. Repointed all consumers,
deleted the old modules. No compat shims (git holds the history).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Sweep orphans and verify the canonical stack is whole

The investigation found orphaned new-stack modules (`recorder/storage/cloud/dropbox/*`, `recorder/activity/linux/*`) that were dead because the old stack was live. After Task 6 they should now be REACHED (via the repointed `collector/__init__` / `__main__`). Confirm — and confirm no NEW orphans were created.

**Files:**
- Verify only; possibly a coverage/import-graph check. No deletions unless a module is confirmed dead AND Tony-confirmed (do not delete on sight — `project_storage_object_built_then_discarded_fossil`).

- [ ] **Step 1: Confirm every canonical recorder is now imported by something**

Run: `for m in recorder.storage.local.linux recorder.storage.cloud.dropbox recorder.activity.linux recorder.semantic.openrouter recorder.storage.local.checksum; do echo "== $m =="; grep -rn "$m" src/ tests/ | grep -v "src/yanantin/$(echo $m | tr . /)" | head -3; done`
Expected: each has at least one importer outside its own package. If one is still orphaned, report it — do NOT delete; flag for Tony (it may be intended-but-not-yet-wired, like Phase 2's target).

- [ ] **Step 2: Full clean suite run**

Run: `uv run pytest tests/unit/ tests/red_bar/ -q`
Expected: **>= 1542 passed**, 1 skipped, 3 xfailed.

- [ ] **Step 3: Confirm the tree shape matches the 06-14 target**

Run: `find src/yanantin/collector src/yanantin/recorder src/yanantin/transport src/yanantin/machine -name "*.py" | grep -v __pycache__ | sort`
Compare against the 06-14 plan's "New path" table. Every **Canonical** row should exist; no old flat module should remain.

- [ ] **Step 4: Report orphan-sweep findings to Tony**

Write a 5-line summary: which canonical modules are now live, any still-orphaned (flagged not deleted), final test count vs baseline. This is the handoff into Phase 2.

- [ ] **Step 5: Commit (if any verification artifact/test added)**

```bash
git add -A
git -c user.name="Yanantin AI (Claude Opus)" -c user.email="yanantin@wamason.com" \
  -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
  commit -S -m "test(collector): verify canonical stack is whole after migration (Phase 1 Task 7)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec/goal coverage:**
- Migrate checksum → Task 1. ✓
- Migrate openrouter → Task 2. ✓
- Collapse duplicate ProviderRegistration → Task 3. ✓
- Repoint __init__/pipeline → Task 4. ✓
- Repoint __main__ (+ divergence adoption) → Task 5. ✓
- Repoint tests + delete old → Task 6. ✓
- Verify whole, sweep orphans → Task 7. ✓
- Suite stays green throughout → every task ends with a `pytest -q` step and an expected count. ✓
- No registration work mixed in → stated in Global Constraints; no task touches `core`. ✓
- Delete-not-shim (diverges from 06-14 plan) → stated explicitly in Global Constraints + Task 6. ✓

**Divergence handled:** the new>old feature-superset (machine_id, edges) is addressed in Task 5 with an explicit "callers adopt new behavior; update tests that asserted the old shape to expect the new (stronger), never weaker" rule — consistent with `feedback_stronger_tests_never_an_error`.

**Placeholder scan:** Step bodies reference "read the actual `__all__`" / "adapt to actual argparse" in Tasks 4–5 — these are directives to MATCH existing truth (characterization tests), not placeholders for what to build. The mechanical mapping (old path → canonical path) is given in full in Task 4 Step 3 and reused by reference (DRY) in Tasks 5–6, which is acceptable since it's one explicit lookup table, not "similar to Task N" hand-waving.

**Type/name consistency:** canonical public names (`ChecksumCollector`, `ChecksumRecorder`, `OpenRouterFactRecorder`, `ProviderRegistration`, `CollectorBase`, etc.) are preserved verbatim from the old stack — the whole point is that the public surface is stable while internals move. The characterization tests in Tasks 4–5 enforce this.

**Risk note for the executor:** Task 6 is irreversible (deletion). It is gated on Tasks 1–5 each ending green, and Step 3 hard-checks that NO importer of any old path remains before Step 4 deletes. If Step 5 reveals a missed importer, the fix is to repoint it, never to restore the deleted module. Run Task 6 as its own review checkpoint.
