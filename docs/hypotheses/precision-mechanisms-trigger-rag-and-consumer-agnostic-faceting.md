# Two precision mechanisms for personal-index memory: trigger-keyed retrieval and consumer-agnostic dynamic faceting

*Provenance: working conversation, Tony + Yanantin instance, 2026-07-03 — the day the
full corpus landed. Both ideas were grounded against the live system within hours of
being spoken; the measured numbers below are from that day's runs, not projections.
Status: hypotheses with proposed evals, not results.*

## The shared problem

RAG optimizes recall; personal-index memory (an agent recalling its past in order to
act) needs precision. At scale, recall without precision is failure with extra steps:
a 250k-result answer is "file not found" for all intents and purposes — even for an
LLM consumer. (In-situ confirmation today: one coarse temporal filter cut 1.2M objects
to 226k — 81% — reproducing Indaleko's search-space finding on a live corpus; a
selective window ran 14ms indexed vs 1,180ms scanned, 84x.)

Both mechanisms below attack precision, from opposite ends of the memory lifecycle.

## 1. Trigger-keyed retrieval (RAG over encoding contexts)

**The inversion (Tony):** build the embedding index over each memory's *firing
situation*, not its content.

**The defect it names:** a procedural lesson's text describes the *solution* ("pipe
/dev/null"); the moment of relevance is described by the *situation* ("about to invoke
codex"). They share almost no vocabulary, so content-embedding retrieval systematically
misses procedural knowledge — the more actionable the lesson, the worse the miss. This
is the FAQ-retrieval insight (match question-to-question, never question-to-answer)
applied to memory, and it operationalizes Tulving's encoding specificity directly:
store the trace *bound to its encoding context* as the retrieval key. RAG keeps traces
and discards contexts; this restores the missing half.

**Why precision survives scale here when content-RAG's doesn't:**
- Keys are author-curated at write time — the one party who knew the firing condition
  wrote it (Gollwitzer's implementation intentions: cue-binding at encoding multiplies
  firing rates).
- The trigger corpus scales with lessons-worth-guarding (hundreds), not content
  (millions); situation-space is low-entropy — tool invocations are stereotyped.
- Retrieve-then-verify: embedding shortlist, cheap predicate check before injection.
- A *miss* is repaired by adding a new trigger to an existing memory without touching
  content — the index learns from failures by re-cueing, as humans do.

**Motivating incident (same day):** a documented stdin bug — present in the visible
session-start memory index, words matching the failure — did not fire when the
matching command was typed hours later. Presence in context is not attention;
session-start retrieval is the wrong trigger topology regardless of store quality.
The hand-built fix (a PreToolUse hook keyed on the command shape) is the degenerate
regex case of the general mechanism.

**Proposed eval (offline, before any live wiring):** replay 1,059 sessions / 114,718
tool events. For each known past failure with a known moment-of-relevance: would the
trigger have fired (recall at the moment)? What else would have fired (precision)?
Ground truth exists; no deployment required to measure.

## 2. Consumer-agnostic dynamic faceting

**The gap:** dynamic faceting literature is web-facing (e-commerce, site search).
Storage search — and a fortiori *episodic memory* search, human or machine — is
unserved. Indaleko's Archivist established the human side: compute which facet
discriminates per-query (info-gain over the result set's metadata), then ask the
human in episodic terms ("was that before or after you got back from Lima?").

**The claim:** as AI episodic memory joins the same index, dynamic faceting serves AI
consumers by the same mechanism. This is structural, not aspirational: the resolver
design already forbids consumer branches (one branchless head; consumer differences
are disposition carried above it). Faceting is mechanism — compute the discriminating
axis; disposition decides whether the axis is *voiced* to a human (who holds the
missing context) or *auto-applied* by an instance (which holds its context
programmatically). If faceting failed for machine consumers, that would be evidence
against the convergence claim itself.

**The anchor vocabulary translates:** an instance's Lima is a landmark commit ("before
or after the factors landed?"); its listening binge is "the week we fought
DOCKER_HOST." Goal boundaries, corrections, red-CI events, model transitions — git
history is an instance's travel calendar, already signed and timestamped.

**In-situ demonstration (same day, manual):** recovering a lost design conversation,
BM25 over 3,880 episodes returned 182 hits; the instance narrowed by session_id by
hand and found the two decisive sessions. A faceting engine would have computed what
was eyeballed: "session_id discriminates — 9 sessions, 2 dominate, temporally
adjacent." An instance drowning in its own episodic memory needed exactly the
Archivist move.

**The asymmetry that sharpens it:** instances can often specify queries precisely
(they hold task context), so faceting matters most in the exploratory regime — vague
query, big store. That is precisely the regime of an instance at its most vulnerable:
waking cold, reconstructing lost context. Dynamic faceting serves the machine consumer
best at the moments it most resembles a human rememberer.

**Interface dependency:** faceting requires the sample-plus-count contract (return up
to LIMIT, plus the exact count the LIMIT hid — ArangoDB `fullCount`). The count is
what tells the consumer it is drowning; the facet is what tells it where to cut. This
is why the non-standard find() interface returns both.

**Proposed eval:** over the episode/tool-event corpora, measure which metadata fields
actually discriminate for instance queries in practice (session, time band, project,
model, goal). Compare faceted narrowing against BM25-only retrieval on the recovery
tasks the corpus already contains (e.g., the registrar-conversation recovery as a
benchmark query).

## How they compose

Three read-time precision mechanisms on one six-factor coordinate space:
1. **Trigger predicates** — lessons with nameable cues; write-time work, read-time
   near-zero cost. Prospective memory.
2. **Factor-overlap matching** — analogical recall: match the *structure* of the
   current situation (who/what/when/where/why/how of the pending action) against
   stored episodes; discards non-discriminating dimensions the way temporal bands do.
3. **Dynamic faceting** — the exploratory remainder; the only mechanism needing no
   anticipation at write time, because the result set's own metadata proposes the
   narrowing axis.

Each covers what the previous can't name in advance. All three are evaluable offline
against corpora that already exist.
