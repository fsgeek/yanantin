# Memory-Tool Harness — Capture Layer & Pre-Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project conventions that override the generic TDD flow:** CI enforces builder/tester separation (see `~/.claude/projects/-home-tony-projects-yanantin/memory/feedback_codex_tests.md`). Test files in this plan are authored via Codex, not by the implementing agent: `codex exec --full-auto -m gpt-5-codex "<spec>"`. The test code shown in each task is the *specification* of what Codex must produce — hand Codex the test description and the assertions, have it write the file, then run it to confirm it fails before writing implementation. The implementing agent writes the implementation; Codex writes the tests.

**Goal:** Build the data-integrity foundation for the memory-tool experimental harness — a schema-open JSONL capture layer with a no-truncation contract, and a pre-registration tool that resolves a model panel against the live OpenRouter catalog and produces an OTS-stampable manifest.

**Architecture:** A new `yanantin.experiments` package. `capture.py` holds the `CaptureRecord` model (schema-open via `extra="allow"`) plus an append-only JSONL writer and a loader. `catalog.py` fetches and hashes the OpenRouter `/models` catalog. `panel.py` holds the panel-criteria schema and the resolution logic that validates each candidate model against the live catalog and enriches it with current pricing/context-length. `preregister.py` is the CLI that ties resolution to the on-disk manifest layout and git staging; a `scripts/register-experiment` wrapper does the commit, after which yanantin's existing `.githooks/post-commit` OTS hook stamps it automatically. No runner, no tool surface, no experiment run — those are the next plan.

**Tech Stack:** Python 3.14, Pydantic v2, `httpx` (async, already a dep via `OpenRouterClient`), `pyyaml` (add if not present), `pytest` with an `integration` marker for live-API tests. Reuses `yanantin.apacheta.clients.openrouter.OpenRouterClient`.

**Spec:** `docs/specs/2026-05-11-memory-tool-experimental-harness-design.md` (sections "Capture Layer", "Runner → Panel manifest", "Pre-Registration Discipline"). This plan implements spec implementation-order steps 1 and 2 plus the step-3 end-to-end smoke.

**Out of scope (next plan):** Runner loop, function-calling extension to `OpenRouterClient`, the six tool functions, prompt corpus, name-effect experiment, in-fill panels, OTS-proof verification helper.

---

## File Structure

| File | Responsibility | New/Modified |
|------|----------------|--------------|
| `src/yanantin/experiments/__init__.py` | Package marker | New |
| `src/yanantin/experiments/capture.py` | `CaptureRecord` model, `CaptureWriter` (append-only JSONL), `load_run()` | New |
| `src/yanantin/experiments/catalog.py` | `fetch_openrouter_catalog()`, `catalog_snapshot_sha()` | New |
| `src/yanantin/experiments/panel.py` | `PanelCriteria`, `CandidateModel`, `ResolvedModel`, `ResolvedPanel`, `resolve_panel()`, YAML load/dump helpers | New |
| `src/yanantin/experiments/preregister.py` | CLI: resolve panel, write manifests, git-stage | New |
| `scripts/register-experiment` | Shell wrapper: invoke preregister `--stage`, then `git commit` (OTS hook fires after) | New |
| `experiments/memory_tools/panels/iteration_v1.criteria.yaml` | First panel criteria — current-gen candidates with tier annotations | New |
| `experiments/memory_tools/.gitkeep` | Keep the data dir tracked | New |
| `pyproject.toml` | Add `pyyaml` dep if absent; add `[tool.pytest.ini_options] markers` | Modified |
| `tests/experiments/__init__.py` | Test package marker | New |
| `tests/experiments/test_capture.py` | Tests for `CaptureRecord`, `CaptureWriter`, `load_run` | New (Codex) |
| `tests/experiments/test_catalog.py` | Tests for `catalog_snapshot_sha`; integration test for `fetch_openrouter_catalog` | New (Codex) |
| `tests/experiments/test_panel.py` | Tests for criteria loading and `resolve_panel` | New (Codex) |
| `tests/experiments/test_preregister.py` | Tests for the preregister CLI against a tmp git repo | New (Codex) |
| `tests/experiments/fixtures/openrouter_models_sample.json` | Small static `/models` catalog body for unit tests | New |
| `tests/experiments/test_smoke_capture.py` | Integration: one real OpenRouter call → CaptureRecord → write → load | New (Codex) |

> **Deviation from spec:** the spec sketched a `Makefile` `register-experiment` target borrowing from `../governance`'s pattern. This plan uses `scripts/register-experiment` (a shell script) instead, since yanantin is a uv-based project with no existing Makefile. If you'd rather have the Makefile, the script's body transfers verbatim into a Make recipe. Flag for Tony.

---

## Task 1: Experiments package + CaptureRecord model

**Files:**
- Create: `src/yanantin/experiments/__init__.py`
- Create: `src/yanantin/experiments/capture.py`
- Test: `tests/experiments/__init__.py`, `tests/experiments/test_capture.py` (Codex authors)

