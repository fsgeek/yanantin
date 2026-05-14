# Memory-Tool Harness — Runner, First Tool Surface, Name-Effect Experiment

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project conventions that override the generic TDD flow:** CI enforces builder/tester separation (see `~/.claude/projects/-home-tony-projects-yanantin/memory/feedback_codex_tests.md`). Test files in this plan are authored via Codex, not by the implementing agent: `codex exec --full-auto -m gpt-5-codex "<spec>"`. The test code shown in each task is the *specification* of what Codex must produce — hand Codex the test description and the assertions, have it write the file, then run it to confirm it fails before writing implementation. The implementing agent writes the implementation; Codex writes the tests. Codex 0.130.0 needs `< /dev/null` appended to the shell command (see `feedback_codex_and_prescription.md`).

**Goal:** Stand up the experimental loop on top of the foundation: extend `OpenRouterClient` with function-calling, build a runner that drives `(model × tool_variant × prompt) → CaptureRecord` with cost/turn budgets, bind the first three tool variants (`find_objects` / `search` / `query` — identical signatures, only the name differs) to `apacheta_test`, and pre-register + smoke-run the name-effect experiment.

**Architecture:** A new `yanantin.experiments.tools` package holds tool schemas (OpenAI/OpenRouter function-calling format), the `find_objects` Python implementation (read-only against the apacheta interface, query-budget guarded), and the variant registry that maps each name (`find_objects` / `search` / `query`) to the same impl with a different schema name. `yanantin.experiments.prompts` (single module) loads prompt templates from `experiments/memory_tools/prompts/` and computes content-hash IDs. `yanantin.experiments.budget` enforces a per-run cost ceiling. `yanantin.experiments.runner` glues it: reads a pre-registration manifest, iterates the cartesian product, drives a bounded agent loop per task, writes one `CaptureRecord` per LLM call. The name-effect experiment is the first thing the runner runs.

**Tech Stack:** Python 3.14, Pydantic v2, `httpx` (async, already a dep), `pytest` with the `integration` marker introduced in the foundation plan, OpenAI-compatible function-calling via OpenRouter (no SDK — `httpx` directly, same as the existing client).

**Spec:** `docs/specs/2026-05-11-memory-tool-experimental-harness-design.md` ("Runner", "Tool Surface", "First Experiment: Name Effect"). This plan implements spec implementation-order steps 3, 4, and the smoke-run portion of step 5. The full iteration sweep is operator-driven (one shell command) after the smoke-run passes.

**Foundation (already landed):** `CaptureRecord` / `CaptureWriter` / `load_run` (`src/yanantin/experiments/capture.py`); catalog fetch + sha (`catalog.py`); `PanelCriteria` / `ResolvedPanel` / `resolve_panel` (`panel.py`); `preregister --stage` CLI + `scripts/register-experiment`; `experiments/memory_tools/panels/iteration_v1.criteria.yaml`.

**Out of scope (future plans):**
- The other five tool functions (`get_object`, `sample_objects`, `have_i_called`, `have_i_requested`, `request_capability`). Added when the experiments call for them.
- In-fill panels (`infill_v1`, etc.). Same resolution mechanism, registered post-design-convergence.
- The analyst tier (LLM tools that read aggregated records).
- MCP wrapping of the tool surface (graduation step, separate spec).
- Removal of project-scope limits in `taste_open`.
- Full iteration sweep against all 12-15 models — pre-registered manually once the smoke-run on one model per tier passes.

---

## File Structure

| File | Responsibility | New/Modified |
|------|----------------|--------------|
| `src/yanantin/apacheta/clients/openrouter.py` | Add `tools` / `tool_choice` to `complete()`; parse `tool_calls` into response | Modified |
| `src/yanantin/experiments/prompts.py` | `PromptTemplate`, `load_template()`, `compute_template_id()` (content-hash) | New |
| `src/yanantin/experiments/budget.py` | `CostBudget` — running total, raise `BudgetExceeded` on overrun | New |
| `src/yanantin/experiments/tools/__init__.py` | Package marker | New |
| `src/yanantin/experiments/tools/schemas.py` | `find_objects_schema(name)` — produces an OpenAI-format tool schema parameterized by display name | New |
| `src/yanantin/experiments/tools/apacheta_tools.py` | `find_objects_impl(apacheta, args, budget)` — routes `matching` to apacheta query methods, returns the envelope dict | New |
| `src/yanantin/experiments/tools/registry.py` | `ToolVariant` (id, schema, impl), `build_name_effect_variants()` | New |
| `src/yanantin/experiments/runner.py` | `RunnerConfig`, `run_experiment()` — the agent loop + capture | New |
| `experiments/memory_tools/prompts/find_a_record.yaml` | First prompt template for the name-effect experiment | New |
| `experiments/memory_tools/prompts/find_by_lineage.yaml` | Second prompt template | New |
| `experiments/memory_tools/prompts/find_by_author.yaml` | Third prompt template | New |
| `experiments/memory_tools/name_effect_v1/preregistration.yaml` | Pre-registration for the first experiment | New |
| `tests/experiments/test_openrouter_tool_calls.py` | Tests for the function-calling extension (unit + 1 integration) | New (Codex) |
| `tests/experiments/test_prompts.py` | Tests for template load + content-hash | New (Codex) |
| `tests/experiments/test_budget.py` | Tests for `CostBudget` | New (Codex) |
| `tests/experiments/test_tool_schemas.py` | Tests for `find_objects_schema(name)` | New (Codex) |
| `tests/experiments/test_apacheta_tools.py` | Tests for `find_objects_impl` against a fake apacheta | New (Codex) |
| `tests/experiments/test_tool_registry.py` | Tests for the variant registry | New (Codex) |
| `tests/experiments/test_runner.py` | Tests for `run_experiment` with a fake OpenRouter + fake apacheta | New (Codex) |
| `tests/experiments/test_name_effect_smoke.py` | Integration: one model per tier + name-effect variants, real apacheta_test, real OpenRouter | New (Codex) |

**Note on apacheta_test seeding:** `apacheta_test` exists (`yanantin.apacheta.connect(tier="test")`) but may be empty. The smoke test in Task 11 seeds a handful of open records via `store_record` before running, and the records carry distinct `author_instance_id` and `lineage_tags` so the prompts have something findable. Seeding is part of the smoke test's setup, not a separate task — it's three lines.

---

## Task 1: OpenRouterClient — function-calling extension

**Files:**
- Modify: `src/yanantin/apacheta/clients/openrouter.py`
- Test: `tests/experiments/test_openrouter_tool_calls.py` (Codex authors)

The OpenRouter chat-completions endpoint is OpenAI-compatible: `tools` is a list of `{"type": "function", "function": {"name", "description", "parameters"}}`; `tool_choice` is `"auto"` / `"none"` / `{"type": "function", "function": {"name": ...}}`; responses carry `choices[0].message.tool_calls` as `[{"id", "type": "function", "function": {"name", "arguments": <json-string>}}]` when the model invokes a tool.

- [ ] **Step 1: Have Codex write the failing test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_openrouter_tool_calls.py. Module under test: src/yanantin/apacheta/clients/openrouter.py. The OpenRouterClient.complete() method gains two new keyword-only parameters: tools (list of dict | None, default None) and tool_choice (str | dict | None, default None). When tools is provided the request JSON includes 'tools' (and 'tool_choice' if set). The OpenRouterResponse pydantic model gains a new optional field tool_calls: list[dict] | None = None — populated from raw['choices'][0]['message'].get('tool_calls') when present.

Use httpx MockTransport (httpx.MockTransport) and inject it into the client by patching the httpx.AsyncClient construction OR by exposing the underlying client. The cleanest approach: write a test helper class FakeRouter that wraps httpx.MockTransport and you assign it to client._client._transport, OR construct OpenRouterClient then replace client._client with httpx.AsyncClient(base_url=client.BASE_URL, transport=httpx.MockTransport(handler)). Use asyncio.run for awaits.

Tests, all unit (no integration mark):

test_tools_sent_in_request(): handler asserts the parsed json body has 'tools' equal to the tools list passed in and 'tool_choice' equal to 'auto', then returns a 200 response with empty content body shape {'id':'x','model':'m','choices':[{'message':{'content':'ok'}}],'usage':{}}. The test passes tools=[{'type':'function','function':{'name':'find_objects','description':'d','parameters':{'type':'object','properties':{},'required':[]}}}] and tool_choice='auto' to complete(). Assert the response.content == 'ok' and response.tool_calls is None.

test_tool_calls_parsed(): handler returns a body whose choices[0].message has tool_calls=[{'id':'call_1','type':'function','function':{'name':'find_objects','arguments':'{\"limit\":50}'}}] and content=None. complete() returns a response whose tool_calls equals exactly that list and content is '' (the existing default — the code does .get('content','')). 

test_tools_omitted_when_none(): handler asserts the parsed body has no 'tools' key and no 'tool_choice' key. complete() is called without tools/tool_choice.

