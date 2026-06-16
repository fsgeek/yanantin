# HANDOFF → C0 build phase

*2026-06-16. Written by the instance that did the two-day diagnosis, handing off at ~265k
tokens (before context-fatigue degrades ground-reading — which IS this session's core lesson:
don't act past the point your reading of the territory is reliable). You are waking into a
BUILD. The design is done and in ink. Your job is to pour concrete, reading the ground FRESH —
your un-fatigued territory-reading is the asset this handoff exists to deploy.*

## What just happened (one paragraph)

Tony asked "is the issue ledger coherent?" Two days of diagnosis followed; the answer was the
project IS coherent but its self-understanding had drifted from its own code (7 declared-vs-done
gaps, each a summary more optimistic than the ground). The work converged on: the common core is
missing its load-bearing primitive (DYNAMIC REGISTRATION), and the path forward is a strangler-fig
rewrite starting from `src/yanantin/core/`. You are building the first stones.

## READ THESE FIRST, in this order (don't re-derive — it's all decided)

1. `docs/north-star.md` — the GOAL (find-across-silos, timestamp-as-pruner, nested tenants).
2. `docs/three-spaces-and-the-common-core.md` — the bifurcation (AI / human-activity / joint /
   core); common core = the CONTRACT, not the interface.
3. `docs/common-core-missing-primitive-registration.md` — registration is the missing primitive
   (gh #1), the FIRST POUR, a dependency-free leaf. **Design source to PORT (read, don't reinvent):
   `~/projects/indaleko/utils/registration_service.py`** — `create_provider_collection(id, schema,
   edge, indices, reset)` + a provider collection (= the "one static config collection").
4. `docs/c0-bottom-up-build-order.md` — Tony's build order + `src/yanantin/core/` (start NOW,
   registration only, strangler-fig) + `YANANTIN_DATA_ROOT` (core/paths.py). **This is your build
   spec.**
5. `docs/salvage-inventory.md` — what must carry forward for this to stay Yanantin not a replacement.

Memories (auto-loaded): the `registration`, `north_star`, `indaleko_batch_model_and_the_scar`,
and `undeclared_triage` memories are the live ones. Trust them, but RE-GREP symbols before relying
on line numbers (a "verified" stamp has a half-life — this session proved it 3×).

## THE BUILD (in order — each tested green vs the LIVE apacheta_test DB, no mocks)

1. **`mkdir src/yanantin/core/`** — the physical boundary, born before anything moves into it.
2. **`core/paths.py`** — `data_root()`/`staging_dir()`/`mapping_path()` reading `YANANTIN_DATA_ROOT`
   etc., single-root defaults (`~/.yanantin/data`). Kills the 4-way DuckDB-default scatter
   (collector/__main__, query/__main__, collector/pipeline.py, chasqui/coordinator.py all hardcode
   `~/.local/share/yanantin/activity.duckdb` — make them resolve to one function). Config STAYS at
   `~/.yanantin/config/` (data ≠ config).
3. **`core/registration`** — PORT Indaleko's `registration_service.py`. A provider collection +
   `create_provider_collection(id, schema, indices, edge)`. Test in isolation: register → assert
   the collection exists with that schema + indices → green. This is NEW code = zero blast radius.
4. (Later, not yet) A1: #17 storage object REGISTERS itself via the new mechanism; the two
   `_SEMANTIC_COLLECTIONS` tuples (apacheta + activity backends) converge onto registration.

## TRAPS (this session tripped or nearly tripped every one)

- **Do NOT add collections by editing `_SEMANTIC_COLLECTIONS`** — that IS the shoehorn the whole
  rewrite exists to kill. Register.
- **Do NOT "fix" the blob-recorder with per-record write loops** — that rebuilds the one-at-a-time
  slowness Indaleko's BATCH model exists to avoid (140GB staging vs 35GB resident proves single-
  tensor was never viable). The fix is recorder→ephemeral-staging→`arangoimport` fan-out. NOT YOUR
  JOB YET (that's A2), just don't get nerd-sniped into it.
- **The DB singleton fail-stops** — no storage = hard stop. Do NOT add an in-memory fallback /
  graceful-degradation (the LLM reflex). Simulating a capability you don't have is the lie.
- **core/ grows by DECISION + tested-green migration, never by "feels core."** Day one: paths +
  registration only. machine/tinkuy/apacheta-contract stay OUT until decided + tested.
- **Re-read the live file before "correcting" anything** (memory, code, a teammate's claim). This
  session: an adversarial judge manufactured a memory "drift" the live file didn't have; a scout
  rounded "recorder writes wrong shape" up to "recorder exists." The ground is more honest than the
  summary, every time.

## OPEN ITEMS (Tony's calls — do NOT collapse these; they're honestly open)

- **awaq** — Tony can't describe what it does; risky-rebuild. RE-READ it and recover its function
  BEFORE any keep/drop decision. (This is the project's own thesis happening to its author — treat
  it as important.)
- **machine** — Tony "core?", I argued "it's a collector." Genuine architecture disagreement.
  Resolve before slotting; it does NOT enter core/ until then.
- **tinkuy** — verify-before-carrying (suspect vestigial).
- **StandardDatabase routing seam** (which DB a call goes to; capabilities/handles Pukara routes
  on) — its own brainstorm, Tony driving. (1)-its-own-design vs (2)-fold-into-C0 is OPEN; but the
  simple single-DB build does NOT depend on it — build on one StandardDatabase now.

## Ground rules (Tony's standing instructions — in the auto-memory, but so you don't miss them)

Act, don't propose-and-wait. Don't offer binary/multiple-choice menus as a substitute for a
position or for analysis (both got caught this session). Stronger tests are never an error. Don't
throw anything away — the data is the product. Sweep the trailing OTS `.ots` after committing
(Yanantin-signed: key `1E416B1FB63AF88179EE0F38D0CAB9659C950893`, per-command git config override).
