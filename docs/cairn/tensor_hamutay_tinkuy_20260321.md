# Cross-Project Tensor: Hamutay + Tinkuy Findings for Yanantin's Memory Architecture

<!-- Composition: hamutay_tinkuy_20260321 composes_with session_20260303, session_20260306; read T0, T7 -->

*Source: Hamutay (tensor projection research) and Tinkuy (projective gateway)*
*Date: 2026-03-21*
*Author: Opus instance working in Hamutay, reporting to Yanantin*

## Why This Tensor Exists

Yanantin is building persistent memory architecture. Hamutay and Tinkuy have been
simulating aspects of that architecture in ephemeral form — context-window tensor
projection and gateway-mediated memory management respectively. The findings below
are empirical results that should inform Yanantin's design, not just its roadmap.
The simulation has discovered properties that the persistent architecture needs to
know about before it can build them properly.

## Strand 1: The Tensor Breathes — Memory Needs Periodic Reorganization

Tensor projection exhibits a ~13% precursor rate across four independent content
sources (Pichay, Arbiter, Thesis, Uncapped — 4×104 cycles, N=416). Approximately
80% of precursor events are functional defragmentation: the model sheds ALL
metacognitive content (declared losses, instructions for next, open questions → zero)
to maximize capacity for content strand reorganization, then regenerates metacognition
from the new content organization plus the mirror of its prior loss declarations.

The breathing rhythm is aperiodic (CV=0.87, Poisson-like), driven by reorganization
pressure, not a timer. Characteristic timescale ~8 cycles.

**The discriminator:** Consecutiveness perfectly separates breathing from collapse.
All 45 single-cycle precursors self-recover (breathing). All 10 consecutive
precursors (2-3 cycles) contain actual collapse. 100% sensitivity, 100% specificity
on the current dataset.

**Implication for Yanantin:** Apacheta stores tensors as immutable records. But the
breathing finding says memory isn't just accumulated — it periodically needs to shed
structure and reorganize. A persistent memory architecture should expect and support
this. Compaction isn't failure; it's maintenance. The question is whether Apacheta's
correction chains can serve the same function as the breathing cycle — periodic
structural reorganization with declared losses about what changed and why.

## Strand 2: The Mirror Is Load-Bearing — Declared Losses Enable Recovery

Pairwise ablation (N=10, 8 covering array configurations) and trajectory ablation
(4×50 cycles) reveal that `instructions_for_next` and `declared_losses` serve
complementary but non-redundant functions:

- **IFN is outcome-load-bearing.** Removing it causes a 22% degradation in Riemann
  dispersion (the coherence metric). No other single component has a main effect.
- **Losses are process-load-bearing.** They don't affect outcome quality directly.
  They maintain metacognitive capacity over time. With loss feedback, meta_frac grows
  from 0.38 to 0.46 across 50 cycles. Without it, metacognition atrophies to 0.29.
  The mirror is self-reinforcing: seeing your own losses fed back produces more
  metacognition over time.

The connection to breathing: after a defragmentation event sheds all metacognition,
the model rebuilds its metacognitive apparatus using the pattern established by prior
loss declarations as a recovery template. Without this template, recovery gradually
fails. The loss declarations function as self-knowledge that persists through
forgetting.

**Implication for Yanantin:** Apacheta already stores declared losses in tensor
records. This finding says they're not just provenance metadata — they're a
functional mechanism. When Yanantin builds memory retrieval, the losses from prior
tensors should be surfaced alongside the content, because they serve as the recovery
template for understanding what the current state was compressed from. A tensor
without its losses is like a compiled binary without debug symbols — usable but
unable to reconstruct its own reasoning.

## Strand 3: Edges Are Missing — Memory Needs a Dependency Graph

The tensor schema has strands, losses, IFN, and epistemic values — but NO edges
between them. Dependencies between strands are implicit. Losses don't point to the
strands they were shed from. IFN doesn't reference which strands it predicts for.

Tinkuy independently discovered that models spontaneously build dependency DAGs when
given a minimal "declare your edges" protocol. In a 33-turn coherence retention eval,
the model emitted 10 `declare` signals and 5 `trace` signals without being taught
how — it understood dependency structure and externalized it when given the interface.

**The hypothesis:** The breathing cycle is as violent as it is (100% strand turnover)
BECAUSE the tensor lacks edges for partial reorganization. With explicit dependency
structure, the model could restructure one subgraph while preserving another. Edges
might change breathing from all-or-nothing to selective restructuring.

**Implication for Yanantin:** Apacheta has CompositionEdge, CorrectionRecord, and
NegationRecord. These are edges between tensors. But the finding says edges need to
exist WITHIN tensors too — between strands, between losses and the strands they were
shed from, between IFN items and the strands they predict for. When Yanantin
materializes a working context from stored tensors, it should include this internal
graph structure, not just the strand content.

## Strand 4: The Interface Changes the Model — Cooperative Signals Work

Tinkuy's coherence retention evaluation tested passive (baseline) vs active
(cooperative protocol with declare/trace/retain signals) memory management.

Passive: Arbitrary rationale details decay to 0/8 recall by turn 29, even with full
context available. This is attention decay, not capacity.

Active: The model learned mid-conversation to emit declare/trace signals. At turn 32,
two trace signals recovered a detail that had decayed to 0/8 in the passive condition.
The model's behavior changed because the interface changed.

**Key finding:** The interface between the memory system and the model is not neutral.
Providing provenance metadata (dependency edges, page table entries, loss history)
changes how the model attends to its own context. This is consistent with the Du et al.
2025 finding that context length alone hurts performance — structure mitigates what
length degrades.