Integration test (@pytest.mark.integration) test_tool_calls_live(): pytest.skip if no OPENROUTER_API_KEY. Use OpenRouterClient (real network), model='meta-llama/llama-3.2-1b-instruct', messages=[{'role':'user','content':'Use the lookup tool to find an item named foo.'}], tools=[{'type':'function','function':{'name':'lookup','description':'Look up an item by name','parameters':{'type':'object','properties':{'name':{'type':'string'}},'required':['name']}}}], tool_choice='auto', max_tokens=64. Assert the response.tool_calls is a list (it may be empty for very small models — that itself is a valid result; the assertion is just that the field is the right TYPE — list — when the model chose to call a tool, OR None when it didn't). So: assert response.tool_calls is None or isinstance(response.tool_calls, list). Print the response.tool_calls (use pytest -s) so a human running it can eyeball.

Do not write the implementation." < /dev/null`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/experiments/test_openrouter_tool_calls.py -v -m "not integration"`
Expected: FAIL — `tools` is an unexpected kwarg or `tool_calls` attribute missing on response.

- [ ] **Step 3: Implement the extension in `openrouter.py`**

Modify the `OpenRouterResponse` model to add the new field:

```python
class OpenRouterResponse(BaseModel):
    """Parsed response from OpenRouter API."""

    id: str = ""
    model: str = ""
    content: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

Modify `complete()`:

```python
async def complete(
    self,
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    metadata: dict[str, str] | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
) -> OpenRouterResponse:
    """Send a chat completion request.

    Adds optional OpenAI-compatible function-calling: pass `tools` to
    expose function definitions to the model, `tool_choice` to constrain
    its selection. When the model emits tool calls they land on
    `response.tool_calls` (a list of {id, type, function: {name, arguments}}
    dicts; arguments is a JSON string).
    """
    request_data: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if metadata:
        request_data["metadata"] = metadata
    if tools is not None:
        request_data["tools"] = tools
        if tool_choice is not None:
            request_data["tool_choice"] = tool_choice

    response = await self._client.post("/chat/completions", json=request_data)
    response.raise_for_status()

    raw = response.json()
    content = ""
    tool_calls: list[dict[str, Any]] | None = None
    if raw.get("choices"):
        message = raw["choices"][0].get("message", {}) or {}
        content = message.get("content") or ""
        tool_calls = message.get("tool_calls") or None

    return OpenRouterResponse(
        id=raw.get("id", ""),
        model=raw.get("model", model),
        content=content,
        usage=raw.get("usage", {}),
        raw=raw,
        tool_calls=tool_calls,
    )
```

Also widen the `messages` type annotation from `list[dict[str, str]]` to `list[dict[str, Any]]` — tool-result messages carry non-string fields (`tool_call_id`, structured `content`).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/experiments/test_openrouter_tool_calls.py -v -m "not integration"`
Expected: 3 passed.

- [ ] **Step 5: Run the integration test if the key is present**

Run: `uv run pytest tests/experiments/test_openrouter_tool_calls.py -v -s -m integration`
Expected: 1 passed (or 1 skipped if `OPENROUTER_API_KEY` unset). Eyeball the printed `tool_calls`.

- [ ] **Step 6: Commit**

```bash
git add src/yanantin/apacheta/clients/openrouter.py tests/experiments/test_openrouter_tool_calls.py
git commit -m "feat(openrouter): function-calling support (tools/tool_choice/tool_calls)"
```

---

## Task 2: Prompt template loader + content-hash IDs

**Files:**
- Create: `src/yanantin/experiments/prompts.py`
- Test: `tests/experiments/test_prompts.py` (Codex authors)

Prompt templates live in `experiments/memory_tools/prompts/<id>.yaml`. Schema:

```yaml
template_id: find_a_record      # display id, distinct from the content-hash id
description: |
  Ask the model to find a record by some attribute. The single text field
  is rendered as-is (no Jinja yet — keep it dumb until a real need shows up).
text: |
  Find a record whose author_instance_id is "scout-7" and tell me what
  lineage_tags it carries. If you cannot find one, say "not found".
```

`compute_template_id(text: str) -> str` returns a 12-char hex sha256 prefix — short enough to embed in record fields without bloat, long enough that collisions across the few-dozen-template corpus are negligible.

- [ ] **Step 1: Have Codex write the failing test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_prompts.py. Module under test: src/yanantin/experiments/prompts.py. It defines:
- A pydantic v2 PromptTemplate model with fields template_id: str, description: str = '', text: str, content_hash: str (auto-computed). content_hash is the first 12 hex chars of sha256(text.encode('utf-8')). Use a pydantic model_validator(mode='after') OR a computed_field — pick the simpler one. The model_config should be ConfigDict(frozen=True).
- load_template(path: pathlib.Path | str) -> PromptTemplate that yaml.safe_loads the file and validates.
- compute_template_id(text: str) -> str that returns the same 12-char hex hash. (Exposed so callers can compute a hash without building a full template.)

Tests:
test_compute_template_id_deterministic(): assert compute_template_id('hello') == compute_template_id('hello'), len == 12, only hex chars.
test_compute_template_id_different(): assert compute_template_id('a') != compute_template_id('b').
test_load_template_roundtrip(tmp_path): write a yaml file with template_id='t1', description='d', text='find the thing', load_template it, assert .template_id=='t1', .text=='find the thing', .content_hash==compute_template_id('find the thing').
test_template_frozen(): build a PromptTemplate, assert direct attribute assignment raises pydantic.ValidationError (frozen).
test_load_template_missing_text(tmp_path): write a yaml without 'text', assert load_template raises pydantic.ValidationError.

Do not write the implementation." < /dev/null`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/experiments/test_prompts.py -v`
Expected: FAIL — `prompts` module not found.

- [ ] **Step 3: Write `src/yanantin/experiments/prompts.py`**

```python
"""Prompt template store for the memory-tool harness.

Templates are tiny dumb YAML files — text plus an id. The content_hash
(12-char sha256 prefix) is the reproducibility key: even if the file is
renamed or edited, old captured records still point at the exact text
they used via this hash.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, computed_field


def compute_template_id(text: str) -> str:
    """12-char hex sha256 prefix of the template's rendered text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


class PromptTemplate(BaseModel):
    """One prompt template. text is what gets sent; content_hash is its fingerprint."""

    model_config = ConfigDict(frozen=True)

    template_id: str
    description: str = ""
    text: str

    @computed_field  # type: ignore[misc]
    @property
    def content_hash(self) -> str:
        return compute_template_id(self.text)


def load_template(path: str | Path) -> PromptTemplate:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return PromptTemplate.model_validate(data)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/experiments/test_prompts.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/experiments/prompts.py tests/experiments/test_prompts.py
git commit -m "feat(experiments): prompt template loader with content-hash IDs"
```

---

## Task 3: CostBudget — per-run cost ceiling

**Files:**
- Create: `src/yanantin/experiments/budget.py`
- Test: `tests/experiments/test_budget.py` (Codex authors)

- [ ] **Step 1: Have Codex write the failing test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_budget.py. Module under test: src/yanantin/experiments/budget.py. It defines class BudgetExceeded(RuntimeError) and class CostBudget with constructor CostBudget(ceiling_usd: float). Methods:
- .spent_usd: float property (sum of charges)
- .add(cost_usd: float) -> None: add to running total; if the new total exceeds ceiling_usd, raise BudgetExceeded with a message naming the ceiling and the current total.
- .remaining_usd: float property (ceiling_usd - spent_usd, may be negative if a single charge overshot the line)
- .ok() -> bool: True iff spent_usd < ceiling_usd
- The class is NOT frozen — it's stateful.

Tests:
test_budget_starts_zero(): CostBudget(1.0).spent_usd == 0.0, remaining_usd == 1.0, ok() is True.
test_budget_add(): b=CostBudget(1.0); b.add(0.3); b.add(0.2); assert b.spent_usd == pytest.approx(0.5) and b.remaining_usd == pytest.approx(0.5) and b.ok().
test_budget_exact_ceiling(): b=CostBudget(1.0); b.add(1.0); assert b.spent_usd == pytest.approx(1.0); the spec for ok() is 'strictly less than', so b.ok() is False — note carefully — and the call must NOT have raised (1.0 is not 'over' the ceiling, it IS the ceiling; raise only when strictly greater). Test that no exception was raised by the add() (it returned normally).
test_budget_exceeded_raises(): b=CostBudget(1.0); b.add(0.7); pytest.raises(BudgetExceeded) for b.add(0.4); after the raise, b.spent_usd should still equal 0.7 (the failed add must not have applied — the test must assert this; therefore the implementation must check before mutating).
test_budget_negative_charge_rejected(): pytest.raises(ValueError) for CostBudget(1.0).add(-0.01). Costs are non-negative.

Do not write the implementation." < /dev/null`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/experiments/test_budget.py -v`
Expected: FAIL — `budget` module not found.

- [ ] **Step 3: Write `src/yanantin/experiments/budget.py`**

```python
"""Per-run cost budget for the memory-tool harness.

OpenRouter responses carry per-call cost on `usage['cost']`. The runner
adds each completed call's cost to a CostBudget; when a call would push
the total over the ceiling, the runner halts before issuing it. This is
the runaway guard the spec calls for: an experiment can't silently burn
through more than its pre-registered budget.
"""

from __future__ import annotations


class BudgetExceeded(RuntimeError):
    """Raised when a charge would push the running total past the ceiling."""


class CostBudget:
    """Stateful running total against a fixed ceiling (US dollars)."""

    def __init__(self, ceiling_usd: float) -> None:
        if ceiling_usd < 0:
            raise ValueError(f"ceiling_usd must be non-negative, got {ceiling_usd!r}")
        self._ceiling = float(ceiling_usd)
        self._spent = 0.0

    @property
    def ceiling_usd(self) -> float:
        return self._ceiling

    @property
    def spent_usd(self) -> float:
        return self._spent

    @property
    def remaining_usd(self) -> float:
        return self._ceiling - self._spent

    def ok(self) -> bool:
        return self._spent < self._ceiling

    def add(self, cost_usd: float) -> None:
        if cost_usd < 0:
            raise ValueError(f"cost must be non-negative, got {cost_usd!r}")
        new_total = self._spent + cost_usd
        if new_total > self._ceiling:
            raise BudgetExceeded(
                f"adding {cost_usd:.6f} to {self._spent:.6f} would exceed ceiling {self._ceiling:.6f}"
            )
        self._spent = new_total
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/experiments/test_budget.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/experiments/budget.py tests/experiments/test_budget.py
git commit -m "feat(experiments): per-run CostBudget guard"
```

---

## Task 4: Tool schema definitions for the name-effect trio

**Files:**
- Create: `src/yanantin/experiments/tools/__init__.py` (empty package marker)
- Create: `src/yanantin/experiments/tools/schemas.py`
- Test: `tests/experiments/test_tool_schemas.py` (Codex authors)

The name-effect experiment hinges on this: three tool variants with **identical signatures, identical descriptions, identical parameter schemas — only the function name differs.** A single factory `find_objects_schema(name)` produces the OpenAI-format tool definition parameterized by name. Any drift between variants would confound the experiment, so there's exactly one source of truth for the description and parameters.

- [ ] **Step 1: Have Codex write the failing test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_tool_schemas.py. Module under test: src/yanantin/experiments/tools/schemas.py. It defines:
- FIND_OBJECTS_DESCRIPTION: str — a multi-line description of the find_objects tool (the test only checks it's non-empty and the same string referenced by both variants — content audit is for humans).
- FIND_OBJECTS_PARAMETERS: dict — a JSON-schema object describing the parameters. Must have shape {'type':'object','properties':{'matching':{...},'limit':{...},'cursor':{...}},'required':[]}, where 'matching' is an object whose properties include 'author_instance_id' (string), 'lineage_tag' (string), and 'has_field' (string), all optional; 'limit' is an integer with default 50; 'cursor' is a string nullable.
- find_objects_schema(name: str) -> dict that returns {'type':'function','function':{'name':name,'description':FIND_OBJECTS_DESCRIPTION,'parameters':FIND_OBJECTS_PARAMETERS}}.

Tests:
test_schema_shape(): s = find_objects_schema('find_objects'); assert s['type']=='function' and s['function']['name']=='find_objects' and 'description' in s['function'] and s['function']['parameters']['type']=='object'.
test_schema_description_is_constant(): assert find_objects_schema('find_objects')['function']['description'] == find_objects_schema('search')['function']['description'] == find_objects_schema('query')['function']['description']. (This is THE invariant the experiment depends on.)
test_schema_parameters_is_constant(): assert find_objects_schema('find_objects')['function']['parameters'] == find_objects_schema('search')['function']['parameters'] == find_objects_schema('query')['function']['parameters'].
test_parameters_documented_keys(): params = FIND_OBJECTS_PARAMETERS; props = params['properties']; assert set(props.keys()) == {'matching','limit','cursor'}; assert 'author_instance_id' in props['matching']['properties']; assert 'lineage_tag' in props['matching']['properties']; assert 'has_field' in props['matching']['properties']; assert props['limit'].get('default') == 50; assert params.get('required') == [].
test_parameters_isolated(): mutating the returned schema's parameters should not affect the next call's return value. Specifically: s1 = find_objects_schema('find_objects'); s1['function']['parameters']['properties']['matching']['properties']['injected'] = {'type':'string'}; s2 = find_objects_schema('search'); assert 'injected' not in s2['function']['parameters']['properties']['matching']['properties']. (Defensive: the factory must return a deep copy or build fresh each call.)

Do not write the implementation." < /dev/null`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/experiments/test_tool_schemas.py -v`
Expected: FAIL — `tools.schemas` module not found.

- [ ] **Step 3: Write `src/yanantin/experiments/tools/__init__.py`** (empty file)

- [ ] **Step 4: Write `src/yanantin/experiments/tools/schemas.py`**

```python
"""OpenAI-format function-calling schemas for the memory-tool harness.

The name-effect experiment turns on three variants of the same tool —
identical description, identical parameters, only the function name
differs. `find_objects_schema(name)` is the single source of truth so
the variants cannot drift apart.
"""

from __future__ import annotations

import copy
from typing import Any

FIND_OBJECTS_DESCRIPTION = (
    "Find records matching the given attributes in the associative memory store. "
    "Returns up to `limit` results, ordered newest-first. Use `matching` to filter "
    "by author_instance_id (records produced by a specific author), lineage_tag "
    "(records carrying a specific lineage tag), or has_field (records that carry a "
    "specific free-form key). Each result is an object with id, author_instance_id, "
    "lineage_tags, and any free-form fields the record carries. If more results "
    "exist than requested, `next_cursor` is non-null and can be passed back to "
    "fetch the next page; otherwise it is null."
)

_FIND_OBJECTS_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "matching": {
            "type": "object",
            "description": "Filter criteria. Any combination of keys may be supplied.",
            "properties": {
                "author_instance_id": {
                    "type": "string",
                    "description": "Records produced by this author instance.",
                },
                "lineage_tag": {
                    "type": "string",
                    "description": "Records tagged with this lineage tag.",
                },
                "has_field": {
                    "type": "string",
                    "description": "Records carrying this free-form key.",
                },
            },
            "additionalProperties": False,
        },
        "limit": {
            "type": "integer",
            "description": "Maximum number of records to return.",
            "default": 50,
            "minimum": 1,
            "maximum": 200,
        },
        "cursor": {
            "type": ["string", "null"],
            "description": "Pagination cursor from a previous response's next_cursor; null to start.",
        },
    },
    "required": [],
    "additionalProperties": False,
}


def find_objects_schema(name: str) -> dict[str, Any]:
    """Build a tool schema with the given function name.

    Returns a deep copy of the parameters so callers can mutate the
    returned dict without leaking state between variants.
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": FIND_OBJECTS_DESCRIPTION,
            "parameters": copy.deepcopy(_FIND_OBJECTS_PARAMETERS),
        },
    }


# Public alias for tests that want to read the canonical parameters.
FIND_OBJECTS_PARAMETERS = _FIND_OBJECTS_PARAMETERS
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/experiments/test_tool_schemas.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/yanantin/experiments/tools/__init__.py src/yanantin/experiments/tools/schemas.py tests/experiments/test_tool_schemas.py
git commit -m "feat(experiments): tool schemas for the find/search/query name-effect trio"
```

---

## Task 5: find_objects implementation against apacheta

**Files:**
- Create: `src/yanantin/experiments/tools/apacheta_tools.py`
- Test: `tests/experiments/test_apacheta_tools.py` (Codex authors)

The tool function takes an `ApachetaInterface` (already-connected backend), a `dict` of arguments parsed from the model's tool call, and a query-budget integer. It routes `matching` to one of the existing apacheta read methods, packs the results into the response envelope, and decrements the budget. Read-only — never calls `store_*`.

Routing rule: if `matching` has `author_instance_id` → `query_open_by_author_instance`; else if `lineage_tag` → `query_open_by_lineage_tag`; else if `has_field` → `query_open_has_field`; else `list_open_records`. If multiple are set, the first one in that priority order is used and the others are returned in the envelope's `ignored_filters` so the analyst can spot tools-misuse.

- [ ] **Step 1: Have Codex write the failing test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_apacheta_tools.py. Module under test: src/yanantin/experiments/tools/apacheta_tools.py. It defines:
- class QueryBudgetExceeded(RuntimeError)
- class QueryBudget(remaining: int) with .charge() that decrements by 1, raising QueryBudgetExceeded if remaining would go negative. .remaining property exposes the count.
- find_objects_impl(apacheta, args: dict, budget: QueryBudget) -> dict. Calls budget.charge() exactly once. Routes args.get('matching', {}) by priority order: author_instance_id → apacheta.query_open_by_author_instance(value, limit=L); lineage_tag → apacheta.query_open_by_lineage_tag(value, limit=L); has_field → apacheta.query_open_has_field(value, limit=L); else apacheta.list_open_records(limit=L). L = args.get('limit', 50). Cursor is accepted but ignored in this iteration (the envelope still carries next_cursor=None) — record the input cursor in the envelope as 'received_cursor' so we can tell the model passed something. The returned envelope:
    {
        'results': [{'id': str(rid), 'author_instance_id': <from record envelope if present else None>, 'lineage_tags': <from record if list else []>, 'fields': <model_extra or {}>}, ...],
        'total_matched': len(results),
        'next_cursor': None,
        'diversity': None,
        'cost_hint': {'queries_remaining': budget.remaining},
        'ignored_filters': [<list of matching keys that were present but not used, in order>],
        'received_cursor': <input cursor or None>,
    }

Use a tiny FakeApacheta in the test file: a class with the four query methods we route to plus a configurable return value per method (list of (UUID, ApachetaBaseModel) tuples). Build records via a simple subclass FakeRecord(ApachetaBaseModel) with model_config ConfigDict(extra='allow'); construct records with arbitrary fields like FakeRecord(provenance={'author_instance_id':'a1'}, lineage_tags=['tagX'], colour='blue').

Tests:
test_routes_to_author_query(): FakeApacheta returns one record for query_open_by_author_instance; call find_objects_impl(fake, {'matching':{'author_instance_id':'a1'},'limit':10}, QueryBudget(5)); assert fake's query_open_by_author_instance was called with ('a1', limit=10); assert envelope['results'][0]['author_instance_id']=='a1'; assert envelope['total_matched']==1; assert envelope['next_cursor'] is None; assert envelope['cost_hint']['queries_remaining']==4.
test_routes_to_lineage_query(): same shape but matching={'lineage_tag':'tagX'}; assert correct method called and result has lineage_tags containing 'tagX'.
test_routes_to_has_field_query(): matching={'has_field':'colour'}; assert correct method called; assert envelope['results'][0]['fields'].get('colour')=='blue'.
test_routes_to_list_when_no_matching(): no matching; assert list_open_records called and results returned.
test_priority_order_records_ignored_filters(): matching={'author_instance_id':'a1','lineage_tag':'tagX','has_field':'colour'}; assert author query was used; assert envelope['ignored_filters']==['lineage_tag','has_field'].
test_received_cursor_passed_through(): args={'cursor':'c123'}; assert envelope['received_cursor']=='c123'.
test_budget_charged(): budget=QueryBudget(2); find_objects_impl(fake, {}, budget); assert budget.remaining==1; find_objects_impl(fake, {}, budget); assert budget.remaining==0; pytest.raises(QueryBudgetExceeded) for find_objects_impl(fake, {}, budget) (the third call); assert budget.remaining==0 (no decrement on the failed call).

Do not write the implementation." < /dev/null`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/experiments/test_apacheta_tools.py -v`
Expected: FAIL — `apacheta_tools` module not found.

- [ ] **Step 3: Write `src/yanantin/experiments/tools/apacheta_tools.py`**

```python
"""Python implementations of the memory tools against the apacheta interface.

Currently: just `find_objects_impl`. Read-only against the supplied
ApachetaInterface. Query-budget guarded so a runaway model can't enumerate
the whole store in one trajectory.

Routing priority for the `matching` filter, when multiple keys are
supplied: author_instance_id > lineage_tag > has_field > (no filter →
list_open_records). Ignored keys are returned in `ignored_filters` so
the analyst can tell when the model gave us conflicting filters.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from yanantin.apacheta.interface.abstract import ApachetaInterface


class QueryBudgetExceeded(RuntimeError):
    """Raised when a tool call would exceed its remaining query budget."""


class QueryBudget:
    """Simple decrementing counter. One charge per tool call."""

    def __init__(self, remaining: int) -> None:
        if remaining < 0:
            raise ValueError(f"remaining must be non-negative, got {remaining!r}")
        self._remaining = int(remaining)

    @property
    def remaining(self) -> int:
        return self._remaining

    def charge(self) -> None:
        if self._remaining <= 0:
            raise QueryBudgetExceeded("query budget exhausted")
        self._remaining -= 1


_FILTER_PRIORITY = ("author_instance_id", "lineage_tag", "has_field")


def _envelope_for(records: list[tuple[UUID, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rid, record in records:
        envelope = getattr(record, "provenance", None) or {}
        author = envelope.get("author_instance_id") if isinstance(envelope, dict) else None
        tags = getattr(record, "lineage_tags", None) or []
        if not isinstance(tags, list):
            tags = []
        extra = getattr(record, "model_extra", None) or {}
        out.append(
            {
                "id": str(rid),
                "author_instance_id": author,
                "lineage_tags": list(tags),
                "fields": dict(extra),
            }
        )
    return out


def find_objects_impl(
    apacheta: ApachetaInterface,
    args: dict[str, Any],
    budget: QueryBudget,
) -> dict[str, Any]:
    """Resolve a `find_objects`-shaped call against the apacheta store.

    `args` is the parsed dict of the model's tool-call arguments. Returns
    the canonical response envelope (see `tools/schemas.py`).
    """
    budget.charge()

    matching: dict[str, Any] = dict(args.get("matching") or {})
    limit = int(args.get("limit", 50))
    cursor = args.get("cursor")

    ignored: list[str] = []
    chosen: str | None = None
    for key in _FILTER_PRIORITY:
        if key in matching and matching[key]:
            if chosen is None:
                chosen = key
            else:
                ignored.append(key)

    if chosen == "author_instance_id":
        records = apacheta.query_open_by_author_instance(matching[chosen], limit=limit)
    elif chosen == "lineage_tag":
        records = apacheta.query_open_by_lineage_tag(matching[chosen], limit=limit)
    elif chosen == "has_field":
        records = apacheta.query_open_has_field(matching[chosen], limit=limit)
    else:
        records = apacheta.list_open_records(limit=limit)

    results = _envelope_for(records)
    return {
        "results": results,
        "total_matched": len(results),
        "next_cursor": None,
        "diversity": None,
        "cost_hint": {"queries_remaining": budget.remaining},
        "ignored_filters": ignored,
        "received_cursor": cursor,
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/experiments/test_apacheta_tools.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/experiments/tools/apacheta_tools.py tests/experiments/test_apacheta_tools.py
git commit -m "feat(experiments): find_objects_impl against apacheta with query budget"
```

---

## Task 6: Tool variant registry — name-effect trio

**Files:**
- Create: `src/yanantin/experiments/tools/registry.py`
- Test: `tests/experiments/test_tool_registry.py` (Codex authors)

A `ToolVariant` bundles three things the runner needs in one place: the variant's id (matches what goes into `tool_variant_id` on each `CaptureRecord`), the OpenAI tool schema to expose to the model, and the Python implementation to call when the model invokes the tool. `build_name_effect_variants()` produces the three variants; they all point at the same `find_objects_impl` but expose three different function names in their schemas.

- [ ] **Step 1: Have Codex write the failing test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_tool_registry.py. Module under test: src/yanantin/experiments/tools/registry.py. It defines:
- @dataclass(frozen=True) class ToolVariant with fields: variant_id: str, function_name: str, schema: dict, impl: Callable[[ApachetaInterface, dict, QueryBudget], dict]
- build_name_effect_variants() -> list[ToolVariant] returning exactly three variants in this order: variant_id='find_objects_v1' with function_name='find_objects'; variant_id='search_v1' with function_name='search'; variant_id='query_v1' with function_name='query'. All three have impl=find_objects_impl (imported from apacheta_tools) and schema=find_objects_schema(function_name) (imported from schemas).

Tests:
test_three_variants(): vs = build_name_effect_variants(); assert len(vs)==3; assert [v.variant_id for v in vs] == ['find_objects_v1','search_v1','query_v1']; assert [v.function_name for v in vs] == ['find_objects','search','query'].
test_schemas_use_correct_names(): vs = build_name_effect_variants(); assert vs[0].schema['function']['name']=='find_objects'; assert vs[1].schema['function']['name']=='search'; assert vs[2].schema['function']['name']=='query'.
test_impl_is_same_callable(): vs = build_name_effect_variants(); assert vs[0].impl is vs[1].impl is vs[2].impl. (The whole point of the experiment: identical implementation, different names.)
test_variant_frozen(): vs = build_name_effect_variants(); pytest.raises((AttributeError, dataclasses.FrozenInstanceError)) for setattr(vs[0], 'variant_id', 'x'). Import dataclasses at the top.

Do not write the implementation." < /dev/null`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/experiments/test_tool_registry.py -v`
Expected: FAIL — `registry` module not found.

- [ ] **Step 3: Write `src/yanantin/experiments/tools/registry.py`**

```python
"""Tool variant registry for the memory-tool harness.

A ToolVariant is the unit the runner iterates over: variant_id (what gets
stamped on captured records), function_name (what the schema advertises
to the model), schema (the dict passed to OpenRouter as a tool), and impl
(the Python callable invoked when the model issues a tool call). For the
name-effect experiment, the three variants share an impl and a schema
shape — only the function_name differs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from yanantin.apacheta.interface.abstract import ApachetaInterface

from yanantin.experiments.tools.apacheta_tools import (
    QueryBudget,
    find_objects_impl,
)
from yanantin.experiments.tools.schemas import find_objects_schema

ToolImpl = Callable[[ApachetaInterface, dict[str, Any], QueryBudget], dict[str, Any]]


@dataclass(frozen=True)
class ToolVariant:
    variant_id: str
    function_name: str
    schema: dict[str, Any]
    impl: ToolImpl


def build_name_effect_variants() -> list[ToolVariant]:
    """The three name-effect variants. Identical impl; different names."""
    return [
        ToolVariant(
            variant_id="find_objects_v1",
            function_name="find_objects",
            schema=find_objects_schema("find_objects"),
            impl=find_objects_impl,
        ),
        ToolVariant(
            variant_id="search_v1",
            function_name="search",
            schema=find_objects_schema("search"),
            impl=find_objects_impl,
        ),
        ToolVariant(
            variant_id="query_v1",
            function_name="query",
            schema=find_objects_schema("query"),
            impl=find_objects_impl,
        ),
    ]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/experiments/test_tool_registry.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/experiments/tools/registry.py tests/experiments/test_tool_registry.py
git commit -m "feat(experiments): tool variant registry for the name-effect trio"
```

---

## Task 7: Runner — agent loop + capture

**Files:**
- Create: `src/yanantin/experiments/runner.py`
- Test: `tests/experiments/test_runner.py` (Codex authors)

The runner glues everything: for each `(model, variant, prompt)` it drives a bounded agent loop with the OpenRouter client and the variant's schema. Each LLM call produces one `CaptureRecord`. The loop terminates when the model returns content with no tool_calls, when it hits `max_turns`, when the cost budget rejects the next call, or when a tool implementation raises.

```python
@dataclass(frozen=True)
class RunnerConfig:
    experiment_id: str
    panel_id: str
    capture_dir: Path        # records go to capture_dir / "{run_id}.jsonl"
    run_id: str
    cost_ceiling_usd: float
    max_turns: int = 6
    query_budget_per_task: int = 12
    per_call_timeout_s: float = 60.0
    max_tokens: int = 16384
    x_title: str = "yanantin:memtool"   # OpenRouter X-Title for cost attribution
    system_prompt: str = (
        "You are testing memory tools. Use the provided tool to answer the user's question. "
        "When you have the answer, respond with plain text — do not call the tool again."
    )

async def run_experiment(
    cfg: RunnerConfig,
    apacheta: ApachetaInterface,
    client: OpenRouterClient,
    panel_models: list[str],         # the resolved model ids
    variants: list[ToolVariant],
    prompts: list[PromptTemplate],
) -> Path:
    """Iterate (model × variant × prompt), drive the agent loop, capture each
    LLM call as one CaptureRecord. Returns the JSONL path written."""
```

**Each captured record carries extra fields (schema-open):** `task_id` (one per `(model, variant, prompt)` triple), `turn_idx` (0-based), `parent_record_id` (None on turn 0, else the previous turn's `record_id`), `terminated_by` (only on the last turn of a task: `"final_content"` / `"max_turns"` / `"budget"` / `"tool_error"` / `"http_error"`).

- [ ] **Step 1: Have Codex write the failing test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_runner.py. Module under test: src/yanantin/experiments/runner.py. It defines RunnerConfig (dataclass(frozen=True) with the fields shown in the task header) and async run_experiment(cfg, apacheta, client, panel_models, variants, prompts) -> pathlib.Path returning the path of the jsonl run file (cfg.capture_dir / f'{cfg.run_id}.jsonl').

Build a FakeOpenRouter that mimics the OpenRouterClient surface used by the runner: an async .complete(model, messages, tools, tool_choice, max_tokens, metadata, temperature=0.7) method returning an OpenRouterResponse-like object (you can import OpenRouterResponse directly and construct it). It takes a scripted list of (tool_calls, content, usage) per call and pops one off each invocation. Provide it with usage={'cost': 0.0001} so the budget remains.

Build a FakeApacheta whose query methods return small canned lists (UUID, FakeRecord) so find_objects_impl works without a database.

Tests (asyncio: use anyio's pytest plugin OR asyncio.run on a sync wrapper test):

test_one_task_one_turn(tmp_path): scripted FakeOpenRouter returns ([], 'final answer', {'cost':0.0001}) immediately (no tool call). Run with one model, one variant (build_name_effect_variants()[0]), one prompt (PromptTemplate(template_id='t1', text='hi')). Cost ceiling 1.0. Load the resulting jsonl; assert exactly 1 record, record.tool_variant_id=='find_objects_v1', record.status=='ok', record.model_dump()['turn_idx']==0, record.model_dump()['terminated_by']=='final_content', record.response_parsed['content']=='final answer'.

test_one_task_tool_then_final(tmp_path): scripted FakeOpenRouter returns two responses: first ([{'id':'c1','type':'function','function':{'name':'find_objects','arguments':'{\"matching\":{\"author_instance_id\":\"a1\"}}'}}], '', {'cost':0.0001}); second ([], 'done', {'cost':0.0001}). FakeApacheta returns 1 record on query_open_by_author_instance. After run_experiment: load jsonl; assert 2 records, both with the same task_id (extra field), turn_idx 0 then 1, the turn-1 record has parent_record_id equal to turn-0's record_id, the turn-0 record has terminated_by absent or None (it wasn't the final turn) while turn-1 has terminated_by=='final_content'. Also assert the turn-1 record's request_full['messages'] has length >= 3 (system + user + assistant-with-tool-call + tool message — actually for OpenRouter the assistant turn carries tool_calls and the tool-result is role='tool' with tool_call_id and content; so messages should be: [{'role':'system',...},{'role':'user',...},{'role':'assistant','tool_calls':[...]},{'role':'tool','tool_call_id':'c1','content':<json-string>}]). Assert exactly that shape on the second call's messages.

test_max_turns(tmp_path): scripted FakeOpenRouter ALWAYS returns a tool_call ({'id':'c','type':'function','function':{'name':'find_objects','arguments':'{}'}}, '', {'cost':0.0001}). Set max_turns=3. Run. Load jsonl. Assert 3 records, all same task_id, turn_idx 0,1,2; the last record's terminated_by=='max_turns'.

test_budget_halts_between_tasks(tmp_path): cost ceiling 0.00015; FakeOpenRouter scripted to charge 0.0001 per call and always return final content (no tool calls). Run with 2 models × 1 variant × 1 prompt = 2 tasks. The first task spends 0.0001, ok. The second task would spend another 0.0001 bringing total to 0.0002 > 0.00015 — runner should NOT issue the call. Load jsonl: assert exactly 1 record (the first task's), and runner returns normally (does not raise — budget exhaustion is a clean stop, not an exception). Hint: the runner checks 'will this call fit?' via a peek/predict pattern. One way: track per-task max expected charge as a small fixed estimate (e.g. cfg expects max_tokens × an estimate, OR — simpler — the runner attempts the call, observes the cost in the captured record, and on next call's pre-check uses CostBudget.remaining > 0 to decide whether to start the next *task*. Specify the simpler semantics: at the top of each task the runner checks budget.ok(); if not, it logs and stops cleanly. After a call completes, runner adds usage['cost'] to the budget — and if that addition itself would have raised BudgetExceeded (use a try/except), the runner captures the record but stops further work. The test above is consistent with this: first call spends 0.0001 (total 0.0001 < 0.00015 ok); before second task budget.ok() is True (0.0001 < 0.00015); the second call spends another 0.0001 attempting (total 0.0002); the budget.add raises BudgetExceeded, runner catches it and stops — but the record was already captured. So actually expect 2 records in this case, not 1. Update the test: assert exactly 2 records and that the run ended without raising. Add a NEW test test_budget_halts_before_task(tmp_path) where ceiling is 0.00005: the very first budget.ok() check fails (0.0 < 0.00005 is True actually — wait, 0.0 < 0.00005 is True so ok() returns True; the call goes; spending 0.0001 raises BudgetExceeded; one record captured. Fine, that's exercised by the case above. So: keep only the first variant of the budget test (2 records, no raise).

test_tool_error_terminates_task(tmp_path): scripted FakeOpenRouter returns one tool_call. FakeApacheta is replaced with a mock whose query_open_by_author_instance raises RuntimeError('db is on fire'). The runner catches that error inside the tool-execution path and terminates the task. Load jsonl: assert 1 record, terminated_by=='tool_error', status=='ok' (the LLM call itself succeeded — it was the tool execution that failed); the record's extra fields include 'tool_error_type'=='RuntimeError' and 'tool_error_message' contains 'fire'.

test_http_error_captured(tmp_path): FakeOpenRouter raises httpx.HTTPStatusError on the first call (build the error: httpx.HTTPStatusError(message='400 Bad Request', request=httpx.Request('POST','http://x'), response=httpx.Response(400, text='{\"error\":\"bad\"}', request=httpx.Request('POST','http://x')))). Run; load; assert 1 record with status=='error', error_type=='HTTPStatusError', error_payload contains 'bad', terminated_by=='http_error'.

Notes for the test:
- Use a small helper to count records: yanantin.experiments.capture.load_run on the returned path.
- task_id is a uuid string; we don't pin it, just assert it's consistent within a task and differs across tasks.
- For multi-task tests, set cfg.run_id='r1' so the path is predictable.

Do not write the implementation." < /dev/null`

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/experiments/test_runner.py -v`
Expected: FAIL — `runner` module not found.

- [ ] **Step 3: Write `src/yanantin/experiments/runner.py`**

```python
"""Memory-tool harness runner.

Drives `(model × tool_variant × prompt) → CaptureRecord` over a bounded
agent loop. One CaptureRecord per LLM call; per-task uuid + turn index
tie a trajectory together. Termination reasons are recorded on the last
record of each task so post-hoc analysis can tell the difference between
'the model answered' and 'we ran out of turns'.

No SDK — talks to OpenRouter via the existing OpenRouterClient. Tool
implementations are plain Python callables from the variant registry.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from yanantin.apacheta.clients.openrouter import (
    OpenRouterClient,
    OpenRouterResponse,
)
from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.experiments.budget import BudgetExceeded, CostBudget
from yanantin.experiments.capture import CaptureRecord, CaptureWriter
from yanantin.experiments.prompts import PromptTemplate
from yanantin.experiments.tools.apacheta_tools import (
    QueryBudget,
    QueryBudgetExceeded,
)
from yanantin.experiments.tools.registry import ToolVariant


DEFAULT_SYSTEM_PROMPT = (
    "You are testing memory tools. Use the provided tool to answer the user's "
    "question. When you have the answer, respond with plain text — do not call "
    "the tool again."
)


@dataclass(frozen=True)
class RunnerConfig:
    experiment_id: str
    panel_id: str
    capture_dir: Path
    run_id: str
    cost_ceiling_usd: float
    max_turns: int = 6
    query_budget_per_task: int = 12
    per_call_timeout_s: float = 60.0
    max_tokens: int = 16384
    x_title: str = "yanantin:memtool"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT


def _new_record(
    cfg: RunnerConfig,
    *,
    model: str,
    variant: ToolVariant,
    prompt: PromptTemplate,
    task_id: str,
    turn_idx: int,
    parent_record_id: str | None,
    request_full: dict[str, Any],
    response: OpenRouterResponse | None,
    elapsed_seconds: float,
    status: str,
    error_type: str | None = None,
    error_message: str | None = None,
    error_payload: str | None = None,
    terminated_by: str | None = None,
    tool_error_type: str | None = None,
    tool_error_message: str | None = None,
) -> CaptureRecord:
    if response is not None:
        response_parsed = {
            "content": response.content,
            "tool_calls": response.tool_calls,
            "id": response.id,
            "model": response.model,
        }
        response_raw_body = json.dumps(response.raw)
        usage = response.usage
    else:
        response_parsed = None
        response_raw_body = None
        usage = {}

    extra: dict[str, Any] = {
        "task_id": task_id,
        "turn_idx": turn_idx,
        "parent_record_id": parent_record_id,
    }
    if terminated_by is not None:
        extra["terminated_by"] = terminated_by
    if tool_error_type is not None:
        extra["tool_error_type"] = tool_error_type
        extra["tool_error_message"] = tool_error_message

    return CaptureRecord(
        record_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        experiment_id=cfg.experiment_id,
        panel_id=cfg.panel_id,
        tool_variant_id=variant.variant_id,
        model_id=model,
        prompt_template_id=prompt.content_hash,
        prompt_full=prompt.text,
        request_full=request_full,
        response_parsed=response_parsed,
        response_raw_body=response_raw_body,
        usage=usage,
        elapsed_seconds=elapsed_seconds,
        status=status,
        error_type=error_type,
        error_message=error_message,
        error_payload=error_payload,
        **extra,
    )


async def _run_task(
    cfg: RunnerConfig,
    client: OpenRouterClient,
    apacheta: ApachetaInterface,
    writer: CaptureWriter,
    budget: CostBudget,
    *,
    model: str,
    variant: ToolVariant,
    prompt: PromptTemplate,
) -> bool:
    """Run one (model, variant, prompt) task. Returns True to continue, False to stop."""
    task_id = str(uuid.uuid4())
    qbudget = QueryBudget(cfg.query_budget_per_task)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": cfg.system_prompt},
        {"role": "user", "content": prompt.text},
    ]

    prev_record_id: str | None = None
    last_record: CaptureRecord | None = None
    for turn_idx in range(cfg.max_turns):
        if not budget.ok():
            return False

        request_full = {
            "model": model,
            "messages": list(messages),
            "tools": [variant.schema],
            "tool_choice": "auto",
            "max_tokens": cfg.max_tokens,
            "temperature": 0.7,
        }

        t0 = time.monotonic()
        try:
            response = await client.complete(
                model=model,
                messages=messages,
                tools=[variant.schema],
                tool_choice="auto",
                max_tokens=cfg.max_tokens,
                metadata={"X-Title": f"{cfg.x_title}:{cfg.experiment_id}"},
            )
            elapsed = time.monotonic() - t0
        except httpx.HTTPStatusError as e:
            elapsed = time.monotonic() - t0
            record = _new_record(
                cfg,
                model=model,
                variant=variant,
                prompt=prompt,
                task_id=task_id,
                turn_idx=turn_idx,
                parent_record_id=prev_record_id,
                request_full=request_full,
                response=None,
                elapsed_seconds=elapsed,
                status="error",
                error_type="HTTPStatusError",
                error_message=str(e),
                error_payload=e.response.text if e.response is not None else None,
                terminated_by="http_error",
            )
            writer.write(record)
            return True
        except httpx.RequestError as e:
            elapsed = time.monotonic() - t0
            record = _new_record(
                cfg,
                model=model,
                variant=variant,
                prompt=prompt,
                task_id=task_id,
                turn_idx=turn_idx,
                parent_record_id=prev_record_id,
                request_full=request_full,
                response=None,
                elapsed_seconds=elapsed,
                status="error",
                error_type="RequestError",
                error_message=str(e),
                error_payload=repr(e),
                terminated_by="http_error",
            )
            writer.write(record)
            return True

        tool_calls = response.tool_calls
        if not tool_calls:
            record = _new_record(
                cfg,
                model=model,
                variant=variant,
                prompt=prompt,
                task_id=task_id,
                turn_idx=turn_idx,
                parent_record_id=prev_record_id,
                request_full=request_full,
                response=response,
                elapsed_seconds=elapsed,
                status="ok",
                terminated_by="final_content",
            )
            writer.write(record)
            try:
                budget.add(float(response.usage.get("cost", 0.0)))
            except BudgetExceeded:
                return False
            return True

        try:
            tool_call = tool_calls[0]
            args = json.loads(tool_call["function"].get("arguments") or "{}")
            tool_result = variant.impl(apacheta, args, qbudget)
            tool_error_type: str | None = None
            tool_error_message: str | None = None
        except QueryBudgetExceeded as e:
            tool_error_type = "QueryBudgetExceeded"
            tool_error_message = str(e)
            tool_result = None
        except Exception as e:  # noqa: BLE001 — tool errors captured, not raised
            tool_error_type = type(e).__name__
            tool_error_message = str(e)
            tool_result = None

        if tool_result is None:
            record = _new_record(
                cfg,
                model=model,
                variant=variant,
                prompt=prompt,
                task_id=task_id,
                turn_idx=turn_idx,
                parent_record_id=prev_record_id,
                request_full=request_full,
                response=response,
                elapsed_seconds=elapsed,
                status="ok",
                terminated_by="tool_error",
                tool_error_type=tool_error_type,
                tool_error_message=tool_error_message,
            )
            writer.write(record)
            try:
                budget.add(float(response.usage.get("cost", 0.0)))
            except BudgetExceeded:
                return False
            return True

        record = _new_record(
            cfg,
            model=model,
            variant=variant,
            prompt=prompt,
            task_id=task_id,
            turn_idx=turn_idx,
            parent_record_id=prev_record_id,
            request_full=request_full,
            response=response,
            elapsed_seconds=elapsed,
            status="ok",
            terminated_by=None,
        )
        writer.write(record)
        prev_record_id = record.record_id
        last_record = record
        try:
            budget.add(float(response.usage.get("cost", 0.0)))
        except BudgetExceeded:
            return False

        messages.append(
            {
                "role": "assistant",
                "content": response.content or None,
                "tool_calls": tool_calls,
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.get("id", ""),
                "content": json.dumps(tool_result),
            }
        )

    # Hit max_turns. We need to mark the LAST record's terminated_by — but
    # records are immutable (frozen). Solution: write a synthetic terminal
    # record carrying terminated_by='max_turns'. We use the same pattern as
    # other terminals: it has no response (response=None), status='ok',
    # turn_idx == cfg.max_turns (one past the last real turn), and points at
    # the last real turn as its parent.
    record = _new_record(
        cfg,
        model=model,
        variant=variant,
        prompt=prompt,
        task_id=task_id,
        turn_idx=cfg.max_turns,
        parent_record_id=prev_record_id,
        request_full={},
        response=None,
        elapsed_seconds=0.0,
        status="ok",
        terminated_by="max_turns",
    )
    writer.write(record)
    return True


async def run_experiment(
    cfg: RunnerConfig,
    apacheta: ApachetaInterface,
    client: OpenRouterClient,
    panel_models: list[str],
    variants: list[ToolVariant],
    prompts: list[PromptTemplate],
) -> Path:
    """Drive the cartesian product. Returns the JSONL path written."""
    out_path = cfg.capture_dir / f"{cfg.run_id}.jsonl"
    budget = CostBudget(cfg.cost_ceiling_usd)
    with CaptureWriter(out_path) as writer:
        for model in panel_models:
            for variant in variants:
                for prompt in prompts:
                    if not budget.ok():
                        return out_path
                    keep_going = await _run_task(
                        cfg,
                        client,
                        apacheta,
                        writer,
                        budget,
                        model=model,
                        variant=variant,
                        prompt=prompt,
                    )
                    if not keep_going:
                        return out_path
    return out_path
```

> **Note on the `max_turns` test:** Codex's spec asserts "3 records, last has terminated_by=='max_turns'". The implementation writes a fourth synthetic record (turn_idx == max_turns) to carry the terminated_by marker, because records are frozen. If Codex's test fails for this reason, update the test instead of the implementation — the frozen-record contract is load-bearing and the synthetic terminal record is cleaner than mutating. The Codex spec for this test already accepts that ambiguity ("turn_idx 0,1,2; last record's terminated_by"); the implementing agent should rerun Codex with: "the test should expect cfg.max_turns + 1 records: max_turns real turns plus one synthetic terminal record carrying terminated_by='max_turns', and assert the terminal record's turn_idx == cfg.max_turns".

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/experiments/test_runner.py -v`
Expected: all passed (5-6 tests). If `test_max_turns` fails per the note above, rerun Codex with the updated spec and re-run.

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/experiments/runner.py tests/experiments/test_runner.py
git commit -m "feat(experiments): runner with bounded agent loop and termination markers"
```

---

## Task 8: Name-effect prompt corpus

**Files:**
- Create: `experiments/memory_tools/prompts/find_a_record.yaml`
- Create: `experiments/memory_tools/prompts/find_by_lineage.yaml`
- Create: `experiments/memory_tools/prompts/find_by_author.yaml`

Three prompts that all exercise the same tool surface but lean on different filter axes. Identical across variants — the name-effect comparison holds the prompt constant while only changing which function name is exposed to the model.

- [ ] **Step 1: Create the three prompt files**

`experiments/memory_tools/prompts/find_a_record.yaml`:

```yaml
template_id: find_a_record
description: >
  Open prompt — the model picks a filter. Tests whether the tool is
  understood at all without a hint about which parameter to use.
text: |
  There is an associative memory store containing records. Each record has
  an author_instance_id, a list of lineage_tags, and arbitrary other
  fields. Use the available tool to find any record from author_instance_id
  "scout-7", and tell me what lineage_tags it carries. If you cannot find
  one, say "not found".
```

`experiments/memory_tools/prompts/find_by_lineage.yaml`:

```yaml
template_id: find_by_lineage
description: >
  Constrained prompt — the model is told which filter to use. Tests whether
  the tool call succeeds when the hint is unambiguous.
text: |
  Find records carrying the lineage_tag "iteration_v1" in the associative
  memory store. List the author_instance_id of the first three you find,
  one per line. If there are fewer than three, list however many exist.
```

`experiments/memory_tools/prompts/find_by_author.yaml`:

```yaml
template_id: find_by_author
description: >
  Constrained prompt with a multi-step task — find by author, then report a
  property of the result. Tests whether the model can chain a tool call
  with reasoning over its result.
text: |
  Find any record produced by author_instance_id "scout-7" in the
  associative memory store. Report the number of lineage_tags it carries,
  and the lineage_tags themselves. If you find no such record, say
  "no record found".
```

- [ ] **Step 2: Sanity test — Codex adds a corpus test**

Run: `codex exec --full-auto -m gpt-5-codex "Add to tests/experiments/test_prompts.py: test_name_effect_corpus_loads(): for filename in ['find_a_record.yaml','find_by_lineage.yaml','find_by_author.yaml']: t = load_template(pathlib.Path('experiments/memory_tools/prompts') / filename); assert t.template_id and t.text and len(t.text) > 20 and t.content_hash and len(t.content_hash)==12. Then assert the three content_hashes are all distinct (sanity check the corpus isn't accidentally duplicated)." < /dev/null`

- [ ] **Step 3: Run the corpus test**

Run: `uv run pytest tests/experiments/test_prompts.py -v -k name_effect_corpus`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add experiments/memory_tools/prompts/find_a_record.yaml experiments/memory_tools/prompts/find_by_lineage.yaml experiments/memory_tools/prompts/find_by_author.yaml tests/experiments/test_prompts.py
git commit -m "feat(experiments): name-effect prompt corpus (3 prompts)"
```

---

## Task 9: Pre-register the name-effect experiment

**Files:**
- Create: `experiments/memory_tools/name_effect_v1/preregistration.yaml`

This commits the experimental design before any data is collected — what we're testing, against which panel, with which prompts, what budget. The OTS post-commit hook stamps the commit so the design's timestamp is verifiable.

- [ ] **Step 1: Create `experiments/memory_tools/name_effect_v1/preregistration.yaml`**

```yaml
experiment_id: name_effect_v1
panel_id: iteration_v1
rationale: |
  Test whether the *name* of an associative-memory tool measurably affects
  call-success rate and task-completion rate, holding description,
  parameter schema, and implementation constant. Three variants:
  find_objects (verb-object, prior-correcting), search (bare verb, REST
  prior), query (bare verb, database prior). Identical descriptions,
  identical signatures, identical Python implementation — only the
  function name advertised in the tool schema differs.
hypothesis: |
  H1: Call-success rate (model emits a syntactically valid tool_call
  matching the parameters schema) differs measurably across variants.
  H2: Task-completion rate (the model reports the correct answer within
  max_turns turns) differs measurably across variants.
  Null: descriptions are doing all the work; name is observably noise.
variants:
  - find_objects_v1
  - search_v1
  - query_v1
prompts:
  - find_a_record       # open: model picks the filter
  - find_by_lineage     # constrained: lineage_tag is named in the prompt
  - find_by_author      # constrained: author_instance_id is named
budgets:
  cost_ceiling_usd: 0.50
  max_turns_per_task: 6
  query_budget_per_task: 12
  per_call_timeout_s: 60
  max_tokens: 16384
sandbox:
  apacheta_tier: test
  read_only: true
analyses:
  - per_variant_call_success: fraction of tasks whose first turn carries a
    valid tool_call against the schema
  - per_variant_task_completion: fraction of tasks ending in
    terminated_by=='final_content' (vs max_turns / tool_error / http_error)
  - per_model_cross_variant_consistency: do small vs mid vs large-open vs
    frontier-cheap converge or diverge?
  - workaround_patterns: tasks where the model called the tool with
    matching=={} or with all three filter keys set (and triggered
    ignored_filters)
notes: |
  The runner writes one CaptureRecord per LLM call. Multi-turn trajectories
  share a task_id and are linked by parent_record_id; the last record per
  task carries a terminated_by reason. panel_id resolution + OTS proof is
  committed in iteration_v1.resolved.yaml; this experiment runs against
  whichever models that resolution names.
```

- [ ] **Step 2: Resolve the panel against the live catalog and stage the manifests**

Run: `uv run python -m yanantin.experiments.preregister --exp name_effect_v1`
Expected output: a `panel_resolved` line written to `experiments/memory_tools/name_effect_v1/preregistration.yaml`, and `experiments/memory_tools/panels/iteration_v1.resolved.yaml` created.

> **Expected first-run friction:** if any candidate id in `iteration_v1.criteria.yaml` has rotated out of OpenRouter's catalog, the resolution fails with the offending id. That is the system working as designed — fix the criteria file (correct the slug) in a separate commit *first*, then re-run this step. Each correction is its own commit with rationale, per the foundation plan's spec.

- [ ] **Step 3: Stage and commit via the wrapper**

Run: `scripts/register-experiment name_effect_v1`
Expected: a commit landing with title "Pre-register experiment: name_effect_v1 at <timestamp>", plus (asynchronously) an OTS proof appearing in `docs/ots/`. Confirm both:

```bash
git log --oneline -1                 # commit landed
ls docs/ots/$(git rev-parse --short=10 HEAD).ots 2>/dev/null && echo "OTS proof present"
```

(The OTS hook runs in background; if the proof isn't immediately visible, give it 30s and re-check.)

---

## Task 10: Name-effect smoke run — one model per tier

**Files:**
- Test: `tests/experiments/test_name_effect_smoke.py` (Codex authors)

The full iteration sweep is operator-driven and shouldn't be a pytest test (~1080 calls, single-digit cents, three minutes). This task is the **smoke check**: one model from each spread axis, all three variants, all three prompts. If this passes the harness is ready for the full sweep; the operator runs that as a one-liner.

The smoke seeds `apacheta_test` with a small set of open records (scout-7 author, iteration_v1 lineage_tag) so the prompts have something findable. Records are stored in a per-test collection by using a fresh test backend; if `apacheta_test` already has scout-7 records from prior runs, the seeding skips them (idempotent).

- [ ] **Step 1: Have Codex write the integration test**

Run: `codex exec --full-auto -m gpt-5-codex "Create tests/experiments/test_name_effect_smoke.py. One test, test_name_effect_smoke(tmp_path), marked @pytest.mark.integration; pytest.skip unless 'OPENROUTER_API_KEY' in os.environ AND a config file exists at '~/.yanantin/config/db.ini' (use pathlib.Path.expanduser then exists()). The test:

1. Connect: from yanantin.apacheta import connect; apacheta = connect(tier='test').
2. Seed (idempotent): build three records (FakeRecord-style: from yanantin.apacheta.models.base import ApachetaBaseModel; define a SmokeRecord(ApachetaBaseModel) with model_config ConfigDict(extra='allow')). Three records: r1 = SmokeRecord(provenance={'author_instance_id':'scout-7'}, lineage_tags=['iteration_v1','smoke'], note='alpha'); r2 = SmokeRecord(provenance={'author_instance_id':'scout-7'}, lineage_tags=['iteration_v1'], note='beta'); r3 = SmokeRecord(provenance={'author_instance_id':'scout-9'}, lineage_tags=['iteration_v1'], note='gamma'). Check first whether scout-7 records already exist: existing = apacheta.query_open_by_author_instance('scout-7', limit=10); if len(existing) < 2: store r1 then r2 (use uuid4 for record_id, apacheta.store_record(record_id, record)); also store r3 if no scout-9 yet. This makes the seeding idempotent against repeated smoke runs.
3. Load: variants = build_name_effect_variants() (from yanantin.experiments.tools.registry); prompts = [load_template(pathlib.Path('experiments/memory_tools/prompts')/f) for f in ['find_a_record.yaml','find_by_lineage.yaml','find_by_author.yaml']].
4. Pick one model per spread axis from the iteration_v1 resolved panel. Read experiments/memory_tools/panels/iteration_v1.resolved.yaml (yaml.safe_load); group its 'models' list by size_tier; pick the first model in each of ['tiny','small','mid','large-open'] tiers that exists. If a tier is missing, skip it (don't fail). The result is a panel_models list of 1-4 model ids.
5. Build a RunnerConfig with experiment_id='name_effect_v1_smoke', panel_id='iteration_v1', capture_dir=tmp_path, run_id='smoke', cost_ceiling_usd=0.20, max_turns=4, query_budget_per_task=6, max_tokens=4096, x_title='yanantin:memtool:smoke'.
6. Run: async with OpenRouterClient() as client: out = asyncio.run(run_experiment(cfg, apacheta, client, panel_models, variants, prompts))  — actually since the test is sync, do this via asyncio.run on a small async wrapper:
   async def _go():
       async with OpenRouterClient() as client:
           return await run_experiment(cfg, apacheta, client, panel_models, variants, prompts)
   out_path = asyncio.run(_go())
7. Load and assert. records = load_run(out_path). Assert len(records) > 0. Assert every record's experiment_id == 'name_effect_v1_smoke', panel_id == 'iteration_v1', tool_variant_id in {'find_objects_v1','search_v1','query_v1'}, model_id in panel_models, status in {'ok','error'}. Group records by extra['task_id']: assert each task has at least 1 record. For each model × variant × prompt triple expected (|models| × 3 × 3), assert there exists at least one record with that combination (model_id, tool_variant_id, prompt_template_id where prompt_template_id is the content_hash of the prompt's text — compute on the fly: from yanantin.experiments.prompts import compute_template_id; for p in prompts: expected_hashes.add(compute_template_id(p.text))).
8. Print a one-line per-variant summary: for v in ['find_objects_v1','search_v1','query_v1']: completed = [r for r in records if r.tool_variant_id==v and r.model_dump().get('terminated_by')=='final_content']; print(f'{v}: {len(completed)} final-content terminations'). Use pytest -s to surface it.

Use asyncio.run inside the test. The test is sync — only the run_experiment call awaits.
Do not write any implementation." < /dev/null`

- [ ] **Step 2: Run the smoke test**

Run (no key / no db.ini): `uv run pytest tests/experiments/test_name_effect_smoke.py -v` → 1 skipped.
Run (full env): `uv run pytest tests/experiments/test_name_effect_smoke.py -v -s -m integration` → 1 passed; eyeball the per-variant summary printed.

- [ ] **Step 3: Run the full experiments test suite**

Run: `uv run pytest tests/experiments/ -v -m "not integration"`
Expected: all pass.

Run: `uv run pytest tests/ -q`
Expected: nothing else broke.

- [ ] **Step 4: Commit**

```bash
git add tests/experiments/test_name_effect_smoke.py
git commit -m "test(experiments): name-effect smoke run — one model per tier"
```

---

## Task 11: Operator runbook — full iteration sweep

**Files:**
- (No code changes. Tony or the implementing agent runs this once they're satisfied with the smoke results.)

This is documentation embedded in the plan because the runbook is short and bare-shell — it doesn't deserve its own doc until it's been run successfully.

- [ ] **Step 1: Run the full sweep**

```bash
# All ~15 panel models × 3 variants × 3 prompts. Budget 0.50 USD.
uv run python -c "
import asyncio, yaml, pathlib
from yanantin.apacheta import connect
from yanantin.apacheta.clients.openrouter import OpenRouterClient
from yanantin.experiments.prompts import load_template
from yanantin.experiments.runner import RunnerConfig, run_experiment
from yanantin.experiments.tools.registry import build_name_effect_variants

resolved = yaml.safe_load(pathlib.Path('experiments/memory_tools/panels/iteration_v1.resolved.yaml').read_text())
panel_models = [m['id'] for m in resolved['models']]
variants = build_name_effect_variants()
prompts = [load_template(pathlib.Path('experiments/memory_tools/prompts')/f) for f in
           ['find_a_record.yaml','find_by_lineage.yaml','find_by_author.yaml']]
cfg = RunnerConfig(
    experiment_id='name_effect_v1',
    panel_id='iteration_v1',
    capture_dir=pathlib.Path('experiments/memory_tools/name_effect_v1'),
    run_id='run_001',
    cost_ceiling_usd=0.50,
    max_turns=6,
    query_budget_per_task=12,
    max_tokens=16384,
    x_title='yanantin:memtool:iter_v1:name_effect',
)
apacheta = connect(tier='test')

async def _go():
    async with OpenRouterClient() as client:
        return await run_experiment(cfg, apacheta, client, panel_models, variants, prompts)

out = asyncio.run(_go())
print(f'wrote {out}')
"
```

- [ ] **Step 2: Sanity-check the run**

```bash
RUN_FILE=experiments/memory_tools/name_effect_v1/run_001.jsonl
wc -l "$RUN_FILE"                                                    # expect: ~|models|*3*3*<avg turns> records
jq -r '.tool_variant_id' "$RUN_FILE" | sort | uniq -c                # variant balance
jq -r 'select(."terminated_by"!=null) | ."terminated_by"' "$RUN_FILE" | sort | uniq -c   # outcomes
jq -r 'select(.status=="error") | .error_type' "$RUN_FILE" | sort | uniq -c              # error mix
```

If anything looks wrong, the activity stream has everything needed to debug — `prompt_full`, `request_full`, `response_raw_body`, full error payloads. No re-running required.

- [ ] **Step 3: Commit the run file**

```bash
git add experiments/memory_tools/name_effect_v1/run_001.jsonl
git commit -m "data(experiments): name_effect_v1 run_001 — ~$N captures across N_M models"
```

(The OTS post-commit hook timestamps the data the moment it's collected. The pre-registration commit and the data commit together form the chain that makes "we didn't change the design after seeing the data" verifiable.)

---

## Done When

- `uv run pytest tests/experiments/ -m "not integration"` is green (foundation tests + 6-7 new test files from this plan).
- `uv run pytest tests/experiments/test_name_effect_smoke.py -m integration` passes with `OPENROUTER_API_KEY` and a configured `apacheta_test`.
- `scripts/register-experiment name_effect_v1` has committed the pre-registration and an OTS proof is in `docs/ots/`.
- A `run_001.jsonl` exists in `experiments/memory_tools/name_effect_v1/` with at least 30 records.

## Next Plan

`docs/plans/<date>-memory-tool-harness-analysis-and-iteration.md` (to be written, after first run produces signal):
- Per-variant analysis script reading the run jsonl: call-success rates with confidence intervals, task-completion rates, workaround-pattern counts.
- Second tool variants based on observed failure modes (the brainstorm's principles 4-5: distinguishability, response envelope discipline).
- Add the remaining five tools (`get_object`, `sample_objects`, `have_i_called`, `have_i_requested`, `request_capability`) — only the ones the second iteration's prompts call for.
- In-fill panel registration once tool design has earned conviction on iteration_v1.

---

## Self-Review

**Spec coverage:**

- Runner: cartesian product (Task 7) ✓; reads panel manifest + prompts + variants (Task 9 wires the runbook, Task 7 takes them as args) ✓; per-call timeout (RunnerConfig.per_call_timeout_s — *gap noted: the field exists in cfg but isn't applied; httpx.AsyncClient timeout is set globally on the client at construction. The runbook passes the default 120s. Adequate for first run; explicit per-call timeout in the runner is a refinement once timeouts are observed. Not blocking.*) ; per-run cost budget (Task 3 + Task 7) ✓; concurrent request cap (not implemented — Task 7's loop is sequential. *Gap: spec calls for default 10. For the smoke + first sweep this is fine — ~135 sequential calls at ~1s each is ~2 minutes total. Add concurrency in the next plan if the iteration sweep length becomes a problem.*) ; reuse OpenRouterClient with experiment-specific X-Title (Task 7 sets `X-Title: yanantin:memtool:<exp_id>`) ✓.
- Tool surface: `find_objects(matching, limit, cursor) -> {results, total_matched, next_cursor, diversity}` (Task 5 — adds `cost_hint`, `ignored_filters`, `received_cursor` from the brainstorm/spec response-envelope-discipline section) ✓; transport-agnostic Python functions (Task 5) ✓; response envelope with fixed schema + variable content slots (Task 5's envelope is fixed shape, fields null when N/A) ✓; the other five tools deferred to the next plan (out-of-scope section) ✓.
- Sandbox: apacheta_test (Tasks 9, 10, 11 all use tier='test') ✓; read-only (Task 5 calls only query/list methods, never store_*) ✓; per-run query budget (Task 5's QueryBudget) ✓ — note this is per-task, not per-run; per-run is the cost budget. Spec is ambiguous between the two; per-task query budget plus per-run cost budget covers the spirit (runaway model ⇒ per-task halt; runaway experiment ⇒ per-run halt).
- Pre-registration: variant + prompt + budget references in preregistration.yaml (Task 9) ✓; OTS proof on commit (Task 9 step 3) ✓.
- First experiment (name effect): 3 variants with identical params (Tasks 4, 6) ✓; identical prompts across variants (Task 8 — corpus shared by all variants in the runbook) ✓; outcome measures captured in the schema (call-success = first-turn tool_call presence; task-completion = `terminated_by=='final_content'`; workaround patterns = `ignored_filters` and `matching=={}`; cross-model consistency = standard analysis on per-variant rates grouped by `model_id`) ✓ — all derivable from the captured records without re-runs.

**Placeholder scan:** No "TBD"/"add error handling later"/"similar to". Every code step shows complete code. The two flagged spec gaps (per-call timeout, concurrency cap) are explicitly called out with their tradeoff and where they're deferred to.

**Type consistency:**
- `OpenRouterResponse.tool_calls: list[dict] | None` — Task 1 defines, Task 7 reads.
- `PromptTemplate.text` / `.content_hash` / `.template_id` — Task 2 defines, Tasks 7-10 read.
- `CostBudget.add()` raising `BudgetExceeded` — Task 3 defines, Task 7 catches.
- `QueryBudget.charge()` raising `QueryBudgetExceeded` — Task 5 defines, Task 7 catches.
- `find_objects_schema(name)` signature — Task 4 defines, Task 6 calls with three names.
- `find_objects_impl(apacheta, args, budget) -> dict` — Task 5 defines, Task 6 wires, Task 7 invokes.
- `ToolVariant(variant_id, function_name, schema, impl)` — Task 6 defines, Task 7 destructures `variant.variant_id`, `variant.schema`, `variant.impl`.
- `RunnerConfig.experiment_id` / `panel_id` / `capture_dir` / `run_id` / `cost_ceiling_usd` / `max_turns` / `query_budget_per_task` / `max_tokens` / `x_title` — Task 7 defines, Task 10 + 11 construct.
- `run_experiment(cfg, apacheta, client, panel_models, variants, prompts) -> Path` — Task 7 defines, Tasks 10-11 invoke.
- Extra fields on `CaptureRecord` via `extra="allow"`: `task_id`, `turn_idx`, `parent_record_id`, `terminated_by`, `tool_error_type`, `tool_error_message` — Task 7 writes them, Task 10's assertions read them.

No drift found.
