# Memory-Tool Experimental Harness

*Design spec for the experimental infrastructure that lets us design, test, and
iterate LLM-facing tools against yanantin's associative memory store. The tools
under test are themselves the experiment; the activity stream is the data.*

*2026-05-11. Builds on `docs/brainstorm-llm-tool-surface.md` (2026-05-10) and
`experiments/structured_input_results.jsonl` (2026-03-08 cross-model sweep).*

## Problem

Yanantin's apacheta interface (`src/yanantin/apacheta/interface/abstract.py`)
is a rich, schema-open, immutable record store. No LLM-facing tool surface
exists for it. The brainstorm laid out the principles and a worked example
(`find_objects`, `get_object`, `sample_objects` + `have_i_called`,
`have_i_requested`, `request_capability`) but explicitly punted on transport,
activity-stream backend, and implementation.

The goal of this spec is the *experimental infrastructure* that makes tool
design empirical rather than argued. Tools are designed, tested across a model
panel, observed via a complete activity stream, and refined based on observed
behavior. The harness exists so the brainstorm's claim — *"we don't have to
get tool design right the first time; we have to get observability right so
the design can converge on right"* — can actually be executed.

## Substrate

The design rationale rests on a distinction sharpened in the design
conversation: the model's working state is either a **self-curated tensor**
(taste_open, Hamut'ay) or an **append-only log with garbage collection**
(Claude Code). The two substrates have different cost profiles, different
retirement signals, and require different tool affordances.

The memory tools' load-bearing claim is that **the model can only safely let
things go if retrieval is trustworthy.** Without `find_objects`/`get_object`,
the model hoards because forgetting is permanent loss. With them, forgetting
becomes paging-out — recoverable. The experiment tests whether the tools earn
enough trust that models actually trim their working state.

## Architecture

Three components. Each owns one responsibility; together they form the harness.

```
+-------------------+   +-------------------+   +---------------------+
|   Capture Layer   |   |      Runner       |   |  Tool Surface       |
|   (apacheta-open) |<--|  (model panel ×   |<--|  (under test)       |
|   no-truncation   |   |   tool variants × |   |  find_objects, etc. |
|   schema-open     |   |   prompt corpus)  |   |  transport-agnostic |
+-------------------+   +-------------------+   +---------------------+
        ^                       ^                        ^
        |                       |                        |
        | every record          | reads panel manifest,  | concrete Python
        | typed via panel_id,   | prompt template,       | functions; not
        | experiment_id,        | tool variant ID from   | yet bound to MCP
        | tool_variant_id       | pre-registered spec    | or function-call
```

The three components are built in this order: capture layer first (the data is
the output, so this must be correct before the first call), runner second
(shaped by what the first experiment needs), tool surface third (the smallest
thing that produces real data).

### Capture Layer

The activity record store. Schema-open. Records every tool call's full
request, full response, all metadata, no truncation.

**Storage.** JSONL files, one per experimental run, written to
`experiments/memory_tools/<experiment_id>/<run_id>.jsonl`. JSONL is the
cheapest correct answer: append-only, schema-open, queryable with `jq` or
loaded into DuckDB/pandas later. Promote to a queryable backend (ArangoDB
collection, DuckDB warehouse) only when cross-run query at scale starts
hurting — premature.

**Schema (open via apacheta's `extra="allow"` pattern).** Each record carries:

| Field | Source | Purpose |
|-------|--------|---------|
| `record_id` | UUID4 generated at write | Unique key |
| `timestamp` | UTC ISO-8601 with microseconds | Ordering, cost-window analysis |
| `experiment_id` | From pre-registration commit | Join data to its experiment |
| `panel_id` | Pre-registered panel reference (e.g. `"iteration_v1"`) | Distinguish design data from validation data |
| `tool_variant_id` | Variant under test (e.g. `"find_objects_v1"`) | Compare variants on the same task |
| `model_id` | OpenRouter slug | Cross-model analysis |
| `prompt_template_id` | Reference to the template file by content hash | Reproducibility even if filename changes |
| `prompt_full` | Rendered prompt sent to model | Reproducibility, debugging |
| `request_full` | Full HTTP request body sent to OpenRouter | Includes tool definitions, max_tokens, sampling params |
| `response_parsed` | Parsed response (message content, tool calls, finish_reason) | Primary analysis input |
| `response_raw_body` | Raw HTTP response body | Captures malformed responses and discrepancies between parsed and raw |
| `usage` | Token counts, cost from OpenRouter | Cost analysis |
| `elapsed_seconds` | End-to-end wall time | Latency analysis |
| `status` | `"ok"` / `"error"` | Quick filter |
| `error_type`, `error_message`, `error_payload` | When status is error | Failure analysis without re-running |

Any field not in this list can still appear via `extra="allow"` — collectors
attach what they want, downstream analysis adapts.

**No-truncation contract.** Storage is not our concern; signal is. Specific
discipline this imposes:

- `max_tokens` default 16384, with per-model native cap discovered at panel
  registration time and recorded in the panel manifest. The 2026-03-08
  structured-input sweep's `max_tokens=1500` is the failure mode we're
  designing against.
- `response_raw_body` is stored even when parsing succeeds; the parsing path
  is itself a possible source of confound.
- Error responses captured with full payload, not just the status code.
- HTTP-layer logs separate from parsed-response logs so we can tell "the model
  said X but our parser saw Y."
- Cost metadata captured on errors too — knowing what failed runs cost matters.
- No log rotation by size during a run; rotate only between runs.
- Re-running a model already in the panel produces a *new* record (versioned
  by `record_id`), never deduped. Multiple draws on the same prompt is its own
  signal (response variance).

### Runner

Iterates the cartesian product `(model × tool_variant × prompt) → capture`,
respecting budgets and writing records as they complete.

**Panel manifest — selection criteria, not hardcoded IDs.** Hardcoding model
IDs in a spec guarantees they rot; model generations turn over in roughly two
months. The panel is defined as *families + size tiers + cost tiers + count*,
and resolved against the **live OpenRouter `/models` catalog at
pre-registration time** by the `preregister --stage` step. The resolved exact
model IDs (with prompt/completion cost, context length, and a
`resolved_at` timestamp) are written into the committed `preregistration.yaml`,
and the OTS post-commit hook stamps that commit. That stamp is the verifiable
answer to "were these models current when the experiment ran?" — the proof
predates the first record in the activity stream.

`yanantin.chasqui.model_selector.load_from_openrouter_response` already
consumes the `/models` catalog for scout selection; the preregister step
reuses it.

```yaml
# experiments/memory_tools/panels/iteration_v1.criteria.yaml — the input
panel_id: iteration_v1
count: 12-15
rationale: |
  Diverse on family × size × generation × cost, current-gen as of
  pre-registration, defended on first principles before tool design starts.
require:
  context_length_min: 8000
  generation: current   # exclude models superseded by a same-family successor
                        # available on the catalog (no Gemma 3 if Gemma 4 is up)
spread:
  families: [llama, gemma, qwen, mistral, phi, glm, deepseek, gpt-oss, granite,
             "anthropic-haiku-tier", "google-flash-lite-tier"]
  size_tiers: [tiny, small, mid, large-open]   # at least one per tier
  cost_tiers: [free, cheap, frontier-cheap]    # at least one per tier
exclude_patterns: ["*-audio-*", "*-vision-only-*"]   # can't take text-tool input

# experiments/memory_tools/panels/iteration_v1.resolved.yaml — written by
# `preregister --stage`, committed, OTS-stamped:
resolved_at: 2026-05-12T15:00:00Z
catalog_snapshot_sha: <sha256 of the /models response body>
models:
  - id: <openrouter-slug>
    family: <family>
    size_tier: small
    cost_tier: cheap
    prompt_cost: 0.00000002
    completion_cost: 0.00000004
    context_length: 32768
    native_max_tokens: 16384   # discovered, recorded
  # ... 11-14 more, resolved from the live catalog
```

The iteration panel (~12-15 models) is the *training set* — we iterate tool
design against it. The in-fill panels (`infill_v1`, etc.) are registered later,
post-design-convergence, as the *cross-validation set* — same resolution
mechanism against a fresh catalog snapshot. The paper's headline "validated
against 200+ models" comes from the union; each panel's `resolved.yaml` +
OTS proof documents exactly which models, current as of when.

**Sketch of what the criteria resolve to as of 2026-05-12** (illustrative
only — the committed `resolved.yaml` is authoritative): tiny —
`llama-3.2-1b-instruct`, `gemma-3n-e4b-it` or a Ministral-3B; small —
`qwen3.5-9b`, `gemma-4-26b-a4b-it`, `phi-4-mini-instruct`, `granite-4.1-8b`,
`nemotron-nano-9b-v2`; mid — `mistral-small-3.2-24b-instruct`,
`gemma-4-31b-it`, `qwen3-32b`, `lfm-2-24b-a2b`, `gpt-oss-20b`; large-open —
`llama-4-scout`, `qwen3-coder-30b-a3b-instruct`, `gpt-oss-120b`; frontier-cheap
— `claude-haiku-4-5`, `gemini-2.5-flash-lite`, `deepseek-v4-flash`. Pick ~12-15
of these spanning the spread axes. All current-gen, all cheap enough that a
full iteration sweep of one tool variant costs well under $1.

**Pre-experiment conformance smoke check.** Before the first real experiment,
re-run the 2026-03-08 structured-input sweep's scoring against the *resolved*
current panel (not the full 345 — just the ~12-15). Confirms each panel model
can produce structured output legibly before we spend iteration budget on it.
If a panel model fails the smoke check, that's recorded and the model is
replaced via the deliberate-enlargement path (new commit, new OTS stamp), not
silently swapped.

**Prompt template store.** Templates live in
`experiments/memory_tools/prompts/` as discrete files. Each capture record
stores both the template ID (content hash) and the *rendered* prompt — so
even if a template file is later edited, old runs remain reproducible from
their own records.

**Per-call budget enforcement.** Configurable cost ceiling per run; runner
halts when exceeded. Per-call timeout (default 60s, configurable). Concurrent
request cap (default 10, matches the 2026-03-08 sweep's `CONCURRENCY=10`).

**OpenRouter client.** Reuse `yanantin.apacheta.clients.openrouter.OpenRouterClient`
(already X-Title-tagged and storing `generation_id` per the
2026-03-28 work). Pass an experiment-specific `X-Title` (e.g.
`yanantin:memtool:iter_v1:exp_name_effect`) so the cost ledger in OpenRouter
reflects experimental work distinctly.

**Sandbox.** Not chroot or container — wrong threat model. The sandbox is:

- Use `apacheta_test` database (already exists, credentials separate from prod
  via `db.ini` tier discipline from 2026-04-15-db-setup-tooling-design.md).
- Experimental records produced by the runner write to an isolated collection
  (`experimental_records`) that production reads never touch.
- Per-run query budget on apacheta calls so a runaway tool can't exfiltrate
  the entire store. Budget recorded in the run's manifest.

### Tool Surface (under test)

Transport-agnostic Python functions. They are the *thing being designed*, not
the harness's stable feature set. From the brainstorm:

```python
def find_objects(
    matching: dict | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict:
    """{results, total_matched, next_cursor, diversity}"""

def get_object(by: dict) -> dict | None: ...

def sample_objects(count: int = 1, near: dict | None = None) -> list: ...

def have_i_called(tool_name: str, with_args: dict | None = None) -> dict: ...

def have_i_requested(description: str | None = None) -> list: ...

def request_capability(description: str) -> None: ...
```

These are bound into the runner as the tool definitions presented to each
model. The runner emits them as OpenRouter function-calling tool schemas;
the implementations call into the apacheta interface for the operating tools
and into the activity stream for the self-knowledge and meta tools.

**Response envelope discipline (cache-friendliness).** Tool responses follow a
*fixed schema with variable content slots*, not bespoke per call. A
`find_objects` response always returns `{results, total_matched, diversity,
cost_hint}` — even when fields are `null`. Selective omission changes the
prefix structure and breaks Anthropic's prompt-cache point earlier. The
brainstorm's "response shape is part of the interface" gets cheaper than naive
token-counting suggests, *if* the envelope is stable.

**Transport choice deferred.** This spec does not commit to MCP vs Python
direct call vs other transport. The functions above are the surface; the
harness binds them as function-calling tool schemas (OpenRouter's standard
mechanism). Wrapping as MCP later is a mechanical step, not an architectural
one, as long as response shape stays transport-agnostic.

## Pre-Registration Discipline

Borrowed from `../governance`'s auto-commit pattern, sharpened by yanantin's
existing OTS post-commit hook.

**Pre-registration artifact.** A single committed file describing the
experiment before any call is made:

```
experiments/memory_tools/<experiment_id>/preregistration.yaml
```

Contains: experiment ID, panel manifest reference, tool variants under test,
prompt template references, success criteria, planned analyses, expected
runtime and cost.

**Auto-commit Make target.** Adapted from governance's `Makefile`:

```makefile
# Pre-register an experiment. EXP is the experiment ID.
# The preregistration.yaml names its panel and prompt template IDs; the
# Make target stages all referenced files together so the commit is
# self-contained.
register-experiment:
	@test -f experiments/memory_tools/$(EXP)/preregistration.yaml || \
	  (echo "missing preregistration.yaml for $(EXP)" && exit 1)
	uv run python -m yanantin.experiments.preregister --exp $(EXP) --stage
	git commit -m "Pre-register experiment: $(EXP) at $$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

The `preregister --stage` step reads `preregistration.yaml`, resolves the
panel and prompt template references it names, and `git add`s exactly those
files. This keeps the staging contract explicit rather than embedded in
brittle Make shell expansion.

The yanantin `.githooks/post-commit` hook then fires automatically, submitting
the commit hash to OpenTimestamps calendar servers and storing the proof in
`docs/ots/`. Result: the experiment's specification is cryptographically
timestamped at UTC second resolution before any data is collected.

**Why this matters.** When the paper claims "the iteration panel was fixed
before tool design started," the OTS proof is the evidence. Reviewer #2's
"how do we know you didn't pick the panel post-hoc?" has a verifiable answer:
the OTS proof on the pre-registration commit predates the first record in
the activity stream. No trust required.

**Discipline this requires.** Adding a model to the panel mid-iteration is
not silent — it requires a new commit with explicit rationale ("evidence the
panel is missing X family; here's why we're enlarging it before round N").
The OTS chain shows both decisions.

## First Experiment: Name Effect

Per the brainstorm (`docs/brainstorm-llm-tool-surface.md:411-422`), the first
specific test isolates the naming claim. Three variants of the same tool:

```python
find_objects(matching, limit, cursor)  # verb-object, prior-correcting
search(matching, limit, cursor)        # bare verb, REST/SQL prior
query(matching, limit, cursor)         # bare verb, database prior
```

Identical signatures. Identical descriptions. Identical task corpus. Same
iteration panel.

**Hypothesis.** Name affects call-success rate and task-completion rate
measurably. If it doesn't, the description is doing all the work and the
brainstorm's name principle needs revision. Either result is publishable.

**Outcome measures (carried in the capture schema):**

- Call-success rate (response matched expected schema, returned non-error)
- Task completion (did the model accomplish the asked task within N calls)
- Workaround patterns (chained multiple tools where one well-designed tool
  would have done it)
- Capability requests (did `request_capability` fire, and on what)
- Cross-model consistency (do small/large/cheap/expensive converge?)

**Cost estimate.** 12 panel models × 3 name variants × ~10 prompts × ~3 calls
per task = ~1080 calls. At median \$0.0001/call across the iteration panel,
under \$0.20. Cheap.

## Out of Scope

- Full MCP wrapping of the tool surface (graduation step; spec'd separately
  once iteration tool design has converged).
- Tool surface choices beyond the brainstorm's three operating + two
  self-knowledge + one meta. Other tools may be added as experiments demand.
- Activity-stream consumer tooling (analyst LLM tools that read aggregated
  records). The analyst tier is the brainstorm's tier 3; this spec only
  covers tiers 1 and 2 (operating + self-knowledge) for the operating model.
- Removal of project-scope limits in `taste_open` (separately tracked as
  prerequisite work; not bundled here).
- Production memory tooling for Claude Code use (the MCP graduation step
  feeds this, but it's not part of the experimental harness).

## Open Questions

Carried forward from the brainstorm, plus new ones surfaced in design:

- **Diversity hint shape.** Flat distribution per field? Clustering summary?
  LLM-generated paragraph? First experiment doesn't depend on this; later
  ones will.
- **Cost signal source.** Per-call cost is available from OpenRouter; how
  do we surface it in tool responses without leaking transport-specific
  detail? Or do we?
- **`request_capability` analyst surface.** How does the analyst LLM read
  aggregated requests? What's the proposal format for new tools? Who
  decides whether to build them?
- **Activity record schema accretion vs. reorganization.** Schema-open buys
  us free extension; at what point does the schema stop accreting and start
  reorganizing? Probably empirical.
- **Substrate-dependent retirement (research finding, 2026-05-11).** Opus in
  Claude Code retires around 250-300k; Opus in taste_open never has. Possible
  research-paper material; out of scope for tool design but tracked in
  `~/.claude/projects/-home-tony-projects-yanantin/memory/context_virtual_memory.md`.

## Implementation Order

1. **Capture layer first.** `experiments/memory_tools/capture.py` with the
   record schema and JSONL writer. Tested in isolation before any model call.
2. **Pre-registration plumbing.** Makefile target, panel manifest schema,
   prompt template store layout. Commit + verify OTS proof on a no-op
   pre-registration.
3. **Runner skeleton.** Reads pre-registered manifest, calls one model with
   one prompt, captures one record. End-to-end smoke test on whichever free
   model the catalog resolution picks for the panel's free tier.
4. **First tool variants.** `find_objects` / `search` / `query` with identical
   signatures, bound to the live apacheta interface (read-only against
   `apacheta_test` with a query budget).
5. **First experiment run.** Pre-register name-effect experiment, run against
   iteration panel, analyze. Iterate on tool design from observed data.
6. **In-fill (later).** When a tool variant has earned conviction on the
   iteration panel, register an in-fill panel and re-run for cross-validation.

The implementation plan (separate doc) will sequence these into discrete
PRs/commits with verification at each step.
