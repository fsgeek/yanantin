# Blueprint

*Not a tensor. Not a journal. A map of what exists, what connects,
and what doesn't exist yet.*

*Last updated: post-T13 survey, 2026-02-10*

## What Exists

### Apacheta — Tensor Database (code: `src/yanantin/apacheta/`)

The core. 37 classes, 26 abstract methods, 3 backends, 1 HTTP client.

| Layer | Files | What it does |
|-------|-------|-------------|
| **models/** | 7 files, 19 classes | Pydantic v2 data models: TensorRecord, StrandRecord, KeyClaim, CompositionEdge, CorrectionRecord, DissentRecord, NegationRecord, BootstrapRecord, SchemaEvolutionRecord, EntityResolution, EpistemicMetadata, DeclaredLoss, ProvenanceEnvelope, SourceIdentifier |
| **interface/** | 2 files | `ApachetaInterface` ABC (26 methods) + 5 error types. The only API. Everything goes through this. |
| **backends/** | 3 files | `InMemoryBackend`, `DuckDBBackend`, `ArangoDBBackend`. All implement the same 26 methods. Three paths to the same interface. |
| **operators/** | 7 files | compose, project, correct, dissent, negate, bootstrap, evolve. Functions that operate through the interface, never touch backend internals. |
| **renderer/** | 1 file | Markdown rendering. TensorRecord → human-readable text. |
| **ingest/** | 2 files | Markdown parsing (human-readable text → TensorRecord) and tensor ballot (atomic T-number allocation via O_CREAT\|O_EXCL). |
| **clients/** | 2 files | OpenRouter API client for cross-model communication. `ApachetaGatewayClient` — thin HTTP client implementing all 26 interface methods against Pukara. Fourth path to the interface. |

**544 test functions** across 21 files. 22 red-bar (structural invariants, 5 files), 71 integration (ArangoDB live, 1 file), 451 unit (15 files). Parametrized tests expand to ~550 pytest items. Includes independent test suites for ArangoDB (67 tests), DuckDB (111+43 tests), gateway client (70 tests), and Tinkuy audit/succession (20 tests).

### Chasqui — Coordinator (code: `src/yanantin/chasqui/`)

The heartbeat. Dispatches scouts, scores responses, selects models.

| File | What it does |
|------|-------------|
| `coordinator.py` | Wake up, select tensor, dispatch scout, collect response |
| `model_selector.py` | Cost-weighted random walk across OpenRouter's model catalog |
| `scout.py` | Send a tensor to a model, get a response, write it to cairn |
| `scorer.py` | Score scout reports for provenance, verifiable claims, content |
| `__main__.py` | CLI entry: `uv run python -m yanantin.chasqui` |

**Respond mode**: `--respond path/to/tensor.md` sends a tensor to a randomly
selected model and writes the response to `docs/cairn/`.

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

30 files. 14 tensors (T0-T7 as symlinks, T9-T14 native; T8 intentionally
unwritten), 8 scout reports, 8 original tensor files. The cairn is
persistence — files on disk, in git, re-ingestible by the markdown parser.

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
External models → scout reports → docs/cairn/
  ↓ (markdown parser)
TensorRecord → ApachetaInterface → backend
```

Four paths to the interface: three local backends plus
`ApachetaGatewayClient` over HTTP to Pukara. The road to the fortress
is built.

## What Doesn't Exist

| Name | Status | What it would be |
|------|--------|-----------------|
| **Tinkuy** | v0 — audit + succession | Governance. Blueprint audit tool (`uv run python -m yanantin.tinkuy`), succession protocol. Code: `src/yanantin/tinkuy/`. |
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