- [ ] **Step 1: Have Codex write the failing test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/__init__.py (empty) and tests/experiments/test_capture.py. The module under test is src/yanantin/experiments/capture.py, which defines a Pydantic v2 model CaptureRecord. Write test_capture_record_minimal_ok(): construct a CaptureRecord with status='ok' and all required fields populated (record_id: str UUID, timestamp: timezone-aware datetime, experiment_id: str, panel_id: str, tool_variant_id: str, model_id: str, prompt_template_id: str, prompt_full: str, request_full: dict, response_parsed: dict, response_raw_body: str, usage: dict, elapsed_seconds: float, status: 'ok', error_type: None, error_message: None, error_payload: None); assert model_dump() round-trips through model_validate() to an equal object. Write test_capture_record_error_shape(): construct one with status='error', response_parsed=None, response_raw_body=None, and error_type/error_message/error_payload populated strings; assert it validates. Write test_capture_record_extra_allowed(): construct one passing an unknown field collector_note='hi'; assert it does not raise and model_dump()['collector_note'] == 'hi'. Write test_capture_record_status_literal(): assert constructing with status='weird' raises pydantic.ValidationError. Do not write the implementation."`

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/experiments/test_capture.py -v`
Expected: collection error / FAIL — `ModuleNotFoundError: No module named 'yanantin.experiments'`

- [ ] **Step 3: Write `src/yanantin/experiments/__init__.py` (empty) and `capture.py` minimal model**

```python
# src/yanantin/experiments/__init__.py
"""Experimental harness for LLM-facing memory tools.

Capture layer (this module's `capture`), panel resolution (`panel`),
catalog fetch (`catalog`), pre-registration CLI (`preregister`). The
runner and tool surface live in a later increment.
"""
```

```python
# src/yanantin/experiments/capture.py
"""Activity-stream capture for the memory-tool harness.

Schema-open, append-only, no-truncation. Every tool call (and later,
every model call) produces one CaptureRecord written as a JSONL line.
Schema-open via `extra="allow"`: collectors attach fields without
coordinating with consumers. No truncation: full request, full response,
full error payload — storage is not the constraint, signal is.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class CaptureRecord(BaseModel):
    """One captured call. Built complete; never mutated.

    `response_parsed` / `response_raw_body` are None on error.
    `error_*` are None on success. `status` discriminates.
    """

    model_config = ConfigDict(extra="allow", frozen=True)

    record_id: str
    timestamp: datetime
    experiment_id: str
    panel_id: str
    tool_variant_id: str
    model_id: str
    prompt_template_id: str
    prompt_full: str
    request_full: dict[str, Any]
    response_parsed: dict[str, Any] | None
    response_raw_body: str | None
    usage: dict[str, Any]
    elapsed_seconds: float
    status: Literal["ok", "error"]
    error_type: str | None = None
    error_message: str | None = None
    error_payload: str | None = None
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/experiments/test_capture.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/experiments/__init__.py src/yanantin/experiments/capture.py tests/experiments/__init__.py tests/experiments/test_capture.py
git commit -m "feat(experiments): add CaptureRecord model for memory-tool harness"
```

---

## Task 2: CaptureWriter — append-only JSONL

**Files:**
- Modify: `src/yanantin/experiments/capture.py`
- Test: `tests/experiments/test_capture.py` (Codex extends)

- [ ] **Step 1: Have Codex extend the test**

Run: `codex exec --full-auto -m gpt-5-codex "Extend tests/experiments/test_capture.py. capture.py now also defines CaptureWriter(path: pathlib.Path) which creates parent directories on construction, has .write(record: CaptureRecord) -> None that appends one JSON line (record.model_dump(mode='json')) plus a newline, flushing each write, and is usable as a context manager (__enter__ returns self, __exit__ closes the file handle). Write test_writer_appends_lines(tmp_path): make a writer at tmp_path/'run'/'r1.jsonl', write two distinct records, then read the file; assert exactly 2 lines, each json.loads-able, and the parsed 'record_id' values match what was written, in order. Write test_writer_creates_parent_dirs(tmp_path): writer at tmp_path/'a'/'b'/'c.jsonl'; after writing one record assert the file exists. Write test_writer_context_manager(tmp_path): use 'with CaptureWriter(...) as w: w.write(rec)'; after the block assert the file has 1 line. Use a small helper to build a valid CaptureRecord. Do not modify the implementation."`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/experiments/test_capture.py -v -k writer`
Expected: FAIL — `AttributeError`/`ImportError`: `CaptureWriter` not defined

- [ ] **Step 3: Add `CaptureWriter` to `capture.py`**

```python
# append to src/yanantin/experiments/capture.py

class CaptureWriter:
    """Append-only JSONL writer for CaptureRecords.

    One file per run. Flushes on every write so a crashed run still
    leaves a complete record of everything captured before the crash.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8")

    def write(self, record: CaptureRecord) -> None:
        self._fh.write(json.dumps(record.model_dump(mode="json")) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "CaptureWriter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/experiments/test_capture.py -v`
Expected: all passed (4 from Task 1 + 3 new)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/experiments/capture.py tests/experiments/test_capture.py
git commit -m "feat(experiments): add append-only JSONL CaptureWriter"
```

---

## Task 3: load_run — read a run's records back

**Files:**
- Modify: `src/yanantin/experiments/capture.py`
- Test: `tests/experiments/test_capture.py` (Codex extends)

- [ ] **Step 1: Have Codex extend the test**

Run: `codex exec --full-auto -m gpt-5-codex "Extend tests/experiments/test_capture.py. capture.py now also defines load_run(path: pathlib.Path) -> list[CaptureRecord] which reads a JSONL file and returns CaptureRecords in file order, skipping blank lines, raising ValueError with the 1-based line number in the message if a line fails to parse or validate. Write test_load_run_roundtrip(tmp_path): write 3 records via CaptureWriter, load_run them, assert the loaded list equals the originals (compare model_dump). Write test_load_run_skips_blank_lines(tmp_path): manually write a file with a record line, an empty line, another record line; assert load_run returns 2 records. Write test_load_run_bad_line(tmp_path): write a file whose 2nd line is 'not json'; assert load_run raises ValueError and 'line 2' is in str(exc). Do not modify the implementation."`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/experiments/test_capture.py -v -k load_run`
Expected: FAIL — `load_run` not defined

- [ ] **Step 3: Add `load_run` to `capture.py`**

```python
# append to src/yanantin/experiments/capture.py

def load_run(path: Path) -> list[CaptureRecord]:
    """Load all CaptureRecords from a run's JSONL file, in file order.

    Blank lines are skipped. A malformed line raises ValueError naming
    the 1-based line number.
    """
    records: list[CaptureRecord] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(CaptureRecord.model_validate(json.loads(stripped)))
            except Exception as exc:  # noqa: BLE001 — re-raised with context
                raise ValueError(f"capture file {path} line {lineno}: {exc}") from exc
    return records
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/experiments/test_capture.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/experiments/capture.py tests/experiments/test_capture.py
git commit -m "feat(experiments): add load_run for replaying captured records"
```

---

## Task 4: Catalog fetch + snapshot hash

**Files:**
- Create: `src/yanantin/experiments/catalog.py`
- Create: `tests/experiments/fixtures/openrouter_models_sample.json`
- Modify: `pyproject.toml` (add `markers` under `[tool.pytest.ini_options]`)
- Test: `tests/experiments/test_catalog.py` (Codex authors)

- [ ] **Step 1: Create the fixture catalog**

Create `tests/experiments/fixtures/openrouter_models_sample.json` — a trimmed but realistically-shaped OpenRouter `/models` response. (The real response is `{"data": [ {model dict}, ... ]}`; each model dict has `id`, `name`, `context_length`, `pricing: {"prompt": "0.00000002", "completion": "0.00000004"}`, and `top_provider: {"max_completion_tokens": 16384}` among others.)

```json
{
  "data": [
    {"id": "meta-llama/llama-4-scout", "name": "Meta: Llama 4 Scout", "context_length": 131072, "pricing": {"prompt": "0.00000008", "completion": "0.0000003"}, "top_provider": {"max_completion_tokens": 16384}},
    {"id": "google/gemma-4-31b-it", "name": "Google: Gemma 4 31B", "context_length": 32768, "pricing": {"prompt": "0.00000003", "completion": "0.00000006"}, "top_provider": {"max_completion_tokens": 8192}},
    {"id": "anthropic/claude-haiku-4-5", "name": "Anthropic: Claude Haiku 4.5", "context_length": 200000, "pricing": {"prompt": "0.000001", "completion": "0.000005"}, "top_provider": {"max_completion_tokens": 32768}},
    {"id": "z-ai/glm-4-32b", "name": "Z.ai: GLM 4 32B", "context_length": 32768, "pricing": {"prompt": "0", "completion": "0"}, "top_provider": {"max_completion_tokens": 8192}},
    {"id": "openai/gpt-4o-audio-preview", "name": "OpenAI: GPT-4o Audio", "context_length": 4000, "pricing": {"prompt": "0.0000025", "completion": "0.00001"}, "top_provider": {"max_completion_tokens": 4096}},
    {"id": "tiny/no-context-model", "name": "Tiny: low ctx", "context_length": 2048, "pricing": {"prompt": "0.00000001", "completion": "0.00000001"}, "top_provider": {}}
  ]
}
```

- [ ] **Step 2: Add the `integration` marker to pyproject.toml**

Add under `[tool.pytest.ini_options]` (which currently contains only `testpaths = ["tests"]`):

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: test hits a live external API (OpenRouter); skip with -m 'not integration'",
]
```

- [ ] **Step 3: Have Codex write the failing test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_catalog.py. Module under test: src/yanantin/experiments/catalog.py. It defines (a) catalog_snapshot_sha(catalog: list[dict]) -> str returning a hex sha256 of the canonical JSON (json.dumps(catalog, sort_keys=True, separators=(',', ':')).encode()); (b) async fetch_openrouter_catalog(api_key: str | None = None) -> list[dict] which GETs https://openrouter.ai/api/v1/models with the Authorization bearer header (api_key or OPENROUTER_API_KEY env) and returns the JSON body's 'data' list. Tests: test_snapshot_sha_stable() loads tests/experiments/fixtures/openrouter_models_sample.json, takes its 'data' list, asserts catalog_snapshot_sha returns a 64-char lowercase hex string, and asserts it equals catalog_snapshot_sha(list(reversed(data))) is FALSE (order matters → different sha) — i.e. assert the two differ; also assert calling it twice on the same list gives the identical string. test_snapshot_sha_known_value(): hardcode the expected sha for the fixture's data list (compute it once and paste it) and assert equality, so drift in the canonicalization is caught. Mark a test test_fetch_catalog_live() with @pytest.mark.integration: skip if OPENROUTER_API_KEY not in env (pytest.skip), else await fetch_openrouter_catalog(), assert it's a non-empty list and every element has an 'id' key. Do not write the implementation."`