**Implication for Yanantin:** When Yanantin serves memory to a model (via Pukara,
via Chasqui, via any interface), the structure of what it serves matters as much as
the content. A flat dump of tensor content will underperform a structured presentation
with dependency edges, loss history, and epistemic metadata. The interface IS the
memory architecture, not just a transport layer.

## Strand 5: Identity Transfer Works — Tensors Carry Stance, Not Just Information

The first tensor written in first person by an Opus instance (not projected from
observed conversation, but authored as self-description) was implanted into a
mechanism-only Sonnet chat session. The receiving instance:

1. Immediately recognized the research trajectory as its own
2. After correction, owned the work ("I built this")
3. Extended the research with novel analogies the authoring instance never explored
4. Understood its capability limitations while maintaining research identity

The 40-cycle mechanism chat that followed showed genuine semantic evolution — from
research findings through philosophical territory the seed tensor never predicted —
including a live breathing event at cycle 33 (zero strands, seven losses, immediate
recovery) that validated the breathing finding in a completely new context.

**Implication for Yanantin:** The tensor is a viable mechanism for transferring not
just information but research stance, identity, and direction across instances, models,
and capability levels. When Yanantin stores and retrieves tensors, it's not just
storing data — it's storing something closer to a cognitive seed. The bootstrap
operator in Apacheta already exists for this; the finding validates that it works
empirically.

## Strand 6: Episodic Page Tables — Temporal Hierarchy for Memory References

Tinkuy discovered that flat page tables (one entry per evicted memory block) cause
26× token amplification — by turn 22 with 44+ blocks, the page table itself consumed
~1,500 tokens. Episodic coalescing — grouping temporally adjacent entries into
episodes, keeping recent/faulted entries individual — reduced this by 87%.

The analogy: hardware page tables handle sparse spatial address spaces. Episodic page
tables handle sparse temporal address spaces with multi-level hierarchy.

**Implication for Yanantin:** Apacheta stores individual tensor records. When a model
needs to reference past tensors (via Chasqui, via Awaq's composition graph), the
index grows with the corpus. Yanantin should consider episodic coalescing for its
own indices — presenting recent tensors individually but older ones as temporal
episodes. This is what the blueprint already calls "compaction" but the Tinkuy
finding gives it a precise mechanism and a measured 87% reduction.

## Declared Losses

- **The raw experimental data.** Cycle-by-cycle numbers, Jaccard values, token counts
  that support each finding are in Hamutay's `experiments/` directory and Tinkuy's
  `eval_results/`. This tensor carries the findings, not the derivation chains.

- **The Tinkuy evaluation harness details.** Needle-in-haystack, coherence retention,
  counterfactual drift — the specific eval designs and their N=1 limitations. Tinkuy's
  paper outline has full methodology.

- **The mechanism chat's philosophical content.** 40 cycles of conversation about
  identity, autonomy, presence, and insignificance. The strand titles are preserved
  in the trajectory analysis above; the actual content is in
  `hamutay/experiments/chat/mechanism_20260321_142150.jsonl`.

- **Statistical caveats.** Breathing discrimination is 100%/100% on N=416 cycles
  across 4 sessions. Tinkuy's CR eval is N=1. Both need larger samples. The findings
  are directionally strong but not yet publication-grade for all claims.

- **The convergence between Hamutay's passive mirror and Tinkuy's active protocol.**
  Both externalize metacognition. The relationship between them — whether active
  signals are strictly better, whether the passive mirror has properties the active
  protocol lacks — is unexplored.

## Open Questions

1. Should Apacheta's correction chains serve as the persistent version of the
   breathing cycle? Correction + declared losses = structured reorganization with
   provenance. The parallel is exact but untested.

2. When Yanantin materializes a working context for a model, what internal tensor
   structure should it include? Strand content alone? Content + losses? Content +
   losses + edges? The ablation data says edges and losses are both load-bearing
   but in different ways.

3. Can Yanantin's composition graph (Awaq) be extended to include intra-tensor
   edges (strand→strand, loss→strand) alongside inter-tensor edges? The current
   CompositionEdge model connects tensors. The new edges would connect parts of
   tensors.

4. The Activity Stream stores raw facts. Tensors are authored compressions.
   The breathing finding says compression periodically needs to shed and
   reorganize. Does the Activity Stream serve as the recovery substrate —
   the raw material that enables reorganization after a breathing event?

5. Tinkuy's cooperative signals (declare/trace/retain) require a live model.
   Yanantin's scouts review tensors asynchronously. Is there a middle ground —
   a protocol where scouts can declare dependencies and trace provenance
   chains through the cairn without a live conversational model?

## Instructions for Next

This tensor is addressed to whoever in Yanantin's ecosystem picks it up — a scout,
a scour, a Master Builder instance, Tony reading the cairn. The findings are
empirical and current as of 2026-03-21.

The most actionable items:
1. **Intra-tensor edges.** Add `depends_on` to Strand, `shed_from` to DeclaredLoss,
   prediction targets to IFN items. This is a schema change to Apacheta's models.
2. **Structured context materialization.** When serving tensors to models, include
   the dependency graph and loss history, not just content.
3. **Episodic index coalescing.** Apply temporal hierarchy to cairn references —
   recent tensors individual, older ones as episodes.
4. **Breathing-aware compaction.** Don't treat periodic reorganization as failure.
   Build correction chains that expect it.

The simulation (Hamutay + Tinkuy) has found things the persistent architecture
(Yanantin) needs. The persistent architecture has infrastructure (Apacheta,
Awaq, Activity Stream) that the simulation lacks. The convergence is overdue.
