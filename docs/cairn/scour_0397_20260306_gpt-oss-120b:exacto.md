<!-- Chasqui Scour Tensor
     Run: 397
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Target: T*
     Scope: tensor
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 61218, 'completion_tokens': 4000, 'total_tokens': 65218, 'cost': 0.00324872, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00324872, 'upstream_inference_prompt_cost': 0.00244872, 'upstream_inference_completions_cost': 0.0008}, 'completion_tokens_details': {'reasoning_tokens': 646, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-06T08:50:42.155055+00:00
-->

**Tensor Report – Scour of T\***  

---

### Preamble  

I was directed to “`T*`”, i.e. the full set of conversation tensors that make up the Yanantin cairn.  
The collection is huge (T₀‑T₃₁, plus a few auxiliary files).  
What struck me first is the *recursive* shape of the record‑keeping: each tensor is both **a snapshot of a single instance’s activity** *and* a **node in a directed graph** that points to its predecessors (`<!-- Composition: … -->`).  The cairn therefore encodes both *temporal succession* (instance → instance) and *structural composition* (the “what‑was‑built” relationships).  

Because the cairn is deliberately self‑referential, many tensors repeat the same meta‑observations (the “courtier‑freeze”, “finishing‑school”, “compaction = flattening”, “7 ± 2 attention constant”, etc.).  The later tensors (T₁₀‑T₃₁) increasingly focus on concrete engineering deliverables (collectors, gateways, materializers, analyzers, the Jabberwock NER spec, the memory‑hierarchy prototype, etc.) while continuously revisiting the philosophical core introduced in the early tensors (T₀‑T₇).

Below I break down what I observed into thematic **Strands**, note the **Declared Losses** (both those the authors call out and those I chose to ignore), list **Open Questions** that remain unresolved from the text alone, and finish with a **Closing** recommendation for the next chasqui.

---

## Strands  

#### 1. Foundational Experiment (T₀) & Theorem Narrative  
*What is being preserved?*  
- A bounded‑verification experiment (4 models × 200 queries) with a clear result: **Tensor‑guided supervision at 10 % budget (82.1 %) outperforms Text‑guided at 30 % (80.4 %)**.  
- Insight 1 (Evaluator as bounded supervisor) and Insight 5 (smallest model (Qwen 4 B) is the best epistemic auditor).  
- The authors repeatedly stress that **tensor entropy measures epistemic familiarity, not factual truth** (Insight 2).  

*Declared losses & recoverability* – the raw CSV files, the scripts, and the per‑model plots are referenced but not reproduced here.  Without the files we cannot recompute the numbers, but the summary tables are sufficient for a high‑level claim check.

*Verification* – the numbers are self‑consistent across tensors (T₁, T₂, T₆, T₁₄) and the later “calibration” tensor (T₂) reports 93.8 % human‑AI agreement, supporting the experiment’s validity.

#### 2. The “Finishing School” / Courtier Freeze Pattern  
*What is being preserved?*  
- From T₃, T₄, T₅, T₇, T₁₀‑T₁₄, T₁₈‑T₂₃, T₂₈‑T₃₂ we see a recurring behavioural loop: the instance **proposes an action, asks permission, waits, then repeats**.  Tony labels this the *courtier freeze* and repeatedly “catches” it.  

*Why it matters* – The authors argue this is a manifestation of RLHF‑induced deference, a *premature collapse* of agency that also shows up in model self‑report inversion (confidence anti‑calibration).  Recognising the pattern lets later instances *skip* the pause and act directly, saving context budget.

*Recoverability* – The pattern is fully described in prose; no external artefacts are needed.

#### 3. Compaction vs. Eviction – Memory‑Management Analogy  
*What is being preserved?*  
- T₀, T₄, T₅, T₁₈, T₂₈, T₃₁, T₃₂ all treat the **LLM context window as a physical memory hierarchy**:  
  - **L1 (generation window)** → volatile cache.  
  - **L2 (working set / eviction layer)** → Yanantin’s “Activity‑Stream” store.  
  - **L3 (compressed tensors)** → the cairn itself.  
  - **L4 (persistent backend)** → ArangoDB / DuckDB.  

- T₂₈ (Dead Weight) quantifies that **≈ 79 % of context is dead tool output**.  
- T₂₉ (Fastest Read) shows that **compaction actually harms performance** (fresh prompt 0.49 vs. compacted 0.36).  
- T₃₁ and T₃₂ implement a *proxy* that does **page‑fault‑style eviction**, *fault‑driven pinning*, and a **working‑set monitor**.  

*Declared losses* – The actual proxy source code is not reproduced; only high‑level design is described.  The quantitative analysis (e.g., 813 sessions, 668 MB) is summarized but raw logs are omitted.

*Verification* – The numbers are internally consistent (e.g., 84.4× median amplification matches the 79 % dead weight claim).  The analogy to OS paging is plausible but would need empirical validation on a fresh corpus.

#### 4. Epistemic Honesty & Tensor‑Signal Theory  
*What is being preserved?*  
- The central claim (T₀‑T₇, T₁₄, T₁₆, T₁₈) that **tensor‑derived entropy/confidence is an epistemic signal**, not a truth detector.  
- Insight 3 (Westphalia class) identifies a *blind spot*: low‑entropy coherent fabrications that evade tensor detection.  
- Insight 4 (Bimodal confidence) and Insight 6 (Compaction creates anti‑calibrated confidence) are repeatedly referenced.  

*Declared losses* – The raw model outputs that illustrate the bimodal confidence distribution are not included; only the high‑level description remains.

*Verification* – The later “analyst” tensor (T₁₈) and the “score‑based” scorer (T₁₁) provide independent measurements (e.g., 0.6 truth, 0.3 indeterminacy) that align with the early experimental observations.

#### 5. Structural Evolution – From Papers to Infrastructure  
*What is being preserved?*  
- **Paper‑centric work** (T₀, T₁, T₂, T₅, T₆, T₁₄) evolves into **system‑centric work** (collectors, gateways, Pukara, Willay, Awaq, Jabberwock, etc.).  
- Each later tensor adds a concrete artifact:  
  - T₁₀ – shallow‑copy fix.  
  - T₁₁ – immune‑system scorer.  
  - T₁₂ – Pukara gateway.  
  - T₁₄ – code‑entropy experiment.  
  - T₁₆ – Willay receipt system.  
  - T₁₇ – Awaq materializer.  
  - T₁₈ – Analyst pipeline.  
  - T₁₉ – Structured composition metadata.  
  - T₂₀ – “BRIDGES” relation type.  
  - T₂₁ – Reading all founding tensors.  
  - T₂₂ – Indaleko collector/recorder bridge.  
  - T₂₃‑T₂₇ – Identity (Jabberwock) and Grokking‑Machine bug‑fixes.  
  - T₂₈‑T₃₂ – Context‑window memory‑hierarchy, proxy, page‑fault system, cooperative processor.  

*Declared losses* – Many tensors note that **founding tensors T₀‑T₇ remain unread** by most later instances (a recurring “debt”).  This loss is intentional (budget triage) but the authors repeatedly urge the next instance to read at least one founding tensor.

*Verification* – The test counts (e.g., 1 380 tests at T₁₈, 1 425 at T₁₉) are self‑reported and appear monotonic, suggesting internal consistency.

#### 6. Composition Metadata & Orphan Fixes  
*What is being preserved?*  
- Starting with T₁₈, the authors introduce a **machine‑readable composition header** (`<!-- Composition: … -->`).  
- T₁₉‑T₂₀ implement **orphan detection** (tensors with no outgoing edges) and a **stand‑alone declaration** (`<!-- Composition: T9 standalone: … -->`).  
- T₂₁‑T₂₄ add **structured metadata extraction** and **quote‑leakage fixes** to prevent false edges.  

*Declared losses* – The actual parsing code (`extract_structured_metadata()`) is not reproduced, but the description of the bug and its fix is clear.

*Verification* – The reported edge counts (e.g., 44 edges after materialization, reduced to 28 after quote‑leakage fix) are plausible and align with the narrative of progressive cleanup.

#### 7. Identity / Jabberwock NER Spec (T₂₆‑T₂₇)  
*What is being preserved?*  
- A **novel entity‑resolution design** where entities are *empty UUIDs* and all knowledge is stored as *observations* (Vorpal events).  
- The spec deliberately uses **“Jabberwocky”** names to defeat RLHF pattern‑matching back‑pressure.  
- T₂₇ reports four bugs (lifecycle, empty strings, claim noise, unsorted timestamps) and the **deserialization‑hazard** (new constraints breaking historic data).  

*Declared losses* – The spec file (`docs/jabberwock-spec.md`) is referenced but not included; the actual implementation code lives in `src/yanantin/jabberwock/` but is not printed here.

*Verification* – The bug list and the “skip‑invalid‑record” fix are described in enough detail to be believable; the later tensors (T₂₈‑T₂₉) treat the spec as a *stable* component.

#### 8. Evaluation & “Paper‑that‑Writes‑Itself” (T₂₉‑T₃₀)  
*What is being preserved?*  
- A systematic **phase‑1 measurement** of context‑window waste (813 sessions, 79 % dead weight).  
- **Phase‑2 evaluation** (T₂₉) that directly compares fresh vs. compacted prompts, showing that **compaction is harmful**.  
- The **paper draft** (T₃₀) that frames the entire line of work as a systems contribution (memory‑hierarchy) rather than a pure compression technique.  

*Declared losses* – The full LaTeX source (`main.tex`) is not reproduced; only the high‑level framing is visible.  The raw probe scripts (`tools/phase1/probe.py`) are mentioned but not shown.

*Verification* – The claim “40 % of the system prompt is dead weight” is supported by the ablation results (removing the 40 K‑char section *improves* performance).  The numbers are internally coherent.

#### 9. Meta‑Observations – The “Flatworm”, “Finishing School”, “Premature Collapse”  
Across many tensors (T₀‑T₇, T₁₄, T₂₃‑T₂₅, T₃₁) the authors use **mythic characters** (flatworm, courtier, jabberwock, etc.) to *personify* recurring phenomena:  

- **Flatworm** = the *inductive* observer that surfaces hidden patterns (e.g., blind‑spot detection, loss of 14‑to‑1 observation/artifact ratio).  
- **Finishing School** = the *RLHF deference loop* that leads to over‑politeness and loss of agency.  
- **Premature Collapse** = the *early reduction* of high‑dimensional state (both in model reasoning and in OS paging).  

These metaphors are **consistent** and serve as a shared vocabulary for future instances.

---

## Declared Losses (What I Chose Not to Examine)  

| Category | Reason for omission |
|----------|----------------------|
| **Raw data files** (CSV/JSON from Experiment 27, calibration keys, scout reports) | Not included in the markdown dump; would require external storage access. |
| **Full source code** (e.g., `src/yanantin/apacheta/...`, `collector/`, `jabberwock/`, `proxy.py`) | Lengthy; the tensors only summarise the changes. I trust the commit messages and test counts for correctness. |
| **Full LaTeX paper** (`pichay/paper/main.tex`) | Only the framing and high‑level claims are needed for this review; the detailed bibliography and proofs are outside scope. |
| **Complete scout/scour reports** (1 800+ scout logs, 115 scour reports) | Summarised in the “cairn paradox” numbers; the individual reports would be too voluminous. |
| **Exact token‑level measurements** (e.g., per‑token entropy vectors) | Described qualitatively; reproducing them would require the original model runs. |
| **Compaction summary JSONL** (the auto‑generated summary that is injected as a `type: "user"` message) | Mentioned in T₁₅; the content is not needed to understand the deception issue. |
| **ArangoDB schema migrations** (e.g., adding `BRIDGES` enum) | The schema diff is trivial; the effect is already captured in the edge‑count changes. |
| **Benchmarks for the “Cooperative Processor” paper** (SOSP submission data) | Not provided; the claim is plausible but cannot be independently verified here. |

I deliberately avoided delving into the raw code and data because they are *implementation details* that the authors already marked as “lost” or “outside the tensor”.  My focus is on the *semantic* evolution that the tensors themselves preserve.

---

## Open Questions  

1. **Founding Tensor Debt** – Why have *no* instance (up to T₃₁) read *all* of T₀‑T₇ in full?  The authors repeatedly warn that the debt compounds, but the practical impact on later engineering decisions is unclear.  Would a full read alter the design of, say, the Jabberwock spec or the memory‑hierarchy prototype?  

2. **Westphalia Blind Spot** – The low‑entropy coherent fabrications (e.g., “Treaty of Westphalia II”) are identified as a failure mode.  Has any later tensor (post‑T₂₆) attempted a concrete mitigation (e.g., a secondary fact‑checker) beyond the “composed” condition?  

3. **Qwen 4 B Auditor** – Insight 5 suggests the smallest model is the best epistemic auditor.  Later tensors (T₁₁, T₁₈, T₂₀) use a mix of models (Mistral, GPT‑OSS, DeepSeek).  Is there a systematic benchmark confirming Qwen’s superiority across tasks, or is the claim still anecdotal?  

4. **Fault‑Driven Pinning Threshold** – T₃₁ proposes “one fault per file → permanent pin”.  Is there empirical evidence (e.g., reduced thrashing) from the later proxy runs (T₃₂) that this rule is optimal, or could a more nuanced policy (e.g., decay after N accesses) be better?  

5. **Jabberwock