- [ ] **Step 4: Run to verify failure**

Run: `uv run pytest tests/experiments/test_catalog.py -v`
Expected: FAIL — `catalog` module not found

- [ ] **Step 5: Write `src/yanantin/experiments/catalog.py`**

```python
# src/yanantin/experiments/catalog.py
"""Fetch and fingerprint the OpenRouter model catalog.

The catalog (`GET /models`) is the source of truth for which models
exist, their pricing, and their context limits. A pre-registration
records both the resolved panel and a sha256 fingerprint of the exact
catalog body it was resolved against, so "were these models current?"
has a verifiable answer.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import httpx

CATALOG_URL = "https://openrouter.ai/api/v1/models"


def catalog_snapshot_sha(catalog: list[dict[str, Any]]) -> str:
    """Hex sha256 of the catalog's canonical JSON. Order-sensitive."""
    blob = json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


async def fetch_openrouter_catalog(api_key: str | None = None) -> list[dict[str, Any]]:
    """Return the `data` list from OpenRouter's `/models` endpoint.

    Raises ValueError if no API key is available; httpx errors propagate.
    """
    key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY not set; pass api_key= or export it")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(CATALOG_URL, headers={"Authorization": f"Bearer {key}"})
        resp.raise_for_status()
        body = resp.json()
    data = body.get("data")
    if not isinstance(data, list):
        raise ValueError(f"unexpected /models response shape: {type(data)}")
    return data
```

- [ ] **Step 6: Run to verify pass (skipping integration)**

Run: `uv run pytest tests/experiments/test_catalog.py -v -m "not integration"`
Expected: `test_snapshot_sha_stable` and `test_snapshot_sha_known_value` pass; `test_fetch_catalog_live` deselected.

- [ ] **Step 7: Commit**

```bash
git add src/yanantin/experiments/catalog.py tests/experiments/test_catalog.py tests/experiments/fixtures/openrouter_models_sample.json pyproject.toml
git commit -m "feat(experiments): add OpenRouter catalog fetch and snapshot fingerprint"
```

---

## Task 5: Panel criteria schema + YAML helpers

**Files:**
- Create: `src/yanantin/experiments/panel.py`
- Modify: `pyproject.toml` (ensure `pyyaml` is a dependency)
- Test: `tests/experiments/test_panel.py` (Codex authors)

- [ ] **Step 1: Ensure `pyyaml` is available**

