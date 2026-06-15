# Handoff: Execute the machine-identity + filesystem-collector-wiring plan

**For:** A fresh instance, running with **ultracode** enabled.
**From:** The instance that wrote the spec + plan with Tony, 2026-06-14.
**Status:** Design done, reviewed, committed. Code NOT started. Your job is to build it.

---

## One-paragraph orientation

Yanantin's storage collectors got restructured today into domain-separated packages
(`collector/storage/local/linux`, `collector/activity/linux`, `recorder/…`, `transport/`,
`machine/`). That restructuring is **committed and green**. On top of it, Tony and I designed a
slice that gives machines a persistent identity and wires the filesystem collector to it with
graph edges. The spec is approved, the plan is written task-by-task with full code in every step,
and it has been **corrected against live code signatures**. You execute the plan. You do not
re-design it.

---

## Read these, in order, before writing any code

1. **The plan** — `docs/superpowers/plans/2026-06-14-machine-identity-filesystem-wiring.md`
   Six TDD tasks, complete code in every step. This is your script.
2. **The spec** — `docs/superpowers/specs/2026-06-14-machine-identity-and-filesystem-collector-wiring.md`
   The why behind the plan. Read for intent; the plan has the how.
3. **The restructuring context** — `docs/handoff-collector-recorder-architecture.md`
   The collector/recorder/wrangler architecture this all sits in.

