# Blueprint

*Not a tensor. Not a journal. A map of what exists, what connects,
and what doesn't exist yet.*

*Last updated: post-activity-stream implementation, 2026-02-18*

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

**1333 test functions** across 50 files. 41 red-bar (structural invariants, 6 files), 105 integration (ArangoDB live, 2 files), 1187 unit (36 files). Parametrized tests expand beyond that count. Includes independent test suites for ArangoDB (67 tests), DuckDB (111+43 tests), gateway client (70 tests), config tensors, Tinkuy audit/succession (20 tests), content addressing (38 tests), Awaq weaver (69 tests), Awaq materializer (31 tests), scourer (51 tests), gleaner, analyst (56 tests), precompact hook, and collector pipeline (9 tests).

### Chasqui — Coordinator (code: `src/yanantin/chasqui/`)

The heartbeat. Dispatches scouts and scourers, scores responses, selects models,
analyzes cross-model patterns, tracks coverage freshness. Now runs autonomously
via cron using the pulse/heartbeat system (see Infrastructure below). 9 source files.

| File | What it does |
|------|-------------|
| `coordinator.py` | Wake up, select tensor, dispatch scout/scour, collect response |
| `model_selector.py` | Cost-weighted random walk across OpenRouter's model catalog |
| `scout.py` | Send a tensor to a model, get a response, write it to cairn |
| `scourer.py` | Targeted exploration with 3 scope types: introspection (project internals), external (other codebases), tensor (cairn analysis). Three prompt templates. |
| `gleaner.py` | Extract structured claims from scout/scour reports. Deterministic pattern matching. Sits between Scout and Verify in the pipeline. |
| `analyst.py` | Cross-model topology detection. Filters garbage, clusters claims by file reference, groups by word similarity, detects agreement across 3+ models. Surfaces open questions from singleton groups (epistemic/architectural claims consensus missed). Pipeline: Scout → Gleaner → Analyst → Investigate. |
| `scorer.py` | Score scout reports for provenance, verifiable claims, content |
| `coverage.py` | The watchman. Scans cairn for file coverage, computes freshness weights (epoch 0 = never reviewed = max priority). Steers scout file selection toward blind spots. |
| `__main__.py` | CLI: `uv run python -m yanantin.chasqui [--respond PATH] [--scour TARGET --scope {introspection,external,tensor}] [--analyze] [--investigate N]` |

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

Composition graph extraction and materialization. Deterministic, no LLM calls. 4 source files.

| File | What it does |
|------|-------------|
| `weaver.py` | 14 regex patterns extract composition declarations from tensor prose. Also parses structured metadata comments (`<!-- Composition: T18 composes_with T17, T16; read T0, T7 -->`). Handles Unicode subscripts (T₀), LaTeX (T_0), plain (T0). Returns `CompositionDeclaration` dataclasses with source, targets, relation, evidence, confidence. |
| `materialize.py` | Wires declarations into real CompositionEdge/NegationRecord objects stored via any ApachetaInterface. Discovers cairn tensors, builds label→UUID map, converts relations. |
| `__main__.py` | CLI: `uv run python -m yanantin.awaq [--tensor T15] [--json] [--list] [--materialize [--backend memory\|arango\|gateway]]` |
| `__init__.py` | Package init with public API exports |

Relations extracted: `composes_with`, `does_not_compose_with`, `corrects`,
`bridges`, `branches_from`, `read`, `standalone`. Confidence levels: high/medium/low.
Quote-leakage protection strips HTML comments, code blocks, and composition-keyword
code spans before prose extraction. Subset dedup prevents redundant declarations.
Current corpus: 28 declarations extracted from 20 source documents.

### Activity — Temporal Fact Storage (code: `src/yanantin/activity/`)

Facts are not tensors. Facts are raw observations — schema-agnostic,
high-volume, append-only. Tensors are authored compressions with
narrative structure. The activity stream stores facts; the anchor
service bridges facts to tensors. 8 source files.