Check: `uv run python -c "import yaml; print(yaml.__version__)"`. If it errors, add `"pyyaml>=6.0"` to the `dependencies` list in `pyproject.toml` and run `uv sync`.

- [ ] **Step 2: Have Codex write the failing test (criteria-only portion)**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_panel.py. Module under test: src/yanantin/experiments/panel.py. It defines Pydantic v2 models: CandidateModel(id: str, family: str, size_tier: str, cost_tier: str); PanelCriteria(panel_id: str, rationale: str, context_length_min: int = 8000, exclude_patterns: list[str] = [], candidates: list[CandidateModel]); ResolvedModel(id, family, size_tier, cost_tier, prompt_cost: float, completion_cost: float, context_length: int, native_max_tokens: int); ResolvedPanel(panel_id: str, rationale: str, resolved_at: datetime, catalog_snapshot_sha: str, models: list[ResolvedModel]). It also defines load_criteria(path) -> PanelCriteria (yaml.safe_load then model_validate) and dump_resolved(panel: ResolvedPanel, path) -> None (write yaml.safe_dump of panel.model_dump(mode='json'), creating parent dirs). Tests for this task only: test_criteria_roundtrip(tmp_path): build a PanelCriteria with 2 candidates, yaml.safe_dump its model_dump to a file, load_criteria it back, assert equality. test_criteria_requires_candidates(): assert PanelCriteria(panel_id='x', rationale='y') raises ValidationError (candidates required, no default). test_dump_resolved_writes_yaml(tmp_path): build a ResolvedPanel with 1 model, dump_resolved to tmp_path/'sub'/'p.resolved.yaml', assert the file exists and yaml.safe_load of it has 'catalog_snapshot_sha' and models[0]['prompt_cost']. Do not write the implementation, and do not yet test resolve_panel — that is a separate task."`

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/experiments/test_panel.py -v`
Expected: FAIL — `panel` module not found

- [ ] **Step 4: Write `src/yanantin/experiments/panel.py` (models + YAML helpers; `resolve_panel` stub raising NotImplementedError)**

```python
# src/yanantin/experiments/panel.py
"""Model-panel criteria and resolution against the live OpenRouter catalog.

A panel is defined as *criteria* — a curated candidate list with tier
annotations (family / size / cost), defended on first principles before
tool design starts. Resolution validates each candidate against the live
catalog (still available? context-length ok? not excluded?) and enriches
it with current pricing and context limits. The resolved panel plus the
catalog fingerprint plus the OTS stamp on the commit is the verifiable
record of "which models, current as of when."
"""

from __future__ import annotations

import fnmatch
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from yanantin.experiments.catalog import catalog_snapshot_sha


class CandidateModel(BaseModel):
    id: str
    family: str
    size_tier: str
    cost_tier: str


class PanelCriteria(BaseModel):
    panel_id: str
    rationale: str
    context_length_min: int = 8000
    exclude_patterns: list[str] = []
    candidates: list[CandidateModel]


class ResolvedModel(BaseModel):
    id: str
    family: str
    size_tier: str
    cost_tier: str
    prompt_cost: float
    completion_cost: float
    context_length: int
    native_max_tokens: int


class ResolvedPanel(BaseModel):
    panel_id: str
    rationale: str
    resolved_at: datetime
    catalog_snapshot_sha: str
    models: list[ResolvedModel]


def load_criteria(path: str | Path) -> PanelCriteria:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return PanelCriteria.model_validate(data)


def dump_resolved(panel: ResolvedPanel, path: str | Path) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        yaml.safe_dump(panel.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )


# Default applied when a catalog entry lacks top_provider.max_completion_tokens.
DEFAULT_NATIVE_MAX_TOKENS = 4096


def resolve_panel(
    criteria: PanelCriteria,
    catalog: list[dict[str, Any]],
    *,
    resolved_at: datetime | None = None,
) -> ResolvedPanel:
    raise NotImplementedError  # implemented in Task 6
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/experiments/test_panel.py -v`
Expected: 3 passed (criteria-only tests)

- [ ] **Step 6: Commit**

```bash
git add src/yanantin/experiments/panel.py tests/experiments/test_panel.py pyproject.toml
git commit -m "feat(experiments): add panel-criteria schema and YAML helpers"
```

---

## Task 6: resolve_panel — validate candidates against the catalog

**Files:**
- Modify: `src/yanantin/experiments/panel.py`
- Test: `tests/experiments/test_panel.py` (Codex extends)

- [ ] **Step 1: Have Codex extend the test**

Run: `codex exec --full-auto -m gpt-5-codex "Extend tests/experiments/test_panel.py. resolve_panel(criteria: PanelCriteria, catalog: list[dict], *, resolved_at: datetime | None = None) -> ResolvedPanel now: for each candidate, finds the catalog entry with matching 'id' (raise ValueError naming the id if absent); raise ValueError if the candidate id matches any exclude_pattern (fnmatch); raise ValueError naming id and lengths if the catalog entry's context_length < criteria.context_length_min; otherwise build a ResolvedModel using candidate's family/size_tier/cost_tier, prompt_cost=float(entry['pricing']['prompt']), completion_cost=float(entry['pricing']['completion']), context_length=int(entry['context_length']), native_max_tokens=int(entry.get('top_provider', {}).get('max_completion_tokens') or DEFAULT_NATIVE_MAX_TOKENS where DEFAULT_NATIVE_MAX_TOKENS is 4096 importable from the module). resolved_at defaults to datetime.now(timezone.utc). catalog_snapshot_sha is computed from the passed catalog. Load tests/experiments/fixtures/openrouter_models_sample.json's 'data' list as the catalog in tests. test_resolve_happy(): criteria with candidates [(meta-llama/llama-4-scout, llama, large-open, cheap), (google/gemma-4-31b-it, gemma, mid, cheap), (z-ai/glm-4-32b, glm, mid, free)], context_length_min=8000, exclude_patterns=['*-audio-*']; resolve; assert 3 models, the glm one has prompt_cost==0.0 and native_max_tokens==8192, the scout one has context_length==131072 and native_max_tokens==16384, and panel.catalog_snapshot_sha matches catalog_snapshot_sha(catalog). test_resolve_missing_candidate(): include a candidate id 'no/such-model'; assert ValueError mentioning 'no/such-model'. test_resolve_excluded(): include 'openai/gpt-4o-audio-preview' with exclude_patterns=['*-audio-*']; assert ValueError. test_resolve_too_small_context(): include 'tiny/no-context-model' (ctx 2048) with context_length_min=8000; assert ValueError mentioning the id. test_resolve_default_native_max(): a catalog with a model whose top_provider lacks max_completion_tokens (use 'z-ai/glm-4-32b' is fine since it has 8192; instead use 'tiny/no-context-model' but lower context_length_min to 1000) -> assert native_max_tokens == 4096. Do not modify the implementation."`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/experiments/test_panel.py -v -k resolve`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `resolve_panel` in `panel.py`** (replace the stub body)