Do NOT re-derive the design from the spec topic. It is already on disk. (Re-derivation felt as
discovery is a known failure mode here — if you feel like you're "figuring out" the edge model,
stop and read the plan; it's decided.)

---

## What you are building (the shape, so the plan reads fast)

- **`ProvenanceEdge`** — a new Pydantic model (`src/yanantin/apacheta/models/provenance_edge.py`),
  cross-collection ArangoDB edge with native `_from`/`_to` fields (alias'd to Python attrs
  `from_ref`/`to_ref`), free-string `relation_type`. NOT `CompositionEdge` (that's tensor→tensor,
  closed enum, wrong fit — this was a real decision, don't revert it).
- **`store_provenance_edge` + `list_provenance_edges`** on `ApachetaInterface` and all three
  backends (memory: real; arango: real, native edge insert; duckdb: `NotImplementedError` stub).
- **`MachineConfigRecorder.record()`** (`src/yanantin/machine/linux.py`) writes an
  `EntityResolution` keyed by machine_id (`entity.id = UUID(machine_id)` so the ArangoDB `_key`
  IS the machine id — directly addressable), idempotent (skip if exists), then the snapshot
  tensor (unchanged), then a `has_snapshot` edge machine→tensor.
- **`LinuxFilesystemCollector.__init__`** gains `machine_id: str | None = None` (falls back to
  `_get_machine_id()`).
- **`FilesystemFactRecorder`** gains optional `backend: ApachetaInterface | None` and
  `machine_id: str | None`; when both present, writes TWO edges per file fact: `contains`
  (machine→fact) and `collected_by` (provider→fact). When absent, behaves exactly as today
  (backward-compat test included).
- **Integration test** against `apacheta_test`.

---

## DECISIONS THAT ARE SETTLED — do not relitigate

- **Fine-grained per-file edges are the design.** 2 edges × 28.5M files = 57M edges is INTENDED.
  If it's ever too expensive, the mitigation is bulk insert (`arangoimport`/batch AQL), **NOT**
  reducing edge granularity, and **NOT** deriving from `provider_id` fields. I tried to talk us
  out of this with a storage-cost argument; Tony corrected it as premature collapse. The number
  (120GB for 50TB, edges <50% of that, ~4TB budget) says edges are cheap headroom. See
  memory `project_premature_collapse_caught_live`. If you find yourself wanting to "optimize"
  the edges away — that's the reflex, stop.
- **`relation_type` is a free string, not an enum.** Deliberate, to avoid vocabulary lock-in.
- **Machine identity ≠ machine config.** Identity is the stable `EntityResolution` (NER labels
  attach here). Config is the mutable snapshot tensor (changes per run). They are separate by
  design — do not merge them.
- **Out-of-order tolerance.** File records may reference a machine entity that doesn't exist yet.
  That's valid (NER resolves lazily). The caller-runs-machine-config-first ordering is a
  convention, not an enforcement. Don't add a hard dependency.

---

## Ground truth verified at handoff time (re-verify if stale — stamps have a half-life)

- **HEAD:** `fb9935bb` (ots sweep) on `main`. Working tree clean except auto-generated OTS stamps.
- **Test baseline:** `python -m pytest tests/unit/ tests/red_bar/ -q` →
  **1631 passed, 1 skipped, 3 xfailed, 14 FAILED.**
- **The 14 failures are INTENTIONAL red bars** for unbuilt work (gh #17 uniform storage object,
  #19 factor shape, #10 llika wall, plus a portability + mechanism-invariance guard). Their
  own assertion messages say so ("This guard is honestly red until the port lands"). They are
  NOT regressions and NOT yours to fix. Leave them red. Your tasks add NEW passing tests; do not
  touch the red_bar suite. Sanity check: none of the 14 import `provenance_edge`, `machine`, or
  anything you create.
- **`ActivityStreamStore` has NO `get_all_facts`.** It has `get_fact`, `query_latest`,
  `query_range(provider_id, start=, end=)`, `count_facts`. The plan's Task 5 test uses
  `query_range(collector.get_provider_id(), start=, end=)` — already corrected. Do not call
  `get_all_facts`.
- **`tensors` collection is EMPTY** (0 docs) and `entities` is EMPTY (0 docs). `composition_edges`
  has 281 (pre-existing tensor-composition data — leave alone). No storage data exists yet; this
  slice is the first thing that writes machine/file records.
- **`_get_machine_id()` lives in `yanantin.machine.base`** and reads `/etc/machine-id`
  (this machine: `8ae0edf526f3453ab1abaf04e1c75a4a`). The plan patches it via
  `unittest.mock.patch` at BOTH `yanantin.machine.linux._get_machine_id` and
  `yanantin.machine.base._get_machine_id` in places — keep both patches.

---

## Signing / commits (REQUIRED — CI enforces, and AI commits use per-command config)

Every commit in this repo from the AI uses per-command git config overrides, never repo config:

```bash
git -c user.name="Yanantin AI (Claude Opus)" \
    -c user.email="yanantin@wamason.com" \
    -c user.signingkey="1E416B1FB63AF88179EE0F38D0CAB9659C950893" \
    commit -S -m "..."
```

End commit messages with:
`Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

**OTS debt:** a `post-commit` hook stamps each commit to `docs/ots/{short_hash}.ots` but can't
self-commit, so every commit leaves ONE trailing untracked `.ots`. Sweeping the tail
(`git add docs/ots/*.ots` + a signed `ots: sweep` commit) is part of finishing. The single
`.ots` from the sweep commit itself is fine to leave.

---

## Database access

- ArangoDB at `:8529`. `apacheta_test` is the rw test DB. Host resolves via config; both
  `192.168.111.125` and `.127` work (same dual-homed host — neither is "stale," don't "fix" one).
- `ArangoDBBackend()` with no args uses the configured credentials. `ArangoDBActivityStreamStore()`
  same. The integration test (Task 6) hits `apacheta_test` live and cleans up after itself
  (deletes the test entity + edges by the fake machine_id).
- **`provenance_edges` collection does not exist yet.** Task 2 adds it to the Arango backend's
  collection list. If the collection-creation path needs it declared as an EDGE collection (type 3,
  not document type 2) for native traversal — verify this when you implement Task 2 step 6.
  Check how `composition_edges` is created in `arango.py` and mirror it; if it's created as a
  plain document collection there, `provenance_edges` can match, but native graph traversal
  (`FOR v IN OUTBOUND`) requires an edge-type collection. This is the ONE spot the plan flags as
  needing live verification — don't assume.

---

## Execution method

Tony's recommendation: **ultracode**, fresh context. Concretely:
- The six tasks are independent enough to pipeline but have a hard dependency order
  (1 → 2 → {3,4,5} → 6). Task 1 (model) and Task 2 (interface) must land before 3/5.
  Task 4 (collector machine_id) is independent of 1–3, can go anytime before 5.
- Each task is TDD: write failing test, see it fail, implement, see it pass, commit. The plan
  has the exact code and exact pytest commands with expected output for every step.
- After all six: run `python -m pytest tests/unit/ tests/red_bar/ -q`, confirm the 14 red bars
  are STILL exactly those 14 (no new failures, no accidental greening), confirm your new tests
  pass, sweep OTS, and report.

---

## When you're done

Verify against the spec's success criteria (section at the bottom of the spec). Then update Tony.
Do NOT close gh #17/#19/#10 — this slice doesn't satisfy them; it's the machine-identity layer
underneath, a different thing.

The data is the product. If something surprises you mid-build (an edge that won't insert, a
field that doesn't round-trip), that surprise is a finding — record it, don't paper over it.
