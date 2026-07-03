# GOAL: Full-corpus landing (the 2.2M-file index) — batch write path + the production run

*Set 2026-07-03 after Tony's redirect: the resolver/when-pivot work is unaskable against a thin
database (35,805 Objects = 1.6% of the machine). The census vertical (a4e7004c) built the walk
guard, edge idempotence, and shape-report-as-activity — at fixture scale. This goal takes the
same guarantees to full scale and actually lands the corpus in production `apacheta`.*

## Grounding (measured 2026-07-03, not guessed)

- Machine holds ~3.15M inodes on one device (`/dev/sdd`, WSL2 root) — the `st_dev` guard
  geometry works; `/mnt` DrvFs bridges are excluded by the existing walk guard.
- Walk throughput: **12,573 entries/s** (collect-only over /usr/lib, 10,991 entries) →
  full walk ≈ 3 minutes.
- Write throughput, live server (192.168.111.127): single-doc `contribute()` = **457 docs/s**
  (2.2 ms/doc); chunked `insert_many(overwrite_mode="replace")` = **56,148 docs/s**. The
  current path (3 sequential HTTP ops per file: object + records-edge + contains-edge) would
  take ~4 hours non-restartable; the batch path lands the same ~6.6M docs in minutes. This is
  the Indaleko batch-model scar (`project_indaleko_batch_model_and_the_scar`), now measured here.
- Bulk replace-mode re-run keeps count stable (10k→10k) — idempotence survives batching because
  keys are uuid5(source:uri), structural not procedural.

## Design decisions

1. **Collector→file→recorder→bulk-import (the Indaleko fan-out).** The collector streams
   entries to JSONL instead of materializing 2.2M pydantic objects in RAM (~GBs). The JSONL
   *is* the retained raw (the factor shape's raw-retention invariant) — gzip and keep it,
   recorded location. Restartable: the landing step re-reads the file.
2. **The bulk path goes THROUGH the Registrar, not around it.** `contribute()` enforces
   attribution and collection ownership; a raw `insert_many` would route around that boundary
   for speed — the exact erosion `feedback_security_erosion_mechanism` names. Mechanism:
   `Registrar.contribute_many()` / `contribute_edge_many()` in core, same checks once per
   batch, same attributed shape per doc, chunked insert_many inside.
3. **No collector fork.** The batch path drives the SAME `LinuxFilesystemCollector` (walk
   guard included) — a streaming emit added to it, not a parallel walker.
4. **Target is production `apacheta`** (app tier). The corpus exists to be queried by find();
   the disposable test DB is for the red-bars. Baseline before run: Objects=35,805,
   Relationships=71,609 (recorded here so growth is checkable).

## Success criteria (each independently verifiable)

**1. Streaming collect.** The collector can emit entries incrementally to a JSONL sink without
holding the full tree in memory (generator or file-writer form; existing `collect()` untouched).
*Verify:* red-bar — walking a fixture tree yields the same entry set via stream as via
`collect()`, and the stream form never exposes a full-tree list.

**2. Registrar batch contribution.** `contribute_many` / `contribute_edge_many` exist on the
Registrar: ownership + attribution checks identical to the singular forms, chunked
`insert_many(overwrite_mode="replace")` inside, every landed doc carries the contributor
attribution the singular path would have given it.
*Verify:* red-bar on live `apacheta_test` — batch-landed docs are field-identical to
singular-landed docs for the same input (attribution included); zero-attribution docs impossible.

**3. Bulk idempotence (census 2b at the batch layer).** Landing the same JSONL twice changes
neither object count nor edge count — no doubled `contains` edges, no 409s.
*Verify:* red-bar — fixture walk → land → counts → land again → counts identical.

**4. Throughput gate, honest.** Sustained landing rate ≥ 10,000 docs/s over ≥ 100k real docs
(measured 56k/s on the probe; the gate sits 5x below measurement — refusing aspiration).
*Verify:* timed in the landing run's shape report; asserted by the run harness, not eyeballed.

**5. The production run lands.** Full-system walk (root `/`, existing guard excludes) → JSONL
(gzipped, retained, path recorded) → batch landing into `apacheta`. Objects count ≥ 2,000,000;
a CollectorShapeReport FactRecord for THIS run is queryable from the activity store; the
five distribution fields present (mtime bands feed the when-pivot next).
*Verify:* AQL counts + `query_range` returns the report. Growth measured against the recorded
baseline (35,805), not against zero.

**6. Re-observation at scale.** A second landing pass from the same JSONL leaves production
counts unchanged (idempotence holds at 2.2M, not just at fixture scale).
*Verify:* count before == count after re-land (cheap — it re-reads the file, no re-walk).

**7. No regression, environment honest.** Full unit + red_bar suites green at current baseline;
tests that need the live DB guard on it existing (skip-narrow when absent, CI-portable).

## Discipline
- Codex (GPT-5) authors the red-bars for criteria 1–4 BEFORE the build (builder/tester split).
- Live DB, no mocks. `apacheta_test` for tests (disposable); production `apacheta` only for
  criterion 5's run.
- Yanantin-signed commits (all three overrides); sweep the OTS tail after.
- Verify against git log + real runs before claiming done. file-exists ≠ feature-works.

## Out of scope (named, not built)
- The change/refresh recorder (needs this t₀ first — same as the census goal said).
- Pointing query/engine.py at the ArangoSearch view; any query definitions over the corpus.
- Semantic transducer sweep over file contents (separate pour, wants this corpus first).
- Checksums at scale (the walk lands stat metadata; content hashing is its own budget).