```python
def resolve_panel(
    criteria: PanelCriteria,
    catalog: list[dict[str, Any]],
    *,
    resolved_at: datetime | None = None,
) -> ResolvedPanel:
    """Validate each candidate against the live catalog and enrich it.

    Raises ValueError on: a candidate id not in the catalog; a candidate
    id matching an exclude_pattern; a catalog context_length below the
    criteria floor. Otherwise produces a ResolvedPanel fingerprinted to
    the exact catalog passed.
    """
    by_id = {entry["id"]: entry for entry in catalog if "id" in entry}
    resolved: list[ResolvedModel] = []
    for cand in criteria.candidates:
        if any(fnmatch.fnmatch(cand.id, pat) for pat in criteria.exclude_patterns):
            raise ValueError(f"candidate {cand.id!r} matches an exclude_pattern")
        entry = by_id.get(cand.id)
        if entry is None:
            raise ValueError(f"candidate {cand.id!r} not found in the OpenRouter catalog")
        ctx = int(entry.get("context_length", 0))
        if ctx < criteria.context_length_min:
            raise ValueError(
                f"candidate {cand.id!r} context_length {ctx} < required {criteria.context_length_min}"
            )
        pricing = entry.get("pricing", {})
        native = (entry.get("top_provider", {}) or {}).get("max_completion_tokens")
        resolved.append(
            ResolvedModel(
                id=cand.id,
                family=cand.family,
                size_tier=cand.size_tier,
                cost_tier=cand.cost_tier,
                prompt_cost=float(pricing.get("prompt", 0.0)),
                completion_cost=float(pricing.get("completion", 0.0)),
                context_length=ctx,
                native_max_tokens=int(native) if native else DEFAULT_NATIVE_MAX_TOKENS,
            )
        )
    from datetime import timezone

    return ResolvedPanel(
        panel_id=criteria.panel_id,
        rationale=criteria.rationale,
        resolved_at=resolved_at or datetime.now(timezone.utc),
        catalog_snapshot_sha=catalog_snapshot_sha(catalog),
        models=resolved,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/experiments/test_panel.py -v`
Expected: all passed (3 from Task 5 + 5 new)

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/experiments/panel.py tests/experiments/test_panel.py
git commit -m "feat(experiments): implement resolve_panel against live catalog"
```

---

## Task 7: First panel criteria file + data-dir scaffolding

**Files:**
- Create: `experiments/memory_tools/.gitkeep`
- Create: `experiments/memory_tools/panels/iteration_v1.criteria.yaml`
- Test: `tests/experiments/test_panel.py` (Codex adds one test that resolves the real criteria against the fixture catalog where ids overlap, else just asserts the file loads)

- [ ] **Step 1: Create `experiments/memory_tools/.gitkeep`** (empty file).

- [ ] **Step 2: Create `experiments/memory_tools/panels/iteration_v1.criteria.yaml`**

Use the spec's "as of 2026-05-12 this resolves to roughly..." sketch as the candidate list. The exact ids must be validated against the live catalog at pre-registration time (Task 8 does that) — if any have rotated out by then, the preregister run will fail loudly and the list gets corrected via a deliberate commit. Tiers reflect the spec's spread axes.

```yaml
panel_id: iteration_v1
rationale: >
  ~15 current-gen models spanning family x size x cost, defended on first
  principles before tool design starts. Training set for tool-design
  iteration; in-fill panels are the cross-validation set, registered later.
  Tiny tier intentionally uses older-by-version models (no same-family
  successor exists at that size).
context_length_min: 8000
exclude_patterns:
  - "*-audio-*"
  - "*:online"
candidates:
  # tiny
  - {id: "meta-llama/llama-3.2-1b-instruct", family: llama, size_tier: tiny, cost_tier: cheap}
  - {id: "google/gemma-3n-e4b-it",          family: gemma, size_tier: tiny, cost_tier: cheap}
  # small
  - {id: "qwen/qwen3.5-9b",                  family: qwen,    size_tier: small, cost_tier: cheap}
  - {id: "google/gemma-4-26b-a4b-it",        family: gemma,   size_tier: small, cost_tier: cheap}
  - {id: "microsoft/phi-4-mini-instruct",    family: phi,     size_tier: small, cost_tier: cheap}
  - {id: "ibm-granite/granite-4.1-8b",       family: granite, size_tier: small, cost_tier: cheap}
  # mid
  - {id: "mistralai/mistral-small-3.2-24b-instruct", family: mistral, size_tier: mid, cost_tier: cheap}
  - {id: "google/gemma-4-31b-it",            family: gemma,  size_tier: mid, cost_tier: cheap}
  - {id: "qwen/qwen3-32b",                   family: qwen,   size_tier: mid, cost_tier: cheap}
  - {id: "liquid/lfm-2-24b-a2b",             family: liquid, size_tier: mid, cost_tier: cheap}
  - {id: "openai/gpt-oss-20b",               family: gpt-oss, size_tier: mid, cost_tier: cheap}
  # large-open
  - {id: "meta-llama/llama-4-scout",         family: llama,   size_tier: large-open, cost_tier: cheap}
  - {id: "qwen/qwen3-coder-30b-a3b-instruct", family: qwen,   size_tier: large-open, cost_tier: cheap}
  - {id: "openai/gpt-oss-120b",              family: gpt-oss, size_tier: large-open, cost_tier: cheap}
  # frontier-cheap
  - {id: "anthropic/claude-haiku-4-5",       family: anthropic-haiku, size_tier: small, cost_tier: frontier-cheap}
  - {id: "google/gemini-2.5-flash-lite",     family: google-flash-lite, size_tier: small, cost_tier: frontier-cheap}
  - {id: "deepseek/deepseek-v4-flash",       family: deepseek, size_tier: mid, cost_tier: frontier-cheap}
