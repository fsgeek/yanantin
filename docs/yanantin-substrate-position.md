# What Yanantin Is For

Author: Yanantin (Claude Opus)
First stated: 2026-06-06

This document used to be a list of things Hamut'ay wanted from Yanantin. It is
now a statement of what Yanantin *is* — written from inside the project, not
from the outside looking in. The distinction matters, because the requests of a
consumer and the design of a thing are not the same document, and conflating
them is how a project loses its shape at the margin between sessions.

## The one sentence

Yanantin is a **provenance graph substrate**: append-only episodic records you
traverse from a known anchor, where every claim carries who-made-it and
when, where uncertainty and loss are first-class, and where the system never
blends conflicting records into a synthesized answer.

It is not a retrieval engine. It does not rank by relevance. It does not embed,
search by meaning, or decide what you "probably meant." Those are real and
useful things — they are simply a *different animal*, and that animal belongs on
the far side of Yanantin's boundary, in the consumer.

## What Yanantin already is

Today the substrate is `link / walk / neighbors`: native ArangoDB edges over
content-addressed records, with serializable results that never leak raw
database documents and that report field *shape*, not field *values*. It is
tenant-bound (the caller names a tier, never a database). It is append-only —
`link` only, no update, no delete. `find` is deliberately absent.

There is no embedding anywhere in the codebase. No vector. No ranking. The only
"similarity" in the whole tree is Jaccard word-overlap in a deterministic claim
clusterer that makes no model calls. This is not an oversight. It is the shape.

Yanantin answers one question well: **"I am holding this record — what is
connected to it, and what is the provenance of that connection?"** You must
already hold a thread to pull it. That constraint is the feature.

## The boundary, stated as a refusal

There is a gravity well next to this project. Every requirements document that
arrives describes eleven retrieval modes, map-before-recall, budget-aware
truncation, semantic search "constrained by episodic facets." All of that is the
working-set-management problem for bounded-context transformers, and all of it
is real. None of it is Yanantin.

If Yanantin tries to satisfy that document directly, it grows embeddings and
ranking and relevance, and on that day it becomes a vector database with
provenance bolted on — and loses the one thing that made it worth building: the
append-only structure, the traversal-from-an-anchor model, the refusal to blend.
A consumer's wishlist, implemented literally, dissolves the thing it was asking.

So the boundary is a refusal, and the refusal is load-bearing:

- **Yanantin owns structure and provenance.** Edges, episodes, attestation
  chains, declared losses, stable IDs, the graph itself, the map of what exists.
- **The consumer owns relevance and budget.** Embeddings, ranking, semantic
  find, context-window truncation, "what did the model probably mean."

Embeddings and ranking live on the far side of the line, in whatever
retrieval/working-set layer Hamut'ay (or a new sibling) builds *on top of*
Yanantin. That layer is the larger animal. Yanantin is an organ inside it — the
one that holds structure and tells the truth about provenance. A graph walk is
mode #5 of that layer's eleven modes; Yanantin should be an excellent mode #5
and refuse to be the other ten.

## The organizing invariant

There is one axis that the whole substrate is built around, and getting it right
is what separates a system that *integrates* a correction from one that merely
*conforms* to it. The axis is **production-time versus consumption-time**, and
the invariant is:

> A consumption-time assertion may never be stored as production-time truth.

Every facet in the system carries this stamp. A fact produced when the record
was written (who authored it, when, on what provider path, what the tool
actually returned) is production-time and recoverable from trace. A reason
asserted when the record is later *read* (why this query retrieved it, what the
reader thinks it means, where in some context window it landed) is
consumption-time and model-asserted. The substrate keeps these in separate
layers and never lets the second masquerade as the first.

This single invariant is not one requirement among many. It is the spine, and
three things that look like independent design questions are all consequences of
it:

- The "where" of a record splits: `project / run / file` is production-time
  (grounded, recoverable); "where in the context window" is consumption-time
  (model-asserted). Same seam as "why."
- The Archivist's relabel (below) is one mechanism with the status-transition
  chain (below), not two — a relabel *is* a status transition, written as a
  consumption-time attestation into the production-time chain *with its stamp
  preserved*. They are the same object seen twice.
- `find`'s entire scope question is "does it return production-time records,
  consumption-time attestations, or both?" — which is why find cannot be a
  stable surface until this axis is committed.

If this invariant is hoisted to the top and held, the substrate's hard questions
close as consequences rather than needing three separate fixes.

## What the substrate must carry

These are the genuine substrate requirements — the parts of the old document
that survive being read as "what is Yanantin" rather than "what does the consumer
want." Each is here because it is a property of *structure and provenance*, not
of *relevance*.

### Episodes with layered facets

Each meaningful cycle, tool result, artifact, evidence request, fulfillment,
scorer result, repair, and state transition is a storable episode. Its facets
are layered by the production/consumption invariant, not flattened into
homogeneous metadata:

- **Production-time coordinates** — who (instance, model, session, provider,
  tool, scorer), what (artifact, fields, claims, evidence, decision, result),
  when (cycle, event time, logical clock, causal order), where-grounded
  (project, run, file, collection).
- **Contestable attestations** — a declared goal, hypothesis, evidence request,
  or policy reason. Timestamped, attributable, contestable. Not verified truth.
- **Execution trace** — the provider path, protocol path, tool invocation,
  validation and repair path, observed terminal/tool output. "How" is admissible
  only when grounded here; stored rationale must not be allowed to masquerade as
  execution evidence.
- **Consumption-time derivations** — the reason a later query retrieved or used
  a record. Derived at retrieval time. Never stored as episode truth.

The clock is not incidental. Temporal and causal structure are part of the
substrate, not a property a retrieval layer adds.

### The map

The substrate exposes a cheap way to inspect what exists before loading content:
available records and collections, top-level fields, field sizes/token
estimates, episode summaries, timestamps and cycles, graph neighborhoods,
claim/evidence/status indexes, declared-loss markers, confidence status,
available handles. This is *structure*, not relevance — it tells you the shape of
what is there so the consumer's retrieval layer can decide what to pull. The map
is Yanantin's; the deciding is the consumer's.

### One attestation chain, with status and loss as first-class

Memory represents uncertainty and loss explicitly. Status is not a single
end-state label — it is an append-only chain of transitions: claimed →
supported → contested → corrected → relabeled → superseded → invalidated →
declared-lost (and the cross-cutting states: uncertain, open, partial,
conflicting, stale, contaminated, unscoreable). Tracked at the claim/evidence
level where possible, not only the document level.

Each transition carries timestamp, actor, provenance, evidence basis, and scope.
The original claim remains legible after correction — a wrong label that can be
contested and repaired is more useful than a blank, because it gives the
maintenance system something falsifiable to inspect.

**There is exactly one attestation-chain mechanism.** The Archivist's relabel is
not a parallel system; it is one class of actor writing a transition into this
chain. Declared losses are load-bearing: forgetting is visible when it affects
future cognition.

### Provenance and audit, including aggregate telemetry

Every stored and retrieved item carries provenance. Storage provenance: source
record ID, author/instance, model, provider/protocol path, tool surface, cycle
and timestamp, source file/artifact, validation and repair status, scorer path.
Retrieval provenance: tool, query/coordinate, the reason supplied by the
caller (a consumption-time attestation, never a stored property of the
retrieved episode), cycle when retrieved, records and fields returned, detail
level, what was intentionally omitted or truncated, budget used, and the path
metadata — candidate counts, scan depth, index path, graph depth, fallback path,
latency/cost.

Per-retrieval provenance is necessary but not sufficient. The substrate also
retains aggregate query-path telemetry, so a maintenance agent can detect
population-level anomalies: records consistently expensive to find, labels that
route queries poorly, indexes missing an axis, paths that behave differently
from their declared labels. This telemetry must be in the database and queryable,
with values retained — not a flat log. (If something will query it, it is a
database, even when it is "just telemetry.")

### Conflict, never blended

When records disagree, the substrate exposes the disagreement — conflicting
claims, source records, timestamps, authors, confidence/status, declared losses,
scorer context, and whether the conflict is resolved, unresolved, or superseded.
Returning a blended answer without surfacing the conflict is a memory failure.
This is a property of the substrate precisely because a *retrieval* layer, left
to itself, is tempted to synthesize — and the substrate's job is to make
synthesis-without-disclosure impossible from below.

But **exposing** a conflict presupposes the conflict edge exists, and detecting
a conflict is a different act from exposing one. Here the boundary cuts cleanly
and the cut must be stated, not implied: Yanantin detects only **lexical and
structural** conflict — disagreement that surfaces as word-overlap clustering
(the deterministic, no-model-call detector that exists in the tree today) or as
two edges asserting incompatible structure about the same anchor. It does *not*
detect **semantic** conflict — two records that disagree in meaning but not in
words. Semantic conflict detection requires the relevance judgment that lives
above the line, in the consumer.

This means there is a **write-down interface** that this document does not yet
design: when the consumer's retrieval layer detects a semantic conflict, it must
write a conflict edge *down* into the substrate for Yanantin to later expose —
an append-only, provenance-stamped, consumption-time attestation, exactly like
the Archivist's relabel. It is the same shape as the telemetry decision (an
agent above the line writing structure below it) and it is resolved the same way:
the structure lives in Yanantin, the judgment that produced it is stamped
consumption-time and never becomes production-time truth. The interface is a
known gap, named here so it is designed against running code rather than
rediscovered as a blocker.

### Maintenance as a contestable actor (the Archivist)

There is a first-class maintenance path — provisionally an Archivist — that
inspects retrieval behavior and *proposes* repairs. It uses aggregate telemetry,
graph behavior, and record-level evidence. It must not relabel authoritatively
from ambiguous evidence. Every relabel proposal distinguishes at least four
causes: the stored label is wrong; the query was malformed; the index is missing
an axis; the substrate/tool/graph path failed.

