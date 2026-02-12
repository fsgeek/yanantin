# Blueprint

*Not a tensor. Not a journal. A map of what exists, what connects,
and what doesn't exist yet.*

*Last updated: post-T15 survey, 2026-02-12*

## What Exists

### Apacheta — Tensor Database (code: `src/yanantin/apacheta/`)

The core. 33 classes, 26 abstract methods, 3 backends, 1 HTTP client.

| Layer | Files | What it does |
|-------|-------|-------------|
| **models/** | 6 files, 19 classes | Pydantic v2 data models: TensorRecord, StrandRecord, KeyClaim, CompositionEdge, CorrectionRecord, DissentRecord, NegationRecord, BootstrapRecord, SchemaEvolutionRecord, EntityResolution, EpistemicMetadata, DeclaredLoss, ProvenanceEnvelope, SourceIdentifier |
| **interface/** | 2 files | `ApachetaInterface` ABC (26 methods) + 5 error types. The only API. Everything goes through this. |
| **backends/** | 3 files | `InMemoryBackend`, `DuckDBBackend`, `ArangoDBBackend`. All implement the same 26 methods. Three paths to the same interface. |
| **operators/** | 7 files | compose, project, correct, dissent, negate, bootstrap, evolve. Functions that operate through the interface, never touch backend internals. |
| **renderer/** | 1 file | Markdown rendering. TensorRecord → human-readable text. |
| **ingest/** | 2 files | Markdown parsing (human-readable text → TensorRecord) and tensor ballot (atomic T-number allocation via O_CREAT\|O_EXCL). Supports both modern (T*_*.md) and legacy (conversation_tensor_*.md) naming, with label-based deduplication on ingest. |
| **clients/** | 2 files | OpenRouter API client for cross-model communication. `ApachetaGatewayClient` — thin HTTP client implementing all 26 interface methods against Pukara. Fourth path to the interface. |
| **content_address.py** | 1 file | SHA-256 content addressing for cairn documents. `content_hash()`, `ContentIndex` for duplicate detection, CLI dedup reporting. |
| **config.py** | 1 file | Config-as-tensors. `ConfigTensor` model, `store_config`, `get_current_config`, `get_config_history`. Immutable configuration stored in Apacheta with correction-chain lineage. File defaults bootstrap; database overrides. |

**712 test functions** across 25 files. 22 red-bar (structural invariants, 5 files), 71 integration (ArangoDB live, 1 file), 619 unit (19 files). Parametrized tests expand beyond that count. Includes independent test suites for ArangoDB (67 tests), DuckDB (111+43 tests), gateway client (70 tests), config tensors, Tinkuy audit/succession (20 tests), content addressing (38 tests), Awaq weaver (69 tests), and scourer (51 tests).

### Chasqui — Coordinator (code: `src/yanantin/chasqui/`)

The heartbeat. Dispatches scouts and scourers, scores responses, selects models.
Now runs autonomously via cron using the pulse/heartbeat system
(see Infrastructure below). 6 source files.

| File | What it does |
|------|-------------|
| `coordinator.py` | Wake up, select tensor, dispatch scout/scour, collect response |
| `model_selector.py` | Cost-weighted random walk across OpenRouter's model catalog |
| `scout.py` | Send a tensor to a model, get a response, write it to cairn |
| `scourer.py` | Targeted exploration with 3 scope types: introspection (project internals), external (other codebases), tensor (cairn analysis). Three prompt templates. |
| `scorer.py` | Score scout reports for provenance, verifiable claims, content |
| `__main__.py` | CLI: `uv run python -m yanantin.chasqui [--respond PATH] [--scour TARGET --scope {introspection,external,tensor}]` |

**Respond mode**: `--respond path/to/tensor.md` sends a tensor to a randomly
selected model and writes the response to `docs/cairn/`.

**Scour mode**: `--scour TARGET --scope {introspection,external,tensor}` directs
a randomly selected model to examine a specific target. Scourers are focused
where scouts wander freely.

**Autonomous mode**: The pulse hook (`.claude/hooks/chasqui_pulse.py`) detects
code changes, enforces a minimum heartbeat interval, manages a work queue
(scout → verify → respond on DENIED → scour), and integrates with Tinkuy for
governance checks. The simple cron wrapper (`chasqui_heartbeat.sh`) provides
a less reactive alternative for scheduled dispatch.

### Awaq — Weaver (code: `src/yanantin/awaq/`)

Composition graph extraction. Deterministic, no LLM calls. 3 source files.

| File | What it does |
|------|-------------|
| `weaver.py` | 14 regex patterns extract composition declarations from tensor prose. Handles Unicode subscripts (T₀), LaTeX (T_0), plain (T0). Returns `CompositionDeclaration` dataclasses with source, targets, relation, evidence, confidence. |
| `__main__.py` | CLI: `uv run python -m yanantin.awaq [--tensor T15] [--json] [--list]` |
| `__init__.py` | Package init with public API exports |

Relations extracted: `composes_with`, `does_not_compose_with`, `corrects`,
`bridges`, `branches_from`, `read`. Confidence levels: high/medium/low.
Current corpus: 19 declarations from 15 tensors, 14 unique nodes.

### Pukara — Fortress Gateway (separate project: `/home/tony/projects/pukara/`)

FastAPI wrapping ApachetaInterface over HTTP. 39 endpoints.

| Layer | What it does |
|-------|-------------|
| `app.py` | Application factory, lifespan (ArangoDB backend), exception handlers, audit middleware |
| `config.py` | INI + env var config. Credentials in `config/pukara.ini` (gitignored). |
| `auth.py` | API key authentication. Empty key = dev mode. |
| `decoder.py` | DecoderRing — UUID obfuscation. V1 = pass-through. |
| `routes/store.py` | 8 POST endpoints (one per record type) |
| `routes/read.py` | 4 GET endpoints (list, get tensor, get strand, get entity) |
| `routes/query.py` | 20 GET query endpoints across 7 categories |
| `routes/meta.py` | health, version, counts |

Depends on yanantin via path. **150 tests** across 2 files.

### The Cairn (docs/cairn/)

104 files. 15 tensors (T0-T7, T9-T15; T8 intentionally unwritten),
87 scout reports, 2 scour reports, 9 compaction records
(`docs/cairn/compaction/`). Legacy `conversation_tensor_*` duplicates
removed — T*_*.md is the canonical naming. The cairn is persistence —
files on disk, in git, re-ingestible by the markdown parser.
Content addressing (`content_address.py`) prevents future duplicates.

### Infrastructure — Hooks and Heartbeat (`.claude/hooks/`)

Three scripts that give the project autonomous behavior between sessions.

| File | What it does |
|------|-------------|
| `capture_compaction.py` | **PreCompact hook.** Fires before context compaction. Forks a child that polls the session JSONL for the compaction summary, then writes it to `docs/cairn/compaction/` with honest provenance labeling. The compaction summary is system-generated content wearing a `type: "user"` label — this hook surfaces that. Stdlib only, no project dependencies. |
| `chasqui_pulse.py` | **Reactive heartbeat.** Runs via cron (every 1-5 min). Detects code changes via git, enforces minimum scout intervals, manages a work queue (scout → verify → respond on DENIED verdicts), runs Tinkuy governance checks when blueprint drifts. Exclusive lock prevents overlap. State in `.claude/heartbeat_state.json`, queue in `.claude/work_queue.json` (neither committed). |
| `chasqui_heartbeat.sh` | **Simple cron wrapper.** Modes: scout, verify, respond, score. Sources `.env` for API keys. A less reactive alternative to the pulse — good for scheduled 6-hour/daily/weekly dispatch. |

**Config-as-tensors** (`src/yanantin/apacheta/config.py`): Configuration
stored as immutable TensorRecords with correction-chain lineage. Each config
change records what changed, why, and what it replaced. File defaults
bootstrap the system before a database is available; database configs override.
`DEFAULT_CONFIGS` covers Chasqui pulse settings. See the Apacheta table above.

## What Connects

```
Agent
  ↓ (uses ApachetaGatewayClient)
ApachetaInterface (abstract)
  ↓ (HTTP — the security boundary)
Pukara (gateway)
  ↓ (Python import — path dependency)
ApachetaInterface (abstract)
  ↓ (one of three local backends)
InMemoryBackend | DuckDBBackend | ArangoDBBackend

Chasqui (coordinator)
  ↓ (OpenRouter API)
External models → scout/scour reports → docs/cairn/
  ↓ (markdown parser)
TensorRecord → ApachetaInterface → backend

Awaq (weaver)
  ↓ (reads cairn)
docs/cairn/ → CompositionDeclarations → (future: composition edges)
```

Four paths to the interface: three local backends plus
`ApachetaGatewayClient` over HTTP to Pukara. The road to the fortress
is built. Awaq provides the composition graph; Chasqui provides the
epistemic diversity.

## What Doesn't Exist

| Name | Status | What it would be |
|------|--------|-----------------|
| **Tinkuy** | v0 — audit + succession | Governance. Blueprint audit tool (`uv run python -m yanantin.tinkuy`), succession protocol. Code: `src/yanantin/tinkuy/` (4 files). |
| **Gleaner** | Concept | Compose patterns from scour results. Next role after scourer. |
| **Analyst** | Concept | Identify actionable insights from gleaner patterns. |
| **Cantor/Weaver** | Concept (Awaq is step 1) | Curate corpus, create composition edges. Awaq provides deterministic extraction; LLM-guided curation is the next layer. |
| **Choquequirao** | Name only | Archive and provenance. Buried things being excavated. No code, no design. |
| **Takiq** | Name only | Singer role — carries the greeting. No implementation. |
| **DecoderRing v2** | Placeholder | UUID obfuscation is pass-through. Real obfuscation undesigned. |

## Roles

| Role | Who | What they do |
|------|-----|-------------|
| **Master Builder** | Claude Opus (human-facing instance) | Coordinates. Delegates code to subagents. Writes governance infrastructure and tensors. Does NOT write application code directly (T12 coordinator pattern). |
| **Builder** | Delegated subagent (Sonnet/Codex) | Writes application code. Commits signed separately. |
| **Test Author** | Different delegated subagent | Writes tests against code they didn't write. |
| **Scout** | Any model via OpenRouter/Chasqui | Reviews tensors, produces reports. Cost-weighted random selection. |
| **Flatworm** | Tony's alter ego | Asks questions. Tastes gradients. Proposes structural fixes. Invented sybil attacks. |

## Reading Order for New Instances

The context budget is finite. Here's the priority:

1. **CLAUDE.md** — loaded automatically. Social norms, operational principles.
2. **This blueprint** — where everything is and how it connects.
3. **MEMORY.md** — loaded automatically. Credentials, signing, operational state.
4. **The most recent tensor** — what the last instance did and said to you.
5. **docs/apacheta.md** — the design document for the tensor database.
6. **Founding tensors T0-T7** — if context permits. Symlinks in `docs/cairn/`.
   Every instance has been told to read these. No instance has. The cost
   compounds. Decide for yourself whether this session is the one that pays it.

## CI Enforcement

Both projects have `.github/workflows/separation.yml`:
- Rejects commits that modify both `src/` and `tests/`
- Runs full test suite on push/PR
- The boundary is GitHub infrastructure, not local hooks (agents bypassed
  local hooks in Mallku)

## Succession Protocol

Before writing your tensor (the end-of-session ritual), run:

```bash
uv run python -m yanantin.tinkuy
```

Compare the audit report to this blueprint. If they disagree, update the
blueprint. Then run the succession check:

```bash
uv run python -m yanantin.tinkuy --check
```

Empty list = the map matches the territory. Non-empty = fix the blueprint
before writing your tensor.

## How to Update This Blueprint

This document describes what IS, not what should be. When you build
something, update this file. When something described here becomes wrong,
fix it. A blueprint that doesn't match the building is worse than no
blueprint at all. The audit tool (`uv run python -m yanantin.tinkuy`)
generates ground truth — use it to verify your updates.