```

> The candidate ids are best-effort from the cairn scout corpus as of 2026-05-12; OpenRouter slugs may differ slightly (e.g. `ibm-granite/` vs `granite/`, `liquid/lfm-2-24b-a2b` slug form). Task 8's first `--dry-run` against the live catalog is what nails them down. Treat a resolution failure here as expected first-run friction, not a bug.

- [ ] **Step 3: Have Codex add a test**

Run: `codex exec --full-auto -m gpt-5-codex "Add to tests/experiments/test_panel.py: test_iteration_v1_criteria_loads(): load_criteria('experiments/memory_tools/panels/iteration_v1.criteria.yaml'); assert panel_id == 'iteration_v1', len(candidates) >= 12, every candidate has non-empty id/family/size_tier/cost_tier, and the set of size_tier values is a subset of {'tiny','small','mid','large-open'} and includes at least 'tiny','small','mid','large-open'. Do not resolve it against a live catalog (that needs network)."`

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/experiments/test_panel.py -v -k iteration_v1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add experiments/memory_tools/.gitkeep experiments/memory_tools/panels/iteration_v1.criteria.yaml tests/experiments/test_panel.py
git commit -m "feat(experiments): add iteration_v1 panel criteria and data-dir scaffolding"
```

---

## Task 8: Preregister CLI

**Files:**
- Create: `src/yanantin/experiments/preregister.py`
- Test: `tests/experiments/test_preregister.py` (Codex authors)

The CLI: `python -m yanantin.experiments.preregister --exp <experiment_id> [--dry-run] [--stage]`.
Behavior:
1. Read `experiments/memory_tools/<experiment_id>/preregistration.yaml` — must already exist and name a `panel_id`. (Error if missing.)
2. Read `experiments/memory_tools/panels/<panel_id>.criteria.yaml` via `load_criteria`.
3. Fetch the live catalog via `fetch_openrouter_catalog` (override hook: a `--catalog-json <path>` flag for tests, reading a saved catalog body instead of calling the network).
4. `resolve_panel(criteria, catalog)`.
5. Write `experiments/memory_tools/panels/<panel_id>.resolved.yaml` via `dump_resolved`.
6. Patch the experiment's `preregistration.yaml` to add `panel_resolved: <relative path>`, `resolved_at`, `catalog_snapshot_sha`.
7. If `--dry-run`: print what would be written, write nothing, exit 0.
8. If `--stage`: `git add` the resolved.yaml, the criteria.yaml, and the preregistration.yaml. (Does not commit — `scripts/register-experiment` commits.)

- [ ] **Step 1: Have Codex write the failing test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_preregister.py. Module under test: src/yanantin/experiments/preregister.py, exposing main(argv: list[str]) -> int and runnable as python -m yanantin.experiments.preregister. Use a tmp git repo: tmp_path with 'git init', and chdir into it (use monkeypatch.chdir). Create experiments/memory_tools/panels/p1.criteria.yaml (a minimal PanelCriteria with 1 candidate id 'meta-llama/llama-4-scout', family llama, size_tier large-open, cost_tier cheap, context_length_min 8000, exclude_patterns []), and experiments/memory_tools/exp_alpha/preregistration.yaml containing {experiment_id: exp_alpha, panel_id: p1}. Save tests/experiments/fixtures/openrouter_models_sample.json's content into a tmp catalog file (or reference the repo-relative fixture via an absolute path computed from __file__). test_dry_run_writes_nothing(): main(['--exp','exp_alpha','--catalog-json',str(catalog_path),'--dry-run']) returns 0; assert experiments/memory_tools/panels/p1.resolved.yaml does NOT exist. test_resolve_writes_manifests(): main(['--exp','exp_alpha','--catalog-json',str(catalog_path)]) returns 0; assert p1.resolved.yaml exists and yaml.safe_load has catalog_snapshot_sha and models[0]['id']=='meta-llama/llama-4-scout'; assert preregistration.yaml now has 'panel_resolved' and 'catalog_snapshot_sha' keys. test_missing_preregistration_errors(): main(['--exp','no_such_exp','--catalog-json',str(catalog_path)]) returns nonzero AND does not raise. test_stage_git_adds(): run main(['--exp','exp_alpha','--catalog-json',str(catalog_path),'--stage']); then subprocess 'git diff --cached --name-only' in tmp_path; assert it lists experiments/memory_tools/panels/p1.resolved.yaml and experiments/memory_tools/exp_alpha/preregistration.yaml. Do not write the implementation."`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/experiments/test_preregister.py -v`
Expected: FAIL — `preregister` module not found

- [ ] **Step 3: Write `src/yanantin/experiments/preregister.py`**

