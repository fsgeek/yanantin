# The ayllu data-flow topology — node/edge vocabulary

**Date:** 2026-06-28
**Status:** Extracted from a working instance, not pre-minted. Backed by THREE
instances: the in-repo activity path (`pipeline.py`), the dropbox provider, and the
synthetic cloud vertical built this session (commits `ea810708`…`be05c2f8`). This
is observation that earned its generality, per the second-instance discipline —
NOT an abstraction imposed ahead of the code.

**Runnable proof:** `uv run python -m yanantin.collector cloud-synthetic`.
**Design:** `2026-06-28-ayllu-cloud-topology-design.md`. **Flinch log:**
`2026-06-28-ayllu-cloud-topology-FLINCH-LOG.md`.

---

## Why this exists: linear ETL is the wrong shape

The intuitive model — `collector → wrangler → recorder → loader`, a line — is wrong
for this system, and the wrongness is not academic. Two real shapes break it:

- **Fan-out:** one source emission feeds MANY recorders. The cloud delta feeds a
  storage recorder (→ Objects) AND a fact recorder (→ activity_facts) at once.
- **Feedback:** a recorder/monitor leg's output RE-ENTERS a collector. A changed
  file triggers a re-collect, whose fresh metadata updates the storage object.

A line cannot express either. The system is a **directed graph whose edges are
wranglers**, with fan-out and feedback. It is an ayllu, not an assembly line.

---

## The vocabulary (what the instances forced)

### Node roles
- **Collector** — emits data. Verbs observed across the three instances:
  - `collect(cursor=None) → listing` / `collect(cursor) → delta` (full vs incremental)
  - `recollect_one(path) → entry | None` (bounded one-shot; the feedback primitive)
  A node may be BOTH a source and a re-entry target (the feedback edge proves this).
- **Recorder** — consumes one envelope, writes ONE destination. **The destination
  is the only thing that varies between recorders.** activity-stream vs
  storage-object vs tensor is a RECORDER distinction, **not a SOURCE distinction** —
  the same delta drives all of them. This is the single most clarifying realization:
  it collapses three apparent subsystems into one source feeding N recorders.

### Edges
- **Edge = wrangler.** The coupling between a collector emission and a recorder.
  Strategies already exist along a coupling axis (`transport/wranglers.py`):
  `Direct` (in-process, same moment), `Batch` (file handoff, decoupled in time —
  the Indaleko arangoimport fan-out model), `Queued` (in-process producer/consumer).

### Compositions
- **Fan-out** = one emission → N edges → N recorders. Demonstrated: storage +
  activity legs from one cloud delta.
- **Feedback edge** = a recorder/monitor leg whose output re-enters a collector via
  `recollect_one`, whose result updates a destination. Demonstrated depth-1.

---

## The keystone: delivery and depth are EDGE KNOBS, not topology

The shape of the graph is **invariant** under two choices that *feel* like different
architectures but are not:

| Knob | Options | What it changes | What it does NOT change |
|---|---|---|---|
| **Delivery strategy** | webhook ↔ polling | WHEN the edge fires | the graph shape |
| **Re-collect depth** | one-shot ↔ recursive | HOW DEEP a re-enter goes | the graph shape |
| **Coupling** | Direct ↔ Batch ↔ Queued | WHERE/WHEN data is handed off | the graph shape |

This is why the fear of "the cyclic feedback shape" was a phantom (flinch log #1):
the feedback edge is a polling loop with a cursor; webhooks are the same edge with a
different delivery knob. Build the simplest knob first (polling, one-shot, Direct);
the others are knob-turns on the same proven topology, not rewrites.

### Termination
A feedback edge terminates when (a) the delta set is finite (the cursor exhausts)
and (b) the re-collect emits no new delta. **Depth-1 (one-shot re-collect) gives
both structurally** — the cycle cannot grow. Recursive depth needs a
`(st_dev,st_ino)`-style visited-guard to terminate; that is the explicit follow-on,
deferred not lost. The synthetic collector makes termination PROVABLE (seeded,
deterministic), and the Codex-authored test counts cycles exactly — termination
proven, not "didn't hang this run."

---

## What this is NOT yet (honest scope)

- One real provider (GDrive/OneDrive, with OAuth) has not confirmed the vocabulary
  needs no reshaping. This is one synthetic + two in-repo precedents. The vocabulary
  is strong but graduates to canonical only when a SECOND real cloud provider lands
  without forcing a change. (That is itself the second-instance rule, applied to
  this very doc.)
- Webhook/ngrok push reception, recursive re-collect depth, and the Batch
  (arangoimport) coupling for the Objects fan-out are all real follow-ons.

---

## One-line summary

A node is a collector (emits) or a recorder (consumes-and-writes-one-destination);
an edge is a wrangler; fan-out is one emission to many recorders; feedback is a
recorder leg re-entering a collector; and webhook-vs-polling, one-shot-vs-recursive,
Direct-vs-Batch are all EDGE KNOBS that leave the graph shape invariant.
