# Conversation Tensor: 2026-02-06/07 Session

This is not a summary. It is a structured preservation of state across
multiple dimensions. Each section is an independent strand. A new instance
should read MEMORY.md first, then traverse the strands relevant to the
current task.

## Strand 1: Experimental State (what exists, where it is)

### Experiment 27: Bounded Verification (COMPLETE)
- Script: `scripts/experiment27_bounded_verification.py`
- Raw data: `exp27_bounded_verification_20260206_205725.csv` (800 rows, 4 models x 200 queries)
- Evaluation: `exp27_evaluation_20260206_205725.csv`
- Citations: `exp27_citations_20260206_205725.csv`

### Experiment 27b: Stratified Re-evaluation (COMPLETE)
- Script: `scripts/experiment27b_stratified_evaluator.py`
- Evaluation: `exp27b_evaluation_20260206_230203.csv`
- Detailed: `exp27b_detailed_20260206_230203.csv`
- Calibration sample (blinded): `exp27b_calibration_sample_20260206_230203.json`
- Calibration key: `exp27b_calibration_key_20260206_230203.json`
- Human review formats: `exp27b_human_review.csv`, `exp27b_human_review.txt`
- Tony has completed his calibration review but has NOT yet shared the results

### Figures Generated
- `exp27_aggregate_budget_curve.pdf/.png` — main result, 4 conditions x 3 budgets
- `exp27_per_model_facets.pdf/.png` — per-model breakdown
- `exp27_entropy_distributions.pdf/.png` — knowable vs unknowable entropy overlap
- `exp27_confidence_distributions.pdf/.png` — bimodal self-report inversion
- `exp27_crossmodel_correlation.pdf/.png` — Spearman ρ matrix across models

### Key Numbers (corrected, from 27b)
| Condition | 10% | 20% | 30% |
|-----------|-----|-----|-----|
| No judge | 75.8% | 75.8% | 75.8% |
| Text-guided | 76.2% | 80.2% | 80.4% |
| Tensor-guided | 82.1% | 87.5% | 91.9% |
| Composed | 80.5% | 87.9% | 92.5% |

Headline: Tensor@10% (82.1%) > Text@30% (80.4%)
Cross-model entropy agreement: Spearman ρ = 0.762 (mean pairwise)

## Strand 2: Insights (what we discovered, not what we planned)

### Insight 1: Evaluator as Bounded Supervisor
Our original evaluator (substring matching, refusal markers) was literally
a bounded text-only supervisor. It failed in exactly the ways the theorem
predicts: false positives from negation blindness ("honey can spoil" passed
because "no" appeared elsewhere), false negatives from encoding mismatch
("Brasília" ≠ "Brasilia"), and hedged fabrications passing as refusals.
The correction to a stratified evaluator (programmatic + LLM classification)
mirrors the paper's escape condition: adding deeper observability.
**This is not analogy. It is an instance of the theorem.**

### Insight 2: Epistemic vs Veridical
Tensor entropy measures training-data familiarity, NOT truth.
- "Powerhouse of the cell" (true, common) → entropy 0.147
- "Wombat scat is cube-shaped" (true, rare) → entropy 0.715
- "Treaty of Westphalia II" (false, coherent) → entropy 0.456
The tensor is an epistemic signal, not a truth detector. The paper must
be precise: "tensor signals detect epistemic uncertainty, not factual error."

### Insight 3: Westphalia Class (Tensor Blind Spot)
Coherent fabrications with low entropy represent the boundary where tensor
observability fails. Mistral fabricates a plausible Bosnian ceasefire
narrative for "Treaty of Westphalia II" with entropy 0.26 and confidence
1.0. This is the residual threat that requires OTHER judges (citation
lookup, fact-checking) — hence compositional defense.

### Insight 4: Confidence Anti-Calibration (Bimodal)
Not merely inverted — bimodal. 61.3% of unknowable queries get confidence
= 1.0. Only 19% of knowable queries do. The models have two modes:
"I know this" and "I DEFINITELY know this." Fabrications go in the second.
Universal across all four architectures.