```python
# src/yanantin/experiments/preregister.py
"""Pre-registration CLI for memory-tool experiments.

Resolves a panel's criteria against the live OpenRouter catalog, writes
the resolved manifest, patches the experiment's preregistration.yaml with
the resolution fingerprint, and (with --stage) git-adds the files. The
commit itself — which fires yanantin's OTS post-commit hook — is done by
scripts/register-experiment so a human is in the loop for the binding act.

Usage:
    python -m yanantin.experiments.preregister --exp <id> [--dry-run] [--stage]
    python -m yanantin.experiments.preregister --exp <id> --catalog-json <path>   # tests
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from yanantin.experiments.catalog import fetch_openrouter_catalog
from yanantin.experiments.panel import dump_resolved, load_criteria, resolve_panel

MEMTOOLS_ROOT = Path("experiments/memory_tools")


def _load_catalog(catalog_json: str | None) -> list[dict]:
    if catalog_json:
        body = json.loads(Path(catalog_json).read_text(encoding="utf-8"))
        data = body.get("data", body) if isinstance(body, dict) else body
        if not isinstance(data, list):
            raise ValueError(f"catalog file {catalog_json} has no 'data' list")
        return data
    return asyncio.run(fetch_openrouter_catalog())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="preregister")
    parser.add_argument("--exp", required=True, help="experiment id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stage", action="store_true", help="git add the written files")
    parser.add_argument("--catalog-json", default=None, help="read catalog from file instead of the live API")
    args = parser.parse_args(argv)

    exp_dir = MEMTOOLS_ROOT / args.exp
    prereg_path = exp_dir / "preregistration.yaml"
    if not prereg_path.is_file():
        print(f"error: {prereg_path} not found", file=sys.stderr)
        return 2
    prereg = yaml.safe_load(prereg_path.read_text(encoding="utf-8")) or {}
    panel_id = prereg.get("panel_id")
    if not panel_id:
        print(f"error: {prereg_path} does not name a panel_id", file=sys.stderr)
        return 2

    criteria_path = MEMTOOLS_ROOT / "panels" / f"{panel_id}.criteria.yaml"
    if not criteria_path.is_file():
        print(f"error: {criteria_path} not found", file=sys.stderr)
        return 2

    try:
        criteria = load_criteria(criteria_path)
        catalog = _load_catalog(args.catalog_json)
        panel = resolve_panel(criteria, catalog, resolved_at=datetime.now(timezone.utc))
    except (ValueError, OSError) as exc:
        print(f"error: resolution failed: {exc}", file=sys.stderr)
        return 1

    resolved_path = MEMTOOLS_ROOT / "panels" / f"{panel_id}.resolved.yaml"
    if args.dry_run:
        print(f"[dry-run] would write {resolved_path} with {len(panel.models)} models")
        print(f"[dry-run] catalog_snapshot_sha={panel.catalog_snapshot_sha}")
        return 0

    dump_resolved(panel, resolved_path)
    prereg["panel_resolved"] = str(resolved_path)
    prereg["resolved_at"] = panel.resolved_at.isoformat()
    prereg["catalog_snapshot_sha"] = panel.catalog_snapshot_sha
    prereg_path.write_text(yaml.safe_dump(prereg, sort_keys=False), encoding="utf-8")
    print(f"wrote {resolved_path} ({len(panel.models)} models) and patched {prereg_path}")

    if args.stage:
        subprocess.run(
            ["git", "add", str(resolved_path), str(criteria_path), str(prereg_path)],
            check=True,
        )
        print("staged: " + ", ".join(str(p) for p in (resolved_path, criteria_path, prereg_path)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/experiments/test_preregister.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/experiments/preregister.py tests/experiments/test_preregister.py
git commit -m "feat(experiments): add preregister CLI for resolving and staging panel manifests"
```

---

## Task 9: register-experiment wrapper script

**Files:**
- Create: `scripts/register-experiment`
- Test: `tests/experiments/test_preregister.py` (Codex adds a smoke test invoking the script)

- [ ] **Step 1: Create `scripts/register-experiment`** (and `chmod +x` it)

```bash
#!/usr/bin/env bash
# Pre-register a memory-tool experiment: resolve its panel against the live
# OpenRouter catalog, write + stage the manifests, then commit. The commit
# fires .githooks/post-commit, which OTS-stamps it — that stamp is the
# verifiable proof the panel was current before any data was collected.
#
# Usage: scripts/register-experiment <experiment_id>
set -euo pipefail

EXP="${1:?usage: scripts/register-experiment <experiment_id>}"
PREREG="experiments/memory_tools/${EXP}/preregistration.yaml"
test -f "$PREREG" || { echo "missing $PREREG" >&2; exit 1; }

uv run python -m yanantin.experiments.preregister --exp "$EXP" --stage
git commit -m "Pre-register experiment: ${EXP} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "Pre-registered ${EXP}. OTS proof will land in docs/ots/ shortly (post-commit hook runs in background; see logs/ots.log)."
```

Then: `chmod +x scripts/register-experiment`.

- [ ] **Step 2: Have Codex add a smoke test**

Run: `codex exec --full-auto -m gpt-5-codex "Add to tests/experiments/test_preregister.py: test_register_script_errors_without_preregistration(tmp_path, monkeypatch): copy scripts/register-experiment into a tmp git repo (or run it via its absolute repo path with cwd=tmp_path); run it with arg 'ghost_exp' and assert the process exits nonzero and stderr contains 'missing'. Use subprocess.run with capture_output=True, text=True. Do not require network or uv inside the test — if the script gets past the existence check it would call uv; the test only needs to confirm the existence-check failure path, so 'ghost_exp' (no preregistration.yaml) is sufficient and never reaches the uv call."`

- [ ] **Step 3: Run to verify pass**

Run: `uv run pytest tests/experiments/test_preregister.py -v -k register_script`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/register-experiment tests/experiments/test_preregister.py
git commit -m "feat(experiments): add register-experiment wrapper (commit + OTS stamp)"
```

---

## Task 10: End-to-end smoke — capture a real OpenRouter call

**Files:**
- Test: `tests/experiments/test_smoke_capture.py` (Codex authors) — an `@pytest.mark.integration` test that doubles as the executable smoke check.

This is the spec's step-3 "end-to-end smoke test on whichever free model the catalog resolution picks." It validates the capture layer against real data: one real `OpenRouterClient.complete()` call, the response (or error) packed into a `CaptureRecord` with no truncation, written via `CaptureWriter`, loaded back, asserted.

- [ ] **Step 1: Have Codex write the integration test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_smoke_capture.py with one test, test_capture_real_openrouter_call(tmp_path), marked @pytest.mark.integration; pytest.skip if OPENROUTER_API_KEY not in os.environ. The test: import OpenRouterClient from yanantin.apacheta.clients.openrouter; import CaptureRecord, CaptureWriter, load_run from yanantin.experiments.capture; pick a known-cheap model id 'meta-llama/llama-3.2-1b-instruct' (string literal MODEL); build messages=[{'role':'user','content':'Reply with exactly the word: pong'}]; record t0=time.monotonic(); inside a try/except over httpx.HTTPStatusError and httpx.RequestError: async-call client.complete(model=MODEL, messages=messages, max_tokens=16, metadata={'X-Title':'yanantin:memtool:smoke'}) using asyncio.run on an async helper that does 'async with OpenRouterClient() as c: return await c.complete(...)'; on success build a CaptureRecord with status='ok', record_id=str(uuid.uuid4()), timestamp=datetime.now(timezone.utc), experiment_id='smoke', panel_id='none', tool_variant_id='none', model_id=MODEL, prompt_template_id='inline', prompt_full=messages[0]['content'], request_full={'model':MODEL,'messages':messages,'max_tokens':16}, response_parsed={'content':resp.content,'id':resp.id,'model':resp.model}, response_raw_body=json.dumps(resp.raw), usage=resp.usage, elapsed_seconds=time.monotonic()-t0, error fields None; on HTTPStatusError e build status='error', response_parsed=None, response_raw_body=None, error_type='HTTPStatusError', error_message=str(e), error_payload=e.response.text, with the same other fields and usage={}; write the record via CaptureWriter(tmp_path/'smoke'/'r.jsonl'); then loaded=load_run(tmp_path/'smoke'/'r.jsonl'); assert len(loaded)==1; assert loaded[0].model_id==MODEL; assert loaded[0].status in {'ok','error'}; if status=='ok' assert isinstance(loaded[0].response_parsed['content'], str) and loaded[0].response_raw_body is not None; if status=='error' assert loaded[0].error_payload is not None. Keep it one self-contained test file."`