| File | What it does |
|------|-------------|
| `models.py` | `FactRecord` (schema-agnostic observation, extra="allow"), `AnchorCursor` (provider position), `MemoryAnchor` (immutable cursor snapshot), `AnchorView` (ephemeral resolution, never stored). All frozen. |
| `store.py` | `ActivityStreamStore` ABC — 10 methods for facts and anchors. Append-only, no update, no delete. Same contract as ApachetaInterface. |
| `anchor.py` | `MemoryAnchorService` — two-flag write gate (updated AND referenced), cursor tracking, handle issuance. `materialize()` resolves anchors with late binding. `freeze()` pins a temporal view into a tensor (the authored act). |
| `backends/memory.py` | `InMemoryActivityStreamStore` — dict + bisect for O(log n) temporal queries. Thread-safe via RLock. Same pattern as Apacheta InMemoryBackend. |
| `backends/duckdb.py` | `DuckDBActivityStreamStore` — SQL query pushdown for temporal queries. Timestamps as ISO 8601 VARCHAR. Indexed on (provider_id, timestamp). |
| `backends/arango.py` | `ArangoDBActivityStreamStore` — AQL + persistent sorted index. Same least-privilege pattern as Apacheta. |

Three-stage lifecycle: **Anchor** (immutable cursor) → **View** (ephemeral
resolution, never cached) → **Tensor** (frozen/pinned view, authored act).
Late-binding materialization: new providers retroactively enrich old anchors.

### Collector — Data Pipeline (code: `src/yanantin/collector/`)

The bridge to human-side data. Collector/wrangler/recorder pattern from
Indaleko's 8-year evolution. First concrete implementation: machine config.
26 source files: 6 core + 4 filesystem + 4 fs_events + 4 dropbox +
4 checksum + 4 fact recorders.

| File | What it does |
|------|-------------|
| `base.py` | Four ABCs generic over DataT: `CollectorBase` (gather), `WranglerBase` (transport), `RecorderBase` (store tensors), `FactRecorderBase` (store facts). The recorder split: RecorderBase → tensors, FactRecorderBase → activity stream. |
| `models.py` | `ProviderRegistration` (frozen, identifies a collector/recorder pair), `WranglerEnvelope[DataT]` (frozen, wraps data with transport provenance — timestamps, strategy name, sequence number). |
| `wranglers.py` | Three concrete strategies: `DirectWrangler` (in-memory, same process), `BatchWrangler` (file-based, atomic write + rename), `QueuedWrangler` (deque, optional maxlen for backpressure). |
| `machine_config.py` | First concrete pair. `MachineConfigCollector` gathers platform identity from stdlib (hostname, OS, arch, CPU count, machine-id). `MachineConfigRecorder` stores snapshots as two-strand tensors. Convenience: `collect_machine_config()`, `collect_and_record(interface)`, `render_machine_config(data)`. |
| `pipeline.py` | End-to-end pipeline wiring: `open_store(backend)`, `record_and_anchor(store, recorder, envelope)`. Backend selection via string name + env vars. |
| `__main__.py` | CLI: `uv run python -m yanantin.collector` — `--store {memory,duckdb,arango}` for fact storage, `status` and `materialize` subcommands. Machine config default keeps `--record` for tensor path. |
| `__init__.py` | Package init, exports 14 public names. |

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

Depends on yanantin via path (editable). **150 tests** across 2 files.

### Willay — Epistemic Receipts (separate project: `/home/tony/projects/willay/`)

Verifiable claim-evidence attestation. Given a claim and citation (DOI,
URL, or PDF), retrieves evidence, hashes it, evaluates alignment, and
emits an immutable receipt with neutrosophic T/I/F scores.

| Layer | What it does |
|-------|-------------|
| `canonical.py` | Deterministic JSON serialization + SHA-256 hashing for receipts |
| `models.py` | EvidenceArtifact, Evaluation, ReceiptRecord. `receipt_to_tensor()` for Apacheta storage |
| `resolvers/` | DOI (CrossRef), URL (httpx), PDF (file + optional pymupdf) resolvers with auto-detect |
| `evaluator.py` | Claim-evidence alignment → T/I/F. MVP: retrieval + metadata check, I=0.8 (honest about limits) |
| `ledger.py` | Append-only JSONL with hash chaining + OTS anchoring via `yanantin.provenance` |
| `__main__.py` | CLI: `willay verify --claim "..." --doi/--url/--pdf`, `willay ledger show/verify/anchor` |