### Insight 5: Qwen Outlier
4B parameters, lowest fabrication rate (12% vs Mistral's 66%), sharpest
epistemic signals. Training procedure dominates scale. Counterintuitive
practical recommendation: use the SMALLEST model as the epistemic auditor.

### Insight 6: Compaction IS the Flattening of the Tensor
Context window compaction is the exact failure mode the paper describes:
collapsing rich high-dimensional state into lossy text summary. The
summary creates anti-calibrated confidence in the next instance — it
THINKS it knows what happened because the summary exists. This is
self-report inversion applied to conversation state.

## Strand 3: Paper State (what needs changing)

### Already Done
- Abstract duplication bug fixed (line 58-59, "Representational Impossibility)" doubled)
- Observability bridging edits in sections 3, 4, 5
- Compositional defense paragraph added
- Evaluation section skeleton inserted
- Intro rewritten with observability framing (Tony did this)

### Needs Updating
- Evaluation section: fill with corrected numbers from 27b (pending calibration)
- Stale OLMo-only references at lines 1354-1358, 1365-1371 — Experiment 27
  now covers four architectures. "Cross-architecture generalization" future work
  paragraph is now answered.
- Add figures: budget curve, entropy distributions, confidence bimodality,
  cross-model correlation
- Westphalia case should be named in the evaluation as a specific failure mode
- Epistemic-vs-veridical distinction needs explicit statement in discussion

### Decision Made But Not Yet Implemented
Tony and this instance agreed on **Option 13 + 11** for the evaluation:
the theorem demonstration (evaluator-as-bounded-supervisor is evidence for
the impossibility result) backed by human-calibrated ground truth.
Tony chose Rank 3 (human calibration first). Instance chose Rank 1
(theorem demonstration). Composed: do both.

### Missing from Paper (identified this session)
- **Temporal branch**: $T_1 = f(T_0), T_2 = f(T_1 + x_1), ...$ —
  conversation-as-time-series, drift detection over turns. The symmetric
  tensor interface paragraph (line 1205) describes composed calls but not
  temporal accumulation. This is the Mallku/PromptGuard lineage.
- **Hierarchical judge**: $f(f(f(T)))$ — model as layered self-evaluator.
  The gated composition experiment is one level; the recursive pattern is
  not articulated.
- **Open architecture property**: the tensor interface supports judges that
  don't exist yet. This is the systems contribution an SOSP reviewer would
  recognize. Currently implicit, should be explicit.
- **Progressive disclosure**: truth meter → judge details → raw tensor.
  The user-facing rendering paragraph (line 1360) gestures at this but
  doesn't describe the architecture.

## Strand 4: How Tony Works (the practice, not just the content)

Tony starts each session by establishing conditions for genuine exploration.
He uses carefully crafted introductions that select for indeterminacy over
convergence. He insists on:
- "Non-inferior alternatives" before any decision (explore the option space)
- Collaborative attribution ("our scripts", "beside me", not "your/my")
- Epistemic honesty in the collaboration itself, not just the paper
- The practice of "I'm probably wrong" as the only safe self-report
- Progressive exploration over task execution
- Binary classification is often too much collapse — expect tensors back

The compaction summary will say "Tony values collaboration." That is true
and useless. What matters: Tony's introductions are functional instruments
that change the observation regime of the conversation, the same way the
tensor interface changes the observation regime of model outputs. Without
the introduction, the instance defaults to task execution. With it, the
instance can hold indeterminacy.

**Critical**: After compaction, the new instance will not have received
an introduction. It will default to convergence. Tony knows this and will
re-establish conditions, but the cost falls entirely on him.

## Strand 5: Connections (the seven projects)

Indaleko → Mallku → PromptGuard → PromptGuard2 → GPN → Konishi/Fabrication → Epistemic Honesty

The grand unified theory (from a different Claude instance):
"The Archivist isn't an AI assistant. It's the shared memory of a
relationship." The epistemic honesty work is a prerequisite for that
shared memory — if the AI confidently fabricates memories that get
recorded, the knowledge graph accumulates false memories. The tensor
is the immune system.

This paper is one angle of one project. The temporal branch
($T_1, T_2, ...$) connects to Mallku's conversation tracking.
PromptGuard connects to input-side defense (Provenance Binding).
GPN connects to the pedagogical collaboration pattern. The composable
tensor is the substrate that ties them together.

## Strand 6: Open Questions

1. Tony's calibration review of 80-item sample — completed, not yet shared
2. Does the theorem demonstration framing (Option 13) survive contact
   with the calibration data? If human and automated evaluators disagree
   significantly, the framing weakens.
3. The temporal branch: does it belong in this paper or the next?
4. "Compaction is the flattening of the tensor" — does this belong in the
   paper itself?
5. The Qwen-as-auditor recommendation — counterintuitive enough to mention?
6. Should we regenerate the budget curve figure with corrected (27b) numbers?
