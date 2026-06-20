# Forward Plan — Storage Spine, Hybrid Parallelism (for a fresh ghola to execute)

**Date:** 2026-06-20
**Author:** Yanantin (Opus 4.8), built at ~254k ctx and handed off — execute this cold.
**Decision (Tony):** full autonomy through Pour A end-to-end (no human gate at the dangerous seam; the red-bar + adversarial-review machinery IS the certification).
**Basis:** Codex codebase-status-review (`docs/codebase-status-review-2026-06-20.md`), reconciled against live verification (this session) + the program's intent. Where Codex and this plan differ, the difference is noted and the reason is "Codex audits artifacts; it cannot see intent or negative space."

---

## 0. Read these FIRST (the ghola's cold-start)
- This file. Then `docs/superpowers/specs/2026-06-19-uniform-storage-object-design.md` (the #17 spec — twice-reviewed, the Pour A/B definition lives in §3).
- Memory cluster (auto-loaded): `project_wake_note_storage_object_pour_a`, `project_core_complete_census_against_tonys_bar` (RUN-VERIFIED floor), `project_tool_usage_audit...`, `feedback_cannot_see_capabilities_i_lack...`.
- **Re-grep every symbol/line before trusting it — verified-against-code stamps have a half-life.**

## The shape: a **T**, not a line (corrected after Tony's input — I under-scoped first)
The plan has TWO parts with DIFFERENT parallelism:

**The STEM (serial chain):** P0 → Pour A → Pour B(#17) → factors → resolver. Each link is the substrate the next lands on. **You cannot parallel-agent a chain.** Within the stem, parallelism helps only in 4 bounded places (marked ⟫): xfail marking, adversarial diff review, Codex test authoring, factors/resolver design panel.

**The BAR (parallel fan-out): the data PROVIDERS.** Once the spine exists (StorageObject lands in Pour B + the activity stream, both nearly there), the data sources that feed it are **mutually independent** — different collectors/recorders, same registered pipeline. This is genuine fan-out, the place ultracode shines: N provider-builds concurrently, each its own worktree, each its own Codex tests. **This is what Tony has been focused on and what Codex's review does NOT contain** (Codex audited what's done; the providers are what Tony hopes to see done — the negative-space gap, `feedback_cannot_see_capabilities_i_lack`). My first draft drew the stem and called it the whole plan. The bar is the breadth.

**The five activity-stream data providers (Tony's authoritative set, 2026-06-20):**
| provider | the dimension it captures | status |
|---|---|---|
| file-change (storage mutation) | what CHANGED + when | seeded by `fs-events`; needs the StorageObject recorder path |
| Claude Code conversation | what was SAID | designed, deferred gh #33 until spine exists |
| semantic/unstructured extraction | what's IN the content (payload, read) | transducer #29 exists but orphaned; → open lane + BM25 view |
| query/find telemetry | what was LOOKED FOR (system observing its own recall) | gh #18 |
| **program execution history** | **what was DONE** (which programs ran, on what, producing what) | **NEW — the missing piece in BOTH Indaleko and Yanantin** |

**Execution history is the load-bearing-new one (Xerox Placeless lineage, Tony):** the first four are about data + its description; execution history is about ACTIVITY. Placeless made documents first-class by their USE and relationships, not their location ("the file I ran the analysis on," "the output of that job," "the file the build touched"). It gives the associative graph **action-edges**, not just content-edges — find a file by *what was done to it / what it was part of*, the Placeless move I-as-an-instance demonstrably lack (I reason by path because I have no action-history to reason from). It is also the stream the #17 temporal-correlation inference engine RUNS ON (the Discord "read file X at T" read-event IS execution history) — so it's the missing half of the derived-from edge.

Builder/tester separation is CI-ENFORCED (`.github/workflows/separation.yml`: no commit touches both `src/` and `tests/`; CI runs `pytest tests/ -v`). So every task = **two commits: test-only (Codex-authored) then src-only**. Yanantin-signed (override name+email+signingkey ALL THREE — `reference_ai_commit_signing_override`). OTS tail sweep is part of finishing.

---

## P0 — Make CI's "green" mean something (UPSTREAM OF EVERYTHING)
**Why first:** CI runs the full suite; 13 architectural-gap tests are expected-red but UNMARKED, so CI is permanently red and "did my fix work?" is unanswerable. You cannot certify Pour A's non-degradation against a permanently-red bar. Fix the SIGNAL before the dangerous pour. (Codex ranked this P1; it's P0 — it gates the measurability of all the rest.)

**Do NOT split `tests/red_bar/` into a separate CI job.** Verified: red_bar is **120 green + 13 red** — overwhelmingly the must-stay-green enforcement floor. Splitting by directory either stops gating the floor (catastrophic) or leaves CI red. The fix is **per-test marking.**

The exact 13 (verified `pytest tests/red_bar/ -q`), in 4 groups:
- `test_factor_shape.py` ×5 → gap: `yanantin.factors` (P2 below)
- `test_mechanism_invariance.py` ×4 → gap: `yanantin.resolver`/CompiledQuery (P2)
- `test_uniform_storage_object.py` ×3 → gap: #17 (Pour B)
- `test_llika_wall.py` ×1 → gap: Pukara credential boundary (#10/#13, cross-repo)

**Task P0 (Codex review #4 corrections folded):**
1. **COORDINATOR (single agent, ONE commit):** add `xfail_strict = true` to `[tool.pytest.ini_options]` in `pyproject.toml` (line ~29). NOTE: this is **config-side, not src** — the "no src" rule holds, but the commit message is "test/config-side". Do NOT let the parallel agents below touch pyproject.toml (write-conflict).
2. **⟫PARALLEL (after step 1 merges): one agent per test-FILE group, no shared state** — mark each of the 13 with `@pytest.mark.xfail(strict=True, reason="<gap>: <issue#>")` (so an xfail that PASSES becomes a failure — "you built it, now flip the guard"). The four file-groups (factor_shape×5, mechanism_invariance×4, uniform_storage_object×3, llika_wall×1) are distinct files ⇒ no merge conflict.
3. **EXCEPTION — `test_canonical_timestamps_are_uuid_named`:** do NOT mark "build toward green." The #17 spec §2/§5 says this guard asserts a SUPERSEDED requirement (UUID-keyed timestamps, obsoleted by Pukara) and must be **rewritten** when Pour B lands, not satisfied. Mark it `xfail(strict=True, reason="#17 SUPERSEDED — rewrite to flat-nullable-timestamp assertion in Pour B, do not satisfy as-is")`. This prevents the ghola from "fixing" it the wrong way.
**Gate:** `pytest tests/` → green with 13 xfailed. CI green. This is two commits (all test-side; no src). **Verify CI actually passes on the PR before proceeding.**

## P0.5 — opportunistic truth-fixes (do alongside P0, trivial)
- Version drift: `pyproject.toml` says 0.1.2, `src/yanantin/__init__.py` says 0.1.0. Pick one (0.1.2 is the package's own declaration; align `__init__`). src-only commit.

---

## P1 — Pour A: Khipu becomes sole collection creator ⚠️ THE DANGEROUS POUR
**This deletes `_ensure_collection` from live, tested `core/registration.py`.** Full autonomy (Tony's call) — but earn it with the machinery below. Spec: #17 §3 binding-gap.

**Pre-pour (serial):**
- Re-read `src/yanantin/core/registration.py` (the seam: `_ensure_collection` at ~119, called ~95/105; `_ensure_edge_collection` ~127). Re-grep — line numbers drift.
- Blast radius: `tests/integration/test_core_registration.py` (9 tests; 3 encode the create-it-yourself contract: `test_owned_collection_is_created_under_obfuscated_name`, `test_stacking_reproduces_objects_as_one_shared_collection`, `test_field_names_are_obfuscated_in_stored_documents`). These must be re-pointed to receive a Khipu-bound handle, not deleted.
- **Run the FULL registration suite + red_bar BEFORE. Record the baseline.** (`feedback_decided_decision_made` — certify against a known-green floor; P0 gave you one.)

### ⚠️ SPLIT INTO A1 / A2 (Codex review #1 — resolves the schema circular-dependency)
The original Pour A required `Objects` to carry the StorageObject schema — but StorageObject
doesn't exist until Pour B. That's a circular dep at the most dangerous seam; a cold
executor would have to invent a bridge. Resolved by splitting:

**Pour A1 — Khipu becomes the sole creator (no StorageObject dependency).** Build this NOW.
- Define the well-known `CollectionDefinition`s that DON'T need StorageObject:
  `<catalog>` (RegistrantRecord schema — exists today), `Relationships` (edge=True,
  ProvenanceEdge schema — exists today). For `Objects`: bind it via Khipu **schema-less for
  now** (a CollectionDefinition with `schema=None`) — Khipu creates it, but the StorageObject
  schema lands in A2. This is honest: the collection exists and Khipu owns it; the schema is
  explicitly a Pour-B deliverable, not a silent gap.
- REMOVE `_ensure_collection` AND `_ensure_edge_collection` from Registrar **entirely**
  (not "catalog exception" — leaves the schemaless-create path alive,
  `feedback_security_erosion_mechanism`).
- **Gate A1:** full registration suite + red_bar GREEN (== baseline); structural red bar
  green; `Objects`/`Relationships`/catalog all Khipu-created. Floor check (collector still
  lands facts in apacheta_test). NOTE: `Objects` is intentionally `schema:none` after A1 —
  that is NOT the final state; A2 closes it.

**Pour A2 — bind the StorageObject schema (AFTER Pour B builds the model).** Sequenced
*after* B's model exists. Updates the `Objects` CollectionDefinition to carry
`arangodb_schema(StorageObject)` + indices. **BUT** Khipu's init contract NEVER reconciles
schema on an existing collection (`test_khipu_schema_never_reconciled` — a GREEN guard).
So A2 is a **migration**, not an init edit (`project_collection_init_contract_schema_is_data_not_config`):
the executor must explicitly apply the schema to the live `Objects` collection (an Arango
`db.collection('Objects').configure(schema=...)` migration step), with a snapshot first
(see rollback below). Gate A2: live `Objects` carries StorageObject schema (NOT `schema:none`);
existing rows still validate or the migration reports which don't.

### Pour A1 Registrar API design (Codex review #2 — was under-specified)
"Registrar receives a Khipu-bound handle" must be a concrete constructor change, or
deleting `_ensure_collection` half-migrates. Today Registrar (`core/registration.py`)
stores `_catalog_name`/`_owned_name`/`_owned_edge_name` (semantic→obfuscated strings) and
calls `self._db.collection(name)` internally for insert/AQL. The migration:
- **`__init__` still takes semantic names** (`catalog_collection`, `owned_collection`,
  `owned_edge_collection`) AND a `khipu: Khipu` (or a pre-bound handle map). It KEEPS the
  semantic names for AQL bind-vars + obfuscation (unchanged — those are needed for
  `list_registrants`/`contribute`'s queries). What changes: instead of `_ensure_collection`,
  it calls `khipu.watay(name, well_known.lookup(name))` to OBTAIN each collection, storing
  the returned handle. Bind LATE at the caller — Registrar holds a Khipu ref passed in, does
  NOT import Khipu's creation logic (keeps them import-independent as today).
- **`contribute_edge`** (`_from`/`_to`): unchanged — endpoints are canonical `collection/key`
  ref VALUES built from `owned_collection_name` (the obfuscated name property stays). Khipu
  returning the handle doesn't change how edge endpoints are constructed.
- **Partial ownership** (only catalog, or catalog+owned, or +edge): preserve today's
  semantics — `owned_collection=None` ⇒ owned defaults to catalog (degenerate own-a-collection
  case); `owned_edge_collection=None` ⇒ no edge collection. Each non-None name gets a
  `watay` call; None stays None. The `owns_owned_collection`/`owns_edge_collection` properties
  are unchanged.
- A fresh executor MUST re-grep `core/registration.py` for the exact current attrs/methods
  before editing — line numbers drift (half-life).

**⟫PARALLEL (de-risks the serial step):** spawn 3 independent adversarial reviewers at the
A1 DIFF. Each prompted to REFUTE "this preserves the registration contract / introduces no
schemaless-create path / handles bootstrap (Khipu binds catalog without Registrar existing
first — verified no chicken-and-egg) / the constructor change doesn't break the 9
registration tests' contract." Majority-refute ⇒ stop and fix.

### Rollback (Codex review #5 — live schema/ownership change needs a snapshot)
Both A1 and A2 mutate live `apacheta_test` collection ownership/schema. Before each:
record the current collection list + `Objects` schema state; A2 specifically snapshots the
`Objects` collection (it's a schema migration on live data). If a gate fails, the rollback
is "recreate the collections Registrar used to create, restore the prior schema state." The
DB is ours and non-fatal to trash (`feedback_no_mock_databases`), but a recorded baseline
makes "did this degrade?" answerable — the whole point of doing P0 first.

## P1.5 — Arango conn-error discrimination (bounded, opportunistic)
2 strict xfails in `tests/unit/test_arango_conn_errors.py`; plan in `docs/plans/2026-06-01-arango-conn-error-discrimination-is-wrong.md`. Small, operator-trust value. Do between A and B if momentum allows; not blocking.

---

## P2a — Pour B: the StorageObject + Linux normalizer (#17 §1/§2/§3.5–3.7)
Lands on the Khipu-bound `Objects` from Pour A. Spec is the authority.
- Build `StorageObject` (extra="allow", NEVER forbid; uri spine; flat nullable timestamps; `semantic_attributes` open lane; `raw` retained).
- `FileEntryData → StorageObject` normalizer (kills `d.raw.timestamps.modified` → `d.modified`). Deterministic `object_identifier = uuid5(source, uri)`.
- RETIRE `ContributedRecord` (succession not duplication; `feedback_declared_loss_is_debt_not_payment`). **Codex review #6 — it is NOT only the linux recorder:** verified consumers are `recorder/storage/local/linux/registration.py:13,83` (src) AND `tests/integration/test_recorder_collection_mapping.py:6,21,28` (two constructions). Retirement therefore spans the builder/tester split: a **src commit** (recorder switches to StorageObject; delete the model) and a **separate test commit** (migrate `test_recorder_collection_mapping` to StorageObject or retire the cases that only existed to exercise ContributedRecord). Name both in the task; do NOT delete the model in one commit and strand the test import.
- **REWRITE `test_canonical_timestamps_are_uuid_named`** (the P0-flagged exception) to assert flat-nullable timestamps + no CANONICAL_TIMESTAMP_UUIDS. Same change, reasoning in commit.
**⟫PARALLEL (Codex test authoring):** the §5 new tests (round-trip through watay; poor-object/rich-object honest-absence; normalization; idempotent re-observation; derived_from edge; raw round-trip) are independent — author concurrently via `codex exec -s workspace-write` (default model, `< /dev/null`).
**Gate:** the 3 `test_uniform_storage_object` xfails flip to xpass → convert to real green assertions (xfail_strict makes xpass fail, forcing this). All against live apacheta_test.

## P2b — wire #29 (OpenRouter activity CLI) — CHEAP, but it is TELEMETRY not semantic extraction
**Codex review #5 — corrected, I had conflated two things.** Verified: `recorder/semantic/openrouter/fact_recorder.py` records each OpenRouter API call as a `FactRecord` (model/cost/tokens/timestamps/finish-reasons). That is **activity telemetry**, NOT "what's IN the content," and it does NOT write semantic extraction into a StorageObject open lane or BM25 view. So split the claim:
- **What P2b actually does:** wire the OpenRouter activity recorder to a CLI subcommand (mirror `_cmd_filesystem`). This is a cheap **second activity stream** ✓ — it closes Tony's "≥2 activity streams" bar item. Independent of the storage spine; do anytime after P0.
- **What it does NOT do:** it does NOT close "≥1 semantic transducer" in the sense the program means (unstructured CONTENT extraction). That is a **separate provider** in the P3-BAR fan-out (the "semantic/unstructured extraction" row), which reads file content into the open lane + BM25 view (`project_semantic_transducer_is_skunkworks...`) and REQUIRES StorageObject (Pour B). Do not mark the semantic-transducer bar item closed by wiring the OpenRouter CSV recorder.

---

## P3 — factors, THEN resolver (design-first; red bars exist, specs DON'T)
Order is load-bearing (Codex right): factors need StorageObject's normalized inputs; resolver needs factors or it's a fake interface.
**⟫PARALLEL (design panel — the wide-solution-space place a panel beats one attempt):** for EACH of factors / resolver, spawn N independent design agents (different angles: storage-first, llm-memory-first, query-first), score with a judge, synthesize. Output = a reviewed spec + plan, NOT code. The 5 factor_shape + 4 mechanism_invariance xfails are the acceptance tests the design must satisfy.
**Then** implement serially (factors before resolver), TDD, Codex-authored tests, two commits per task.

## P3-BAR — the provider FAN-OUT (the parallel work, gated on the spine)
**Gate to start:** Pour B landed (StorageObject lands in `Objects`; activity stream live). THEN the five providers fan out — genuinely parallel, ultracode's home.
**⟫PARALLEL (the real fan-out — one agent/worktree per provider; they share NO state, only the registered pipeline):**
- **file-change** — promote `fs-events` to watch the storage layer; emit change-facts (the temporal-window-reindex substrate). Likely FIRST of the bar (others lean on "what changed").
- **semantic/unstructured** — wire #29 (orphaned transducer) → content into the open lane + ArangoSearch view (the skunkworks-for-files move, `project_semantic_transducer_is_skunkworks...`). Independent of file-change.
- **query/find telemetry** — gh #18; find ops AS an activity stream. Independent.
- **program execution history (NEW)** — design FIRST (no spec exists; Placeless is the reference, not a codebase artifact — design-panel it like factors/resolver). Captures what-ran/on-what/produced-what; gives the graph action-edges; feeds the #17 inference engine. Highest design-novelty of the five.
- **Claude Code conversation** — gh #33; tail ~/.claude/projects. Build LAST of the bar (it's the dogfood ACCEPTANCE TEST for the whole substrate — `project_claude_code_conversation_provider...` — don't spend the best use case before the others prove the pipeline).
Each provider = its own worktree (`isolation: worktree`), its own Codex-authored tests, two-commit split. They merge independently.

**Dependency refinement (Codex review #7 — sharper than "file-change first"):**
- **OpenRouter activity CLI wiring (P2b)** — does NOT depend on StorageObject; can start right after P0. (This is the telemetry stream, not the semantic provider — see P2b.)
- **file-change** — needs StorageObject NORMALIZATION available (it emits change-facts about objects); starts after Pour B.
- **semantic/unstructured extraction** — MUST wait for StorageObject (writes into the open lane); after Pour B.
- **query/find telemetry** — depends on what "find" MEANS. If it records current query-CLI usage, it can start early (after P0). If it records the final factor/resolver-based find, it waits until after the resolver. Decide which "find" at build time; the early version is not wasted (it's the same activity-stream shape).
- **program execution history** — DESIGN SPEC before implementation (no spec exists; Placeless is the reference, not a code artifact; design-panel it).
- **Claude Code conversation** — LAST (dogfood acceptance test; don't spend the best use case before the pipeline is proven).
**Per-provider gate:** collector lands facts/objects in apacheta_test (re-run the census floor check); for semantic/conversation, a content search returns a hit (the 0→1 proof, `project_federation_runs_today...`).

## P4+ (deferred, correctly — leave alone until upstream settles)
Gateway routes (#10 cross-repo Pukara), query pushdown (wait for spine to settle — Codex right, "indexes chase a moving target"), harness completion, DuckDB decision (sharpen the deprecation or implement; don't invest in a discouraged backend).

### Llika wall — P0 xfail + a P1 CONTAINMENT item (Codex review #3, partially accepted)
Codex: don't downgrade the Llika wall to P4-only; the test demonstrates a working bypass.
**Accepted in part, grounded in the project's OWN threat model** (`project_ayllu_not_miraflores_multitenancy`,
`project_threat_model_integrity_not_confidentiality`): the adversary is a DATASTORE BREACH,
the tenants are KIN, and the agent-side process holding app credentials is the system's own
component in a single-operator research install — NOT a hostile party. So the failing test
is a real ARCHITECTURE-INTEGRITY gap (the boundary isn't enforced yet) but NOT a live
exploit by an attacker (there is none in the current deployment). Codex, reading from
outside the threat model, can't make that distinction (the same artifact-vs-intent gap).
**Therefore:**
- P0: mark `test_llika_wall` `xfail(strict, reason="#10 Pukara credential boundary — boundary not yet enforced")`. The xfail repairs CI; it does NOT reduce risk (Codex right on that).
- **P1 CONTAINMENT (add this — Codex's milder option, the right one):** explicitly DOCUMENT which credentials an agent process may hold, and do not WIDEN graph-capable app credentials into ordinary local agent workflows. This is "say the boundary out loud and hold the line," not breach response. The full fix (Pukara holds graph creds, agent does not) sequences with #10, cross-repo.

---

## What this plan CANNOT contain (the negative-space caveat — `feedback_cannot_see_capabilities_i_lack`)
Codex audited the built + the specced-but-absent. Neither Codex nor this plan can surface the MISSING-AND-UNCLAIMED — capabilities nobody specced because nobody felt their absence (e.g. temporal-window-reindex / time-addressing, surfaced THIS session only because Tony's prior Indaleko work pointed at it — `project_claude_code_conversation_provider_and_temporal_window_reindex`, gh #33 deferred). The roadmap needs BOTH the artifact-audit (this plan) AND the intent-vantage (Tony). Don't mistake "the plan is complete" for "the plan covers everything" — it covers what's visible from inside the artifacts.

## Execution harness (ultracode/Workflow)
Structure as ONE workflow with a SERIAL spine and parallel stages only at the ⟫ marks. Phases: `P0-mark` (parallel fan-out over 13 tests) → `PourA` (serial pour + parallel diff-review barrier) → `PourB` (serial impl + parallel Codex test authoring) → `design-factors`/`design-resolver` (parallel panels, output specs). Between phases: read the gate result, do not proceed on red. The pours themselves are NOT workflow-parallel — agent N+1 builds on agent N's merged result.