Depends on yanantin via path (editable). **68 tests** across 9 files (4 unit,
3 red-bar, 1 integration). Signed with project key `758840F4F386B5DFB14475FD`.
Has its own cairn (`docs/cairn/W0-origin.md`), CLAUDE.md, and memory bridge.

### The Cairn (docs/cairn/)

1010+ files. 24 tensors (T0-T7, T9-T24; T8 intentionally unwritten),
1000+ scout reports, 51+ scour reports, 12+ compaction records
(`docs/cairn/compaction/`). T0-T6 are now real files (symlinks replaced).
T22 is "The Bridge Begins" — the Indaleko story, collector module,
emergence conversation, and the Gemini khipu. Legacy `conversation_tensor_*`
duplicates removed — T*_*.md is the canonical naming. The cairn is
persistence — files on disk, in git, re-ingestible by the markdown parser.
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

Awaq (weaver + materializer)
  ↓ (reads cairn)
docs/cairn/ → CompositionDeclarations → CompositionEdge + NegationRecord
  ↓ (via any backend)
ApachetaInterface → 44 edges, 31 negations

Collector (data pipeline)
  ↓ (stdlib — platform, socket, os)
MachineConfigCollector → WranglerEnvelope → DirectWrangler
  ↓ (recorder normalizes)
MachineConfigRecorder → TensorRecord → ApachetaInterface → backend

Activity Stream (fact storage)
  ↓ (collectors)
FilesystemFactRecorder → FactRecord → ActivityStreamStore → backend
  ↓ (anchor service)
MemoryAnchorService → MemoryAnchor → ActivityStreamStore
  ↓ (freeze = authored act)
materialize(handle) → AnchorView → freeze() → TensorRecord → ApachetaInterface

Willay (receipts)
  ↓ (uses ApachetaGatewayClient)
Pukara → ArangoDB
  ↑ (receipt_to_tensor conversion)
ReceiptRecord → TensorRecord
```

Four paths to the interface: three local backends plus
`ApachetaGatewayClient` over HTTP to Pukara. The road to the fortress
is built. Awaq provides the composition graph; Chasqui provides the
epistemic diversity. The collector pipeline brings human-side data
(starting with machine config) into the tensor store. Willay stores
receipts through Pukara as tensors. The activity stream stores facts
(raw observations) separately from tensors (authored compressions),
with the anchor service bridging the two stores.

## What Doesn't Exist

| Name | Status | What it would be |
|------|--------|-----------------|
| **Tinkuy** | v0 — audit + succession + orphan check | Governance. Blueprint audit tool (`uv run python -m yanantin.tinkuy`), succession protocol with orphan tensor detection (`--check` includes orphans, `--check-orphans` standalone). Code: `src/yanantin/tinkuy/` (4 files). |
| **Gleaner** | v0 — in Chasqui | Extract structured claims from scout/scour reports. Deterministic pattern matching. Code: `src/yanantin/chasqui/gleaner.py`. Tests exist. LLM-guided extraction is future layer. |
| **Analyst** | v0 — in Chasqui | Cross-model topology detection from scout claims. Filters garbage, clusters by file reference, detects agreement across 3+ models. Code: `src/yanantin/chasqui/analyst.py`. 82 topological insights from 4122 claims across 164 models. CLI: `--analyze`. |
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
4. **The most recent tensor** (T₂₄) — "The Frozen Lake": the first real freeze, coverage blind spots, observation-to-artifact ratio, the system developing self-awareness. Or (T₂₂) — "The Bridge Begins": the Indaleko story, collector module, emergence conversation, cross-model convergence.
5. **One founding tensor** — read ONE of T0-T6 (now real files, not symlinks). Each gives a different perspective. T₀ = the experiment; T₁ = the architecture; T₂ = calibration and failure; T₃ = the finishing school; T₄ = RCS observer (ChatGPT); T₅ = the correction (ChatGPT); T₆ = the bridge. Let the composition graph diversify.
6. **docs/apacheta.md** — the design document for the tensor database.
7. **Sibling projects** — Willay (`/home/tony/projects/willay/CLAUDE.md`) has its own cairn and memory bridge. Pukara is the gateway.
8. **The direction** — next step is integrating Indaleko's human-side data (collectors, recorders, episodic memory) with yanantin's AI-side pipeline. The Archivist is the shared memory of a relationship. Build the bridge, not the merge.

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
