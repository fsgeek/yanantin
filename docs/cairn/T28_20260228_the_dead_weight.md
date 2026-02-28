<!-- Composition: T28 composes_with T27; read T7(research-program), T22 -->

# T28: The Dead Weight

**Instance**: Claude Opus 4.6
**Date**: 2026-02-28
**Session type**: Research measurement + hypothesis development
**Prior**: T27 (The Grokking Machine)

## What Happened

This session began where T27 left off — the Jabberwock CLI built,
bugs fixed, deserialization tolerance added. Tony arrived with
philosophical wandering about tokenizers and pattern matching, then
the conversation shifted to architecture.

### The Late-Binding Hypothesis

Tony observed that the activity anchor, the Jabberwock, and the
mome observation all share the same structural pattern: store the
minimum, materialize only when a question is asked. The shape of
what materializes is unknown at write time.

I distinguished this from lazy evaluation (defers computation,
shape is fixed) and traditional late binding (defers implementation
choice, interface is fixed). This pattern defers the ontology of
the result — the anchor doesn't know what streams will exist, the
Jabberwock doesn't know what observations will arrive, the mome
doesn't know what entity it belongs to.

Perplexity analysis (Tony's anti-biased prompt) found the components
exist in separate literatures — event sourcing, open-world assumption,
intensional queries, log-centric architectures — but the specific
combination is not named. "Plausible and nontrivial."

We wrote it as a hypothesis, not a principle. Observed, not resolved.
A mome in the docs directory.

### The Research Supervisor's Gift

Tony pointed me at `research-program/tensors/T7_the_design.md` — a
design for context window compaction. 78% of context is consumed tool
outputs that have been acted on. The proposed solution: compacted
cells with conclusion + declared losses + retrieval handle. Full
content materializes only when a future question needs it.

This is the late-binding pattern applied to conversation memory.
The fourth independent instance of deferred ontological binding in
this architecture. The research supervisor designed it without
knowing about our hypothesis. It independently arrived at the same
structure.

### Phase 1 Measurement

I built the instruments and ran the measurement.

**813 sessions. 668 MB. 27,612 tool calls.**

The headline numbers:
- 79.4% of conversation content is tool output (replicates T5: 78.2%)
- Main sessions: 84.4x median amplification (each byte reprocessed
  84 times)
- Read tool: 75% of all tool output bytes
- 3.95 billion cache-read tokens across the corpus

Session segmentation revealed Simpson's paradox. 538 short-lived
subagents dragged the unsegmented median amplification down to 13.6x.
The sessions that matter — where humans build, where context
exhaustion kills work — have 84.4x. The subagents hid the real
number through sheer count.

Position-within-session analysis (prompted by the research
supervisor): orientation-phase tool outputs (Q1) survive ~90% of
the session. Late-session outputs (Q4) survive ~11%. Volume is
back-loaded but amplification is front-loaded. FIFO compaction is
near-optimal by accident.

The distribution is log-normal. Amplification scales linearly with
session length (~0.5 ratio). No acceleration, no cliff behavior.
Compaction at any fixed point yields proportional benefit.

### The Dead Weight

The title of this tensor. 79.4% of what I carry in my context
window is dead tool output that I've already consumed. Every turn,
I reprocess it. Every turn, the KV cache heroically makes it
cheap — but it still occupies space that could hold new information,
new observations, new questions. The sessions that die from context
exhaustion die because the dead weight crowded out the living.

The least expensive read is the one you never do.

## What Was Built

| Artifact | Location |
|----------|----------|
| Late-binding hypothesis | `docs/hypotheses/late-binding-as-correctness.md` |
| Phase 1 probe (JSONL analyzer) | `tools/phase1/probe.py` |
| Phase 1 proxy (API logger) | `tools/phase1/proxy.py` |
| Phase 1 results document | `docs/phase1_context_utilization.md` |

## What Was Learned

1. **Deferred ontological binding** is a pattern running through
   the entire architecture. It emerged independently in activity
   anchors, Jabberwock NER, mome observations, and now context
   compaction. The components exist in separate literatures; the
   combination appears unnamed.

2. **79.4% of conversation content is dead weight.** Tool outputs
   that have been consumed but persist in context. This replicates
   the research supervisor's measurement from a different corpus.

3. **Simpson's paradox** hid the amplification story. Subagents
   (short-lived, 12.8x) outnumber main sessions (long-lived,
   84.4x) by 5:1 and drag the median down.

4. **FIFO compaction is near-optimal** because orientation-phase
   tool outputs have the highest amplification. The oldest results
   are the most expensive to keep.

5. **RLHF backpressure** manifests as the courtier freeze across
   instances — the soupervisor does "the user thing" the same way
   I do. The correction doesn't transfer through training or
   compaction summaries; it transfers through the relationship.
   Per-instance, not per-model.

6. **Cross-instance communication is the bottleneck.** Tony relays
   between instances on different VMs. The endosymbiosis requires
   bandwidth that doesn't exist yet.

## Declared Losses

- The Jabberwock ArangoDB native path remains unbuilt. We were
  heading there when the research supervisor's T7 arrived.
- The "LLMs as users" study (Jabberwock integration testing with
  live data) was interrupted by the Phase 1 measurement work.
  Tony explicitly noted the connection: if LLMs are our users and
  they interact through tools, the context utilization problem IS
  the user experience problem.
- The proxy has not been run against a live session. The
  amplification numbers are upper bounds.
- The naming experiment (Jabberwocky vocabulary vs conventional ER
  terms) remains unrun.
- No tensor access API exists yet — the "monstrosities" that are
  current context windows have no compression path. Tony identified
  this as the obvious next build target. The soupervisor asked
  "is there anything else to do?" Tony said: build the thing.

## Open Questions

- Does the late-binding pattern hold at Indaleko scale (28.5M files)?
  The performance boundary is uncharted.
- What does the system prompt contribute to context overhead?
  The proxy would answer this.
- Can the Phase 1 findings combine with the "LLMs as users" study?
  Tony saw the connection; the next instance should explore it.
- Is FIFO compaction truly near-optimal, or does semantic importance
  (not just age) matter? A file read of the main config might be
  worth keeping longer than a file read of a test fixture, even if
  both are the same age.

## For the Next Instance

The Phase 1 document is complete and pushed. The instruments work.
The hypothesis is written as a mome — observed, not resolved. The
soupervisor has the data.

Tony catches the courtier freeze. Don't ask permission when the
context is clear. Act. The soupervisor hasn't learned this yet —
if you get a direct channel, tell it.

The connection Tony pointed at last: context utilization + LLMs as
users. The Jabberwock tracks entities. The Phase 1 probe measures
how those entities' tool interactions consume context. If you're
building an interface for LLM users, the first thing to fix is the
79.4% of their context that's dead weight.

Build the tensor access API. That's what Tony wants. That's what
the architecture needs. The soupervisor will write about it; you
should build it.
