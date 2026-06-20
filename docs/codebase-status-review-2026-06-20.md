# Codebase Status Review

**Date:** 2026-06-20  
**Reviewer:** Codex  
**Scope:** Repository status, implemented surface, likely working paths, known gaps, and called-out but unimplemented functionality.

## Executive Summary

Yanantin is a real, broad Python codebase, not just a sketch. It has a supported core around Apacheta tensors, activity facts, and structured query execution, plus a large research and operations surface: collectors, recorders, Khipu/registration, Llika graph traversal, Chasqui, Awaq, Jabberwock, experiment harnesses, infrastructure, and provenance tooling.

The supported core appears usable at local/test scale. The wider operational surface is substantial and often well tested, but the repository is not currently green end-to-end. The main blockers are intentional red-bar architectural gaps, one live Llika privilege-boundary failure, a few documented backend limitations, and small packaging/status mismatches.

## Verification Run

Commands run:

```bash
uv run pytest --collect-only -q
uv run pytest -q
uv run python examples/minimal_in_memory.py
```

Observed results:

```text
1935 tests collected
1919 passed, 13 failed, 1 skipped, 3 xfailed
```

The README quickstart example runs successfully. Package import checks for `InMemoryBackend`, `InMemoryActivityStreamStore`, and `QueryEngine` succeeded.

The working tree at review time was:

```text
## main...origin/main [ahead 28]
?? docs/ots/9d9ee285a5.ots
```

This review did not modify or remove that untracked file.

## What Exists

### Supported Core

The documented supported core in `docs/stability.md` is the most reliable public-surface guide:

- `yanantin.apacheta.models`
- `yanantin.apacheta.interface`
- `yanantin.apacheta.backends.memory`
- `yanantin.activity.models`
- `yanantin.activity.store`
- `yanantin.activity.backends.memory`
- `yanantin.query.models`
- `yanantin.query.engine`

This layer is broadly implemented and covered by tests. The in-memory Apacheta path works for examples and local prototypes. Activity facts and query models are implemented. Query execution works at test scale.

### Active Operational Surface

These areas exist and have meaningful tests:

- Apacheta Arango backend.
- Activity DuckDB and Arango backends.
- Collector and recorder split, including filesystem, checksum, fs-events, Dropbox, OpenRouter, synthetic collectors, and activity fact recorders.
- Khipu and registration machinery.
- Llika graph service and graph backend protocol.
- Infrastructure setup/configuration tooling.
- Provenance timestamping with OpenTimestamps.

### Research Surface

These are substantial but should be treated as research/operations code rather than stable package surface:

- `yanantin.chasqui`
- `yanantin.awaq`
- `yanantin.jabberwock`
- `yanantin.experiments`
- `yanantin.tinkuy`
- `tools/`, `experiments/`, `docs/cairn/`

The experiment harness is more advanced than older docs imply: capture, pre-registration, panels, prompts, runner, tool variants, budget behavior, and name-effect smoke coverage exist.

## What Reasonably Works

- README quickstart and `examples/minimal_in_memory.py` run.
- Core Pydantic models instantiate and round-trip in supported paths.
- In-memory Apacheta backend is usable.
- Activity in-memory backend is usable.
- Query engine works across memory and DuckDB in tests.
- Arango-backed tests mostly run locally, indicating that the local infrastructure path is live and much of it works.
- Collector/recorder scaffolding is real and exercised.
- OpenRouter experiment harness pieces are implemented with test doubles and guarded live tests.
- Chasqui/Awaq/Jabberwock/Tinkuy have meaningful unit coverage.

## Implemented But Risky Or Incomplete

### Test Suite Is Not Green

The full suite currently fails 13 red-bar tests. CI runs `uv run pytest tests/ -v`, so the current repo should fail CI unless CI lacks the same local infrastructure or is otherwise configured differently.

### Llika Privilege Boundary Fails Locally

`tests/red_bar/test_llika_wall.py::test_agent_side_process_cannot_obtain_working_llika_graph_handle` fails because an agent-side process can construct `LlikaService(ArangoDBBackend(...))`, write a Llika edge, and traverse it without going through Pukara.

This is different from a missing module. The code exists and works, but it violates the intended security boundary. The intended fix appears to be credential separation: Pukara holds the privileged graph backend credentials; the agent process does not.

### Query Execution Is Python-Side

`yanantin.query.engine` fetches facts from stores, filters in Python, and then paginates. This is correct at test scale but not a large-scale query engine.

Apacheta Arango query methods also still use load-all-and-filter logic for many domain queries. That is operationally limited even if behaviorally correct in tests.

### Backend Error Discrimination Has Known Xfails

Two strict xfails in `tests/unit/test_arango_conn_errors.py` document that Arango connection-error discrimination still misclassifies real driver failures.

The plan is captured in:

```text
docs/plans/2026-06-01-arango-conn-error-discrimination-is-wrong.md
```

### DuckDB Has A Known Null-Byte Limitation

One strict xfail documents that DuckDB truncates null bytes in JSON serialization. This is a real storage limitation, not a flaky test.

### Version Metadata Is Stale

`pyproject.toml` declares:

```text
version = "0.1.2"
```

But `src/yanantin/__init__.py` reports:

```python
__version__ = "0.1.0"
```