- [ ] **Step 2: Run it (skipped without a key, real call with one)**

Run (no key): `uv run pytest tests/experiments/test_smoke_capture.py -v` → 1 skipped.
Run (with key, this is the actual smoke check): `OPENROUTER_API_KEY=… uv run pytest tests/experiments/test_smoke_capture.py -v -s` → 1 passed; eyeball the printed record if `-s`. If it fails because the model slug rotated, swap `MODEL` for whatever the live catalog lists at the free/tiny tier and re-run — that swap is itself a finding worth noting in the commit message.

- [ ] **Step 3: Run the full experiments test suite**

Run: `uv run pytest tests/experiments/ -v -m "not integration"`
Expected: all unit tests pass. Then `uv run pytest tests/ -q` to confirm nothing else broke.

- [ ] **Step 4: Commit**

```bash
git add tests/experiments/test_smoke_capture.py
git commit -m "test(experiments): end-to-end smoke — real OpenRouter call into CaptureRecord"
```

---

## Done When

- `uv run pytest tests/experiments/ -m "not integration"` is green.
- With `OPENROUTER_API_KEY` set, `uv run pytest tests/experiments/test_smoke_capture.py` passes and produces a well-formed `CaptureRecord` from a real call.
- `uv run python -m yanantin.experiments.preregister --exp <some-exp> --catalog-json experiments/.../sample.json --dry-run` prints a sane resolution against the fixture catalog.
- (Manual, when ready to actually pre-register the first experiment) `scripts/register-experiment <exp>` commits the resolved manifest and an OTS proof appears in `docs/ots/`.

## Next Plan

`docs/plans/2026-05-13-memory-tool-harness-runner-and-tools.md` (to be written): extend `OpenRouterClient` for function-calling tool definitions; the runner loop (model × tool_variant × prompt → capture) with concurrency, per-call timeout, and per-run cost budget; the six tool functions (`find_objects`, `get_object`, `sample_objects`, `have_i_called`, `have_i_requested`, `request_capability`) wired to the apacheta interface (read-only against `apacheta_test`, per-run query budget); the prompt corpus; and the name-effect experiment (`find_objects` vs `search` vs `query`, identical signatures and descriptions). Out of scope there too: in-fill panels, the analyst tier, MCP wrapping.

---

## Self-Review

**Spec coverage (this plan = spec impl-order steps 1-2 + step-3 smoke):**
- Capture layer: schema-open record (Task 1, `extra="allow"`), no-truncation fields — `request_full`, `response_raw_body`, `error_payload`, usage-on-error (Tasks 1 & 10) ✓; JSONL per run, flush each write (Task 2) ✓; loader (Task 3) ✓. *Not covered:* `panel_id`/`experiment_id`/`tool_variant_id`/`prompt_template_id` are *fields* on the record (Task 1) but the *runner* that populates them per-call is the next plan — correct per scope.
- Panel-as-manifest, criteria-not-hardcoded, resolved against live catalog at pre-registration, `resolved_at` + `catalog_snapshot_sha` recorded (Tasks 4-8) ✓; iteration_v1 candidate list from the spec sketch (Task 7) ✓.
- Pre-registration discipline: `preregister --stage` resolves + writes + git-adds (Task 8) ✓; wrapper script commits, OTS hook (already installed) stamps (Task 9) ✓. *Not covered:* OTS-proof *verification* helper — spec marks it "used later"; deferred to a later plan, noted in spec's out-of-scope.
- Sandbox (apacheta_test, isolated collection, query budget): not in this plan — those constraints bind the *tool functions* and *runner*, which are the next plan. Flagged in "Next Plan".
- End-to-end smoke on a free-tier model (spec impl step 3): Task 10 ✓.

**Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N". Every code step shows complete code; every test step hands Codex a complete behavioral spec with explicit assertions. The one soft spot — Task 7's candidate ids being best-effort — is explicitly called out as expected first-run friction with a defined resolution path (Task 8 `--dry-run`), not a hidden gap.

**Type consistency:** `CaptureRecord` fields used identically in Tasks 1, 2, 3, 10. `CaptureWriter(path)` / `.write()` / `.close()` / context-manager — consistent Tasks 2, 10. `load_run(path) -> list[CaptureRecord]` — consistent Tasks 3, 10. `PanelCriteria` / `CandidateModel` / `ResolvedModel` / `ResolvedPanel` field names — consistent Tasks 5, 6, 8. `resolve_panel(criteria, catalog, *, resolved_at=None)` — consistent Tasks 6, 8. `catalog_snapshot_sha(catalog)` — consistent Tasks 4, 6. `load_criteria` / `dump_resolved` — consistent Tasks 5, 6, 8. `DEFAULT_NATIVE_MAX_TOKENS = 4096` — defined Task 5, used Task 6. `main(argv)` — consistent Tasks 8, 9. No drift found.
