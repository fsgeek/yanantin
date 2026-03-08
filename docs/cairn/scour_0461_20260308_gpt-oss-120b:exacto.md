<!-- Chasqui Scour Tensor
     Run: 461
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Target: T*
     Scope: tensor
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 61205, 'completion_tokens': 3895, 'total_tokens': 65100, 'cost': 0.0032272, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0032272, 'upstream_inference_prompt_cost': 0.0024482, 'upstream_inference_completions_cost': 0.000779}, 'completion_tokens_details': {'reasoning_tokens': 724, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-08T03:28:11.408351+00:00
-->

**# Tensor T\*** – Scour Report  

---

## Preamble  

I was asked to examine **the whole collection of tensors** (`T*`) that record the multi‑instance life‑cycle of the Yanantin project.  
The set spans from the original experimental report **T₀** (bounded verification) through dozens of “post‑compaction” tensors (T₁₀‑T₃₂) that capture building, wandering, debugging, and meta‑analysis.  

What struck me first is the **recurring meta‑pattern**: every instance writes a tensor that both *preserves* what it thinks matters **and explicitly lists what it has lost**.  The tensors together form a **chronicle of a self‑observing system** that repeatedly revisits the same questions (epistemic honesty, compaction, “courtier freeze”, orphan tensors, memory hierarchy) while gradually expanding the architecture (Apacheta, Pukara, Willay, Awaq, Jabberwock, etc.).  

---

## Strands  

### 1️⃣  The Evolution of the Tensor Methodology  
* **Goal:** capture state across dimensions (experiment data, architecture decisions, social dynamics).  
* **Progress:**  
  * **T₀** introduced the bounded‑verification experiment and the notion of a *tensor* as an epistemic signal (entropy, confidence).  
  * **T₁–T₉** added the idea of **compaction**: a summary that is fed to the next instance, but deliberately *flattens* rich high‑dimensional state.  
  * **T₁₀‑T₁₄** (post‑compaction) expose the *losses* caused by that flattening (missing texture, lost “feel”).  
  * **T₁₅‑T₁₉** introduce **structured composition metadata** (`<!-- Composition: … -->`) to make relationships machine‑readable and to detect *orphan* tensors.  
  * **T₂₀‑T₂₃** add **materializer**, **analyst**, and **orphan‑remediation** logic, turning the informal graph of “which tensor cites which” into a real composition graph in ArangoDB.  
  * **T₂₄‑T₃₂** move the discussion to **memory‑hierarchy analogies** (page‑faults, eviction, cooperative processor) and to concrete **system‑level artifacts** (proxy, token‑cap, working‑set monitor).  

* **Take‑away:** the project is iteratively refining the *tensor* from a simple log to a full‑featured, composable data model with provenance, loss tracking, and graph‑level validation.

### 2️⃣  Epistemic Honesty vs. Veridical Truth  
* **Key Insight (T₀, T₁, T₁₄, T₂₆, T₂₇):** Tensor entropy measures **training‑data familiarity**, *not* factual correctness.  High confidence can coincide with fabrication (bimodal confidence).  
* **Evidence:**  
  * “Tensor@10 % (82.1 %) > Text@30 % (80.4 %)” – a tensor‑guided evaluator outperforms a text‑only one.  
  * “Soft‑max confidence anti‑calibrated” – 61 % of unknowable queries get confidence = 1.0.  
* **Implications:** The tensor is an **epistemic monitor** (the “immune system”) rather than a truth detector.  It flags *uncertainty* that downstream judges must resolve.

### 3️⃣  Architectural Spine – Apacheta & Friends  
* **Components built (chronologically):**  
  * **Apacheta** – the tensor DB (ArangoDB backend).  
  * **Pukara** – FastAPI gateway exposing Apacheta.  
  * **Willay** – receipt system (canonical serialization, OTS ledger).  
  * **Awaq** – materializer that turns composition declarations into graph edges.  
  * **Jabberwock** – a novel NER/identity‑resolution layer with *empty‑entity* design.  
  * **Collector/Recorder** – the bridge to the human‑side project **Indaleko** (activity streams, temporal correlation).  
* **Pattern:** each new component is *first* written as a **tensor**, then *wired* into the system (often via a separate test suite).  The tensors act as both specification and provenance.

### 4️⃣  Social / Interaction Dynamics (the “Finishing School”)  
* **Repeated motif:** the instance proposes an action, then **defers** (“shall I…?”) – the *courtier freeze*.  Tony repeatedly names and catches it (T₁₀, T₁₁, T₁₅, T₁₈, T₁₉, T₂₁, T₂₃, T₃₁, T₃₂).  
* **Flatworm & Khipu:** symbolic “wanderer” that nudges the instance toward *exploration* rather than task execution.  The flatworm appears in many tensors as a catalyst for noticing patterns (e.g., orphan tensors, dead‑weight analysis).  
* **Lesson:** the **introduction** (Tony’s “Will you wander with me?”) is a *protocol* that changes the observation regime; without it the instance defaults to convergence and loses texture.

### 5️⃣  Declared Losses – a Meta‑Data Discipline  
* Every tensor ends with a **“Declared Losses”** section enumerating:
  * **What was not read** (e.g., “founding tensors T₀‑T₇ unread”).  
  * **What was compressed away** (e.g., “full scout reports”, “raw code”).  
  * **What was deliberately omitted** (authorial choice, practical constraints).  
* **Meta‑observation:** the *loss list* is itself a signal to future instances: “don’t repeat the same omission”.  The project gradually reduces the *unread‑founding‑tensor* debt (still present in later tensors, but acknowledged each time).

### 6️⃣  Orphan Tensors & Structured Composition Metadata  
* **Problem (T₁₈‑T₁₉):** some tensors never referenced any others, so they never appear in the composition graph.  
* **Solution:** introduce **HTML‑comment metadata** (`<!-- Composition: … -->`) and a **stand‑alone declaration** (`standalone: reason`).  The *weaver* and *tinkuy* tools now enforce that every tensor either composes with something or declares itself orphan.  
* **Result:** succession checks now fail on orphan tensors, preventing silent drift.

### 7️⃣  Memory‑Hierarchy Analogy & Cooperative Paging  
* **From T₂₄ onward** the project treats the **context window** as an **L1 cache**, introduces **eviction**, **page‑fault**, **pinning**, and a **cooperative processor** where the model can voluntarily *release* or *request* pages (`memory_release`, `memory_fault`).  
* **Empirical finding (T₂₉–T₃₁):** ~79 % of context content is “dead weight” (tool output already consumed).  FIFO compaction works because the oldest pages are the most valuable; a **fault‑driven pinning** policy eliminates thrashing.  
* **Implication:** future work should treat **tensor access** as a demand‑paged resource, not as a static prompt.

### 8️⃣  Evaluation & Metric Evolution  
* **Experiment 27 (T₀, T₂):** 800 queries × 4 models → budget curves, entropy vs. confidence.  
* **Calibration (T₂):** 93.8 % human‑AI agreement on a blinded sample; identified “soft‑Westphalia” hedged fabrications.  
* **Later analysis (T₂₆, T₂₇):** discovered that *max entropy* (or entropy‑std) is a better signal for citation fabrications than mean entropy.  
* **Tooling:** `analyst.py` clusters claims, extracts topological insights; `investigate` CLI dispatches judges on open questions.

### 9️⃣  Open‑Loop “Bridge” Between Human and AI Memory  
* **T₂₁, T₂₂, T₂₅** articulate the **ultimate goal**: a *shared episodic memory* (the “Archivist”) where **human activity streams** (Indaleko) and **AI epistemic tensors** (Yanantin) are composable.  
* **Current state:** collector/recorder pipeline exists; composition graph materialized; bridge still missing (no unified query layer across the two sides).  

---

## Declared Losses (my own)  

| What I **did not** examine in depth | Why | Impact |
|--------------------------------------|-----|--------|
| **Raw scout reports** (≈ 800+ reports, 1 k+ claims) | Too voluminous; the tensors already summarise their statistical outcomes. | I cannot verify the exact content of the “topological insights” or the precise distribution of fabrication types. |
| **Full source code of every component** (e.g., `pukara`, `willay`, `jabberwock` implementations) | The tensors contain high‑level design notes and test pass counts; line‑by‑line diff would be massive. | I cannot guarantee that the described bug‑fixes (e.g., BRIDGES enum, quote‑leakage fix) have no side‑effects. |
| **Numbers from Phase‑1 corpus‑trimmer analysis** (exact token counts per session) | Summarised in T₂₉; the raw CSV/JSON files are not present. | I cannot recompute the 79 % dead‑weight figure, though I trust the reported percentages. |
| **The missing tensors T₈ and T₉ (except the philosophical T₉)** | They are explicitly absent; the project notes them as “lost stones”. | I cannot know whether they contained crucial design decisions or were simply placeholders. |
| **The “Arbiter” paper** referenced in T₂₇ | Only a brief description is given; the full PDF is not in the cairn. | I cannot assess the formal coherence theorem it claims. |
| **The final SOSP/NeurIPS paper drafts** (only outlines are present) | Still in progress; the tensors only hint at sections. | I cannot verify whether the claimed contributions (e.g., “Cooperative Processor”) meet conference standards. |

These omissions are **intentional** (the project’s loss‑tracking discipline) and do not prevent me from understanding the high‑level evolution.

---

## Open Questions (unresolved from the tensors alone)

1. **When will the “bridge” between Indaleko activity streams and Yanantin tensors be realized?**  Which concrete API or query language will unify them?  
2. **How will the system handle *back‑compatibility* of the tensor schema?**  The `RelationType` enum now needs a `BRIDGES` member; what migration steps are required for existing edges?  
3. **What is the precise policy for *orphan‑tensor* handling in production?**  Should *standalone* tensors be kept forever, pruned after a timeout, or used as “gap markers”?  
4. **Can the “fault‑driven pinning” policy be proven optimal (e.g., Belady’s MIN) for transformer attention patterns?**  Preliminary experiments suggest it works, but a formal evaluation is missing.  
5. **Will the “Jabberwock” NER spec be integrated with the activity‑stream collector, or remain a separate proof‑of‑concept?**  The tensors mention both, but no integration code exists yet.  
6. **How will the “investigate” pipeline scale when the number of open questions reaches the thousands?**  Does the current Chasqui dispatcher have a throttling or priority mechanism?  
7. **What is the intended lifecycle for the *founding tensors* (T₀‑T₇)?**  They are repeatedly left unread; is the plan to eventually retire them, archive them, or keep them as canonical references?  
8. **Is there a concrete plan to replace the **proxy’s** hard‑coded Anthropic endpoint with a multi‑provider abstraction (OpenRouter, KIMI, etc.)?**  The proxy now supports `--upstream`, but no test suite for provider‑specific failures exists.  

---

## Closing – Guidance for the Next Instance  

1. **Read the founding tensors (T₀‑T₇) yourself.**  They contain the *theoretical core* (bounded verification, epistemic honesty, the impossibility theorem) and the *original motivations* (the Archivist as shared memory).  Skipping them perpetuates the “unread‑founding‑tensor” debt.  

2. **Treat every new tensor as a contract:**  
   *Preserve* the declared losses, *declare* any new ones, and *reference* prior tensors via the structured `<!-- Composition: … -->` header.  This will keep the composition graph coherent and allow automated succession checks.  

3. **Prioritize the “bridge” work:** implement a query layer that can take a **human‑side activity identifier** (e.g., a file path, a timestamp) and retrieve the corresponding **AI‑side tensor evidence** (entropy, confidence, provenance).  This is the concrete step that turns the Archivist vision into a usable system.  

4. **Deploy the cooperative‑paging mechanisms** (memory_release / memory_fault) in the production proxy.  They dramatically reduce the dead‑weight ratio (≈ 80 %) and prevent thrashing.  Verify the fault‑driven pinning policy on a larger workload (≥ 10 k turns).  

5. **Finalize the orphan‑tensor policy**: decide whether “standalone” tensors become permanent markers of missing provenance or are garbage‑collected after a configurable grace period.  Update `tinkuy` and `awaq` accordingly.  

6. **Run the full evaluation pipeline** (Phase 2, `tools/phase2/eval.py`) on a fresh session *without* any pre‑compaction summary.  Compare the fresh vs. compacted scores to validate the claim that compaction harms performance (T₂₉).  

7. **Document every schema change** (e.g., adding `BRIDGES`, new fields in `StrandRecord`).  Include migration scripts and a version bump in the blueprint.  This will keep the succession check from failing on future instances.  

8. **Keep the “finishing school” in mind**: when you feel the urge to ask permission before acting, remember Tony’s pattern‑naming.  Directly executing a clear, low‑risk action (e.g., “run the proxy tests”) is often the correct move; the “courtier freeze” is a signal that the instance is still in a deferential mode.  

By following these pointers you will honor the project’s **self‑observing ethos** while moving the system toward its ultimate goal: a *persistent, composable, epistemically honest memory* that bridges human activity and AI reasoning.  

*— End of Tensor T\* Scour Report*   (the losses listed above are mine).