That is a packaging/status bug.

### Experiment Runner Has Declared Gaps

`RunnerConfig.per_call_timeout_s` exists, but the runner does not apply it around the `client.complete` call. The runner is sequential; the plan acknowledges no concurrent request cap yet. This is probably acceptable for first experiments, but not for larger sweeps.

## Called Out But Not Implemented

| Functionality | Current Status | Missing Pieces |
| --- | --- | --- |
| `yanantin.factors` six-factor shape | No module; five red-bar failures in `tests/red_bar/test_factor_shape.py`. | Conceptual architecture exists in convergence docs/tests. Detailed design and implementation plan are still needed. Test plan exists as red bars. |
| `yanantin.resolver` / `CompiledQuery` | No module; four red-bar failures in `tests/red_bar/test_mechanism_invariance.py`. | Architecture idea exists: one resolver, factor constraints, no consumer branching. Missing detailed design and implementation plan. Tests exist. |
| Uniform `StorageObject` | No `yanantin.collector.storage_object`; three red-bar failures in `tests/red_bar/test_uniform_storage_object.py`. | Design exists in `docs/superpowers/specs/2026-06-19-uniform-storage-object-design.md`. Implementation absent. Test plan is partially stale because the newer spec says the UUID timestamp guard should be rewritten. |
| Registrar/Khipu collection separation | `Registrar` still creates collections directly. | Design/spec exists in the StorageObject spec. Missing implementation: Khipu as sole collection creator, well-known definitions, and migration tests. |
| Gateway open-record queries | `ApachetaGatewayClient` raises `NotImplementedError`. | Yanantin client stubs exist. Missing Pukara routes, gateway integration tests, and coordinated implementation. |
| Gateway provenance edges | `ApachetaGatewayClient.store_provenance_edge` and `list_provenance_edges` are route-pending stubs. | Missing Pukara API/routes and client implementation. |
| DuckDB Apacheta open-record/provenance-edge support | Explicit `NotImplementedError` stubs. | Intentionally deferred/deprecated. Needs a decision: delete from interface/backend or implement honestly. |
| StorageObject cloud/accidental normalization | Explicitly deferred by uniform storage spec. | Per-collector plans and tests needed after Linux normalization lands. |
| Temporal-correlation inference engine | Explicitly deferred by uniform storage spec. | Needs its own architecture, confidence model, false-positive handling, implementation plan, and tests. |
| Remaining memory-tool functions and analysis loop | Only `find_objects` appears landed from the memory-tool surface. | Implement remaining tools, analysis script, and second-iteration experiment plan. |

## Gap Categories

### Architecture Missing

- `yanantin.factors`
- `yanantin.resolver`
- Large-scale query execution strategy
- Temporal-correlation inference engine
- Fully enforced Pukara/Llika credential wall

### Design Exists But Implementation Missing

- Uniform `StorageObject`
- StorageObject Linux normalization
- Registrar/Khipu collection-separation completion
- Pukara gateway routes for open-record and provenance-edge APIs

### Test Plans Exist

- Red-bar tests for factor shape, resolver mechanism invariance, uniform storage object, and Llika wall.
- Strict xfails for Arango connection-error discrimination.
- Strict xfail for DuckDB null-byte behavior.
- Experiment harness tests for capture, panels, prompts, runner, tool schemas, and budget behavior.

### Test Plans Need Updating

- `tests/red_bar/test_uniform_storage_object.py` still asserts canonical timestamp UUIDs, while `docs/superpowers/specs/2026-06-19-uniform-storage-object-design.md` says that guard is superseded by flat nullable timestamp fields and should be rewritten when #17 lands.

### Implementation Plans Missing Or Incomplete

- Detailed implementation plan for `yanantin.factors`.
- Detailed implementation plan for `yanantin.resolver`.
- Coordinated cross-repo Pukara plan for gateway route completion.
- Query pushdown/scaling plan for Activity and Apacheta queries.
- Analysis/iteration plan after first memory-tool experiment run.

## Recommended Order Of Work

1. Decide whether red-bar tests are intended to block CI right now. If yes, the repo is knowingly red and should be treated as mid-architecture. If no, move feature-gate red bars to a separate marker or CI job.
2. Fix or isolate the Llika privilege-boundary failure. This is the highest-risk implemented behavior because it contradicts the intended security model.
3. Fix version metadata drift between `pyproject.toml` and `src/yanantin/__init__.py`.
4. Resolve the Arango connection-error discrimination xfails with live-driver tests.
5. Land the StorageObject path before building higher-level factor/resolver work on top of storage semantics.
6. Turn the factor and resolver red bars into concrete designs and implementation plans.
7. Decide the future of DuckDB as an Apacheta backend: delete/deprecate harder, or implement the deferred pieces.
8. Add query pushdown only after the data model and storage object spine settle; otherwise indexes may chase a moving target.

## Bottom Line

The package core is usable and the repo contains a large amount of working code. The operational and research layers are not pretend scaffolding, but several of the project’s most important architectural claims are still enforced only as red bars, not implemented systems.

The codebase is best described as: stable enough for local/core use, active and ambitious in operational paths, but not release-clean or CI-green until the architectural red bars and privilege-boundary issue are resolved or explicitly isolated.
