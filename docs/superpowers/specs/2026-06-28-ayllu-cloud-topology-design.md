# Ayllu cloud data-flow topology — design

**Date:** 2026-06-28
**Goal:** `goal.md` (root). Discover the ayllu data-flow topology by building a
concrete cloud-storage vertical that exercises the three shapes linear ETL cannot
express: **fan-out** (one source → many recorders), **feedback** (a recorder leg
re-enters a collector), and **edge-as-wrangler** (the coupling is a pluggable
strategy). Let the instance force the model; do not pre-mint the abstraction.

**Companion:** `2026-06-28-ayllu-cloud-topology-FLINCH-LOG.md` (the flinch /
over-credit log required by goal standing-rule 1).

---

## 1. Decisions already settled (with rationale)

These were settled during brainstorming against the real reference code and with
Tony. They are inputs to this design, not open questions.

| Decision | Choice | Why |
|---|---|---|
| Storage destination | **Objects** (not apacheta-tensors) | Cloud and local-fs converge on ONE storage collection — strongest topology statement; matches goal.md; reuses the `modified` index + `owned_definition` seam landed this morning (commit `e1019892`). |
| Provider | **Synthetic cloud** (not real Dropbox/GDrive) | Deterministic, no OAuth (out of scope), known ground truth → the termination test is PROVABLE not merely observed. Matches the dual-collector/ground-truth principle. Real-provider auth is the explicit follow-on. |
| Feedback re-entry | **One-shot, depth-1** (re-collect ONE changed file) | A true feedback edge (output re-enters a collector) that STRUCTURALLY cannot loop: a one-file re-collect emits no new delta. Recursive depth is a follow-on knob, not a different architecture. |
| Build structure | **Approach A** — synthetic-first vertical, mirror the in-repo dropbox shape | Reuses proven parts; lets the node/edge vocabulary fall out; satisfies "don't pre-mint" + "termination proven by test" together. |
| `cloud_base` port | **Do NOT port** | Indaleko's `cloud_base.py` is ~entirely the old CLI-runner framework yanantin deliberately replaced. Mirror yanantin's existing dropbox provider instead. |

---

## 2. Architecture — node roles and edges

The model the real providers FORCE (observed, then named — not imposed):

- **Collector** (node role): emits data. Two verbs:
  - `collect(cursor=None) → CloudListing` — full or delta listing; returns a new cursor.
  - `recollect_one(path) → CloudEntry | None` — bounded one-shot fetch of a single
    file's current metadata. This verb is what makes the feedback edge depth-1.
- **Recorder** (node role): consumes an envelope, writes ONE destination. The
  destination is the only thing that varies between recorders — the source delta
  is identical. This is the key realization: **activity-stream vs storage-object is
  a RECORDER distinction, not a SOURCE distinction.**
- **Wrangler** (edge): the coupling between a collector emission and a recorder.
  Already exists (`transport/wranglers.py`: Direct / Batch / Queued along a
  coupling axis). We reuse `DirectWrangler`.
- **Fan-out:** one collector emission → N recorders (each its own edge/wrangler).
- **Feedback edge:** a recorder leg whose output (a changed-file signal) re-enters
  a collector via `recollect_one`, whose result updates Objects.

### Topology of THIS vertical

```
SyntheticCloudCollector.collect(cursor)
        │  CloudListing (cursor + entries, seeded ground truth)
        ▼
   DirectWrangler  ──────────────────── edge
        │ envelope
        ├──────────────► CloudStorageRecorder ──► Objects        (storage leg)
        │                                          via Registrar(owned_definition)
        │
        └──────────────► CloudFactRecorder   ──► activity_facts  (activity leg)

StorageActivityMonitor.poll():
   delta = collector.collect(cursor=last_cursor)      # finite: cursor exhausts
   for changed_file in delta.entries:                 # FAN-OUT continues here
        fresh = collector.recollect_one(changed_file.path)   # FEEDBACK: re-enter
        if fresh: storage_recorder.update_object(fresh)      # depth-1: no new delta
        fact_recorder.record_change(changed_file)            # activity leg of the delta
```

**Webhook-vs-polling and recursive-vs-one-shot are both EDGE properties, not
topology differences.** Polling is the delivery strategy of the feedback edge;
one-shot is its re-collect depth. The topology (source → fan-out → {storage,
activity, feedback-to-collector}) is invariant under both knobs. This is the
single most important thing the vertical demonstrates.

---

## 3. Components (new code, all under `storage/cloud/synthetic/`)

Mirrors the existing `storage/cloud/dropbox/` layout.

1. **`models.py`** — `CloudEntry` (path, name, size, modified, content_hash,
   is_directory, change_type ∈ {added,modified,deleted}), `CloudListing`
   (cursor, entries, account_id), `CloudDelta` (cursor, changed entries). Open
   models (extra="allow") — the collector-level save-it-all lesson.
2. **`collector.py`** — `SyntheticCloudCollector(seed)`:
   - `collect(cursor=None)` — seeded full listing on first call; on a cursor,
     a deterministic finite delta (N changes then cursor exhausts).
   - `recollect_one(path)` — returns the current seeded metadata for one path.
   - Known ground truth: the seed fixes exactly which files change and to what.