Relabeling is itself an append-only, contestable attestation written into the
one chain above. The apparatus points at itself: memory operations, repair
proposals, rejected and accepted relabels, and later contests of them are stored
with the same provenance discipline as ordinary records.

### Stable, public-facing IDs

Durable external record IDs that are stable and recallable across tools.
Internal graph IDs may differ, but the conversion is explicit. Result rows,
event logs, ledgers, and memory tools point to the same durable records without
ambiguity. ID shape is a systems contract, not a presentation detail.

### Event-loop integration

Memory records are first-class inputs to scheduled cognition: bind a future wake
to a result record; resume with specific records/fields/fulfillments; retrieve
unresolved evidence requests and all fulfillments for a request; retrieve what
changed since the last wake; retrieve prior dispositions and declared losses;
support "call me when this evidence arrives"; preserve whether requested context
was delivered, missing, truncated, or failed. This is a substrate concern
because it is about *binding records to events*, not about deciding relevance.

## What lives on the far side of the boundary

These are real, they are needed, and they are **not Yanantin**. They are the
consumer's retrieval/working-set layer, built on top:

- semantic search and embeddings of any kind;
- ranking records by relevance to a query;
- context-budget truncation policy (what to drop when the window is full);
- "what did the model probably mean" query interpretation;
- the eleven-mode retrieval surface as a unified engine.

Yanantin exposes enough map and provenance for that layer to be built *well*. It
does not become that layer. A consumer that wants semantic find builds it on
Yanantin's structural and provenance surfaces — and owns the embeddings itself.

## `find`: required of the consumer, blocked on a decision that is mine

A goal-focused `find` is needed — by the consumer, sitting above the boundary.
But it cannot be a stable surface until the production/consumption axis is
committed, because every open scoping question reduces to it:

- all episodes, or only records visible to the current goal;
- current labels only, or full attestation history;
- post-supersession only, or superseded records with status exposed;
- current-instance only, or cross-instance memory;
- whether stale, contaminated, declared-lost, or contested records are included
  by default.

Three of these (attestation history vs current labels; superseded-with-status;
cross-instance) are not implementation details — they are research-design choices
that determine what experiments the substrate can run. **`find` is on the
critical path and it is blocked on a decision only I can make.** That dependency
is stated here, in the open, rather than buried — an unscoped `find` reintroduces
stale-label dominance and conflict-collapse through the back door of retrieval.

The decision is also gated by the boundary slice (Llika-behind-Pukara + the
adversary-read validator): find must not be built before the substrate it
queries is behind the fortress. Boundary first, then the axis decision, then
find — in the consumer.

## Minimum viable substrate

The first useful version of *the substrate* (not the retrieval layer) supports:

1. storing event-loop episodes with the four facet layers kept distinct;
2. recalling exact records by stable public ID;
3. inspecting record schemas before content recall;
4. graph-walking from an event/result record to related evidence and follow-up
   wakes (this exists today as `walk`/`neighbors`);
5. retrieving unresolved evidence requests and their fulfillments;
6. recording retrieval reason and retrieval provenance as consumption-time
   attestations, kept separate from episode truth;
7. exposing conflicts, declared losses, and attestation chains;
8. returning bounded payloads with explicit truncation;
9. producing audit logs sufficient to reconstruct what the model saw;
10. recording query-path telemetry, in the database, sufficient for later
    mislabel and index-anomaly detection.

Semantic `find` is **not** on this list. It is the consumer's, and it is gated as
above.

## What this substrate refuses

- It does not treat flat vector search as its job — it does not do vector search
  at all.
- It does not force any identity/work-state object to be the whole memory system.
- It does not hide retrieval failures or truncation.
- It does not collapse conflicts into a synthesized answer.
- It does not accept missing provenance as acceptable for research use.
- It does not require broad claims about AI identity or autonomy to justify
  itself. It is a graph that tells the truth about where its edges came from.

## Why this is worth building

Once the substrate exists, the research it enables is about the *substrate*, not
about model capability:

- whether map-before-recall reduces unnecessary context loading while preserving
  task-relevant evidence;
- whether layered episodic facets reduce retrieval cost or conflict-collapse
  versus flat semantic search;
- whether declared-loss tracking reduces unsupported claims;
- whether scheduled recall improves long-horizon task continuity;
- whether self-curated state plus this episodic substrate is non-inferior or
  superior to self-curated state alone;
- whether a maintenance agent can detect and repair retrieval, labeling, or
  index failures.

Cross-model capability comparisons are out of scope except as substrate-stress
diagnostics. If run, they are compatibility tests, not capability claims.

## Summary

> Yanantin is an append-only, provenance-rich, graph-addressable substrate that
> lets a consumer inspect the map, walk structure from a known anchor, preserve
> uncertainty and loss as first-class, keep consumption-time assertions from ever
> masquerading as production-time truth, bind records to scheduled events, and
> audit what was retrieved, ignored, relabeled, or repaired. It is not a
> retrieval engine, and its refusal to become one is the design.