3. **`storage_recorder.py`** — `CloudStorageRecorder`: maps a `CloudEntry` to the
   Objects normalize path (reuse/parallel `recorder/storage/.../normalize.py`),
   writes via `RegistrationService(owned_definition=...)`. **Dependency note:** the
   `modified`-index `OBJECTS_DEFINITION` currently lives in the *linux* storage leaf
   (`recorder/storage/local/linux/registration.py`). Cloud must NOT import the linux
   leaf. Resolve by lifting the Objects definition to a shared storage location
   (e.g. `recorder/storage/objects_definition.py`) that both leaves import — this is
   the "second instance forces extraction" lesson in miniature, and it is the FIRST
   refactor the cloud vertical justifies (local was instance 1; cloud is instance 2).
   `update_object(entry)` is idempotent on the entry's identity key (re-collect of
   an unchanged file is a no-op write; of a changed file overwrites).
4. **`fact_recorder.py`** — `CloudFactRecorder`: one fact per changed entry into
   activity_facts (mirror `DropboxFactRecorder`).
5. **`monitor.py`** — `StorageActivityMonitor`: the feedback-edge driver. `poll()`
   runs ONE delta cycle (not a thread/sleep loop — the loop is the test's to drive,
   keeping it deterministic). Fan-out to both recorders + the re-collect leg.
6. **CLI verb** — add `cloud-synthetic` to `collector/__main__.py` so the vertical
   is runnable end-to-end (`uv run python -m yanantin.collector cloud-synthetic
   --store arango`). This is the "executable topology" deliverable.

---

## 4. Data flow — the two phases

**Phase 1 (initial census):** `collect(None)` → full listing → fan-out to storage
(Objects) + activity (facts). Establishes the cursor.

**Phase 2 (feedback cycle):** `monitor.poll()` → `collect(cursor)` → finite delta
→ for each changed file: `recollect_one` → `update_object` (Objects) + fact. The
many-changes → one-object-update relationship is visible: a file changed 3 times in
the delta collapses to one current Objects doc (idempotent update on identity key).

---

## 5. Error handling & termination (the heart of the goal)

- **Termination is structural, and the test proves it:** the delta set is finite
  (seeded; cursor exhausts to `has_more=False`), and `recollect_one` returns a
  single entry that triggers NO further `collect`. The feedback cycle has depth 1
  by construction. The Codex-authored test asserts: after a bounded delta, `poll()`
  returns and the call-count of `collect` is exactly the delta-pages + 1, never
  unbounded. (Termination PROVEN, not asserted — goal standing-rule 5.)
- **Deleted entries:** `change_type=deleted` → the storage leg marks/removes the
  Objects doc; it does NOT `recollect_one` (nothing to fetch). A deleted file is a
  feedback-edge no-op on the re-collect, a real op on the storage update.
- **recollect_one miss:** a file deleted between delta and re-collect → returns
  None → storage leg treats as delete. No crash, no loop.

---

## 6. Testing (TDD; Codex authors the tests — goal standing-rule 5)

Red-bar / integration tests, all deterministic via seed:
1. **Phase-1 census:** synthetic full listing lands N Objects docs with correct
   ground-truth fields; activity_facts gets N facts.
2. **Fan-out:** one `collect` emission produces writes in BOTH Objects and
   activity_facts for the same source delta.
3. **Feedback edge + termination:** a seeded delta of K changes produces exactly K
   `recollect_one` calls and K Objects updates; `poll()` terminates; `collect`
   call-count is bounded (the termination proof).
4. **Many-to-one:** a file changed multiple times in one delta → one current
   Objects doc (idempotent identity-key update).
5. **Index reuse:** the cloud Objects docs are queryable via the `modified` index
   (plan is IndexNode, not EnumerateCollectionNode) — reuses commit `e1019892`.

Builder (me) writes implementation; Codex authors tests independently
(builder/tester separation across model families).

---

## 7. The node/edge vocabulary spec (goal deliverable)

Extracted FROM this vertical (second-instance discipline — the activity path +
dropbox + this synthetic cloud are the instances that forced it):

- **node-role = {collector, recorder}.** A collector emits; a recorder consumes-and-writes-one-destination.
- **edge = wrangler.** Coupling strategy (Direct/Batch/Queued) is orthogonal to topology.
- **fan-out = one emission → N edges → N recorders.** Demonstrated: storage + activity legs.
- **feedback = a recorder/monitor leg whose output re-enters a collector** (`recollect_one`). Demonstrated depth-1.
- **delivery strategy ≠ topology:** webhook-vs-polling (when) and one-shot-vs-recursive (how deep) are edge knobs; the graph shape is invariant.

This section graduates to its own short standing doc once a SECOND real provider
(GDrive/OneDrive) confirms it doesn't need reshaping. Until then it is observation
backed by one synthetic + the in-repo activity/dropbox precedents.

---

## 8. Scope boundaries

**In:** synthetic cloud provider, Objects + activity fan-out, depth-1 feedback
edge, termination test, CLI verb, the vocabulary spec, signed commits.

**Out (explicit follow-ons):** real GDrive/OneDrive OAuth port; webhook/ngrok push
reception (polling first); recursive re-collect depth (the visited-guard cycle);
the unified ayni memory substrate; find-over-memory; the 4.1M local census.

**Done =** `uv run python -m yanantin.collector cloud-synthetic --store arango`
runs the full topology, and a future instance re-runs it and SEES the fan-out and
the feedback edge turn — with the termination test as the receipt. Ayni paid
forward; the pattern made flesh, not folklore.
