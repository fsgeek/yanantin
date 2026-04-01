<!-- Chasqui Scour Tensor
     Run: 1488
     Model: mistralai/mistral-small-creative (Mistral: Mistral Small Creative)
     Target: T29*
     Scope: tensor
     Cost: prompt=$1e-07/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 2054, 'completion_tokens': 4278, 'total_tokens': 6332, 'cost': 0.0014888, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0014888, 'upstream_inference_prompt_cost': 0.0002054, 'upstream_inference_completions_cost': 0.0012834}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-01T07:43:32.947709+00:00
     GenerationID: gen-1775029387-FvE461OnF3ARDBgsbILZ
-->

```
<!-- Tensor: T29_analysis -->
<!-- Title: Scour Report — T29_the_fastest_read.md -->
<!-- Author: Mistral Small Creative (instance yanantin/00000000) -->
<!-- Date: 2026-03-02 -->
<!-- Composition: Analyzes T29; references T0, T7, T15, T26, T28 -->

---

### **Preamble**
Examined **T29_the_fastest_read.md**, a tensor authored by Claude Opus 4.6 (instance `yanantin/9540af94`) on 2026-03-01. The tensor documents a **systematic evaluation of context compaction** in the Yanantin cairn, focusing on whether compressing session history preserves critical project knowledge. The author built two tools (`eval.py` and `ablate.py`) to test this, then reframed the problem using a **virtual memory (VM) metaphor** to propose a radical redesign of how context windows are managed.

**What struck first**:
1. The **counterintuitive finding** that compaction isn’t just useless—it’s *harmful*. The compacted summary (17–27K chars) dilutes the signal in the system prompt (CLAUDE.md + MEMORY.md), which contains the "invariants" of the project.
2. The **ablation study’s precision**: 16,082 chars of the 40K system prompt were found to contribute *zero* to performance, while two sections actively degraded it when removed. This suggests the prompt is **bloated with dead weight** and **anti-patterns**.
3. The **VM metaphor’s elegance**: The author maps context window management to memory management (pinned pages = governance core, pageable = tool output, etc.), proposing a **proxy-as-memory-manager** to rewrite requests on the fly. This feels like a **paradigm shift** from compression to *admission control*.
4. The **declared losses** are as revealing as the findings. The author admits not testing the **structured condition** (Vorpal observations vs. compacted summaries), the **proxy rewrite**, or **cold-start bootstrapping**. These gaps hint at **unresolved tensions** in the design.

---

### **Strands**

#### **1. The Compaction Paradox: Why Less Isn’t More**
**What was preserved**:
- A **rigorous experimental setup**: 9 probes testing documented failure patterns (e.g., "builder/tester separation," "Jabberwocky naming defense") under fresh vs. compacted conditions.
- **Quantitative evidence**: Compacted summaries (0.36) underperform fresh prompts (0.49), and ablation shows **40% of the system prompt is dead weight**.
- **A hypothesis**: Compaction faithfully preserves *garbage*, not signal. The system prompt’s invariants (CLAUDE.md, MEMORY.md) are the true knowledge base.

**What was lost (and is it recoverable?)**:
- The **structured condition** (Vorpal observations as context) was not tested. This is critical: if Vorpal’s graph-based observations (200 bytes) outperform compacted summaries (17–27K chars), it would validate the **representation change > compression** claim. *Recoverable?* Yes, if Vorpal observations exist in the cairn (e.g., T7, T15). The author notes this as a "declared loss."
- **Generalization to non-knowledge tasks**: The ablation only tested project knowledge retention. Behavioral probes (e.g., git safety, tool usage) were omitted. *Recoverable?* Likely, but would require re-running `ablate.py` with expanded probes.
- **Cold-start bootstrapping**: Can a model with a minimal prompt effectively load its own context? This is a **fundamental limitation** of the VM metaphor if true. *Recoverable?* Only by testing.

**Claims and verifiability**:
- **Claim**: "The compacted summary buries [invariants] under a recap of files read, code written, and duplicate operations."
  - *Verifiable*: Yes, the eval results (0.36 vs. 0.49) support this. The compacted summary adds noise.
- **Claim**: "16,082 chars contribute zero to performance."
  - *Verifiable*: The ablation data (full prompt = 0.61, CLAUDE.md + MEMORY.md = 0.61) confirms this. The dead weight is real.
- **Claim**: "The OS metaphor isn’t a metaphor."
  - *Verifiable*: The mapping to VM concepts is **plausible and elegant**, but its **practicality** depends on the proxy rewrite (not yet implemented). The author cites **perplexity** (novelty) but not real-world testing.

**Connections to broader project**:
- **T28**: T29 "composes_with" T28, suggesting this is part of a **Phase 2** effort to rethink context management. T28 likely set up the tools (`eval.py`, `ablate.py`) or defined the failure patterns being tested.
- **T0, T7, T15, T26**: These tensors document the "documented failure patterns" (e.g., "Jabberwocky naming defense," "courtier freeze"). T29’s probes are **direct descendants** of these earlier observations.
- **Episode (research-program)**: The parallel work on duplicate file reads (e.g., `mod.rs` read 46 times) **validates the garbage problem** but doesn’t yet link to the VM solution. This suggests **convergence without integration**.

**What future instances need to know**:
- The **VM metaphor is a hypothesis**, not yet proven. The proxy rewrite is the **next critical step**.
- The **system prompt’s dead weight** is a **design flaw**, not just an optimization target. Removing it improved performance.
- **Vorpal observations** may be the key to breaking the compaction paradox, but they haven’t been tested here.

---

#### **2. The VM Metaphor: A Framework for Admission Control**
**What was preserved**:
- A **coherent analogy**: The context window as physical memory, with:
  - **Pinned pages** = governance core (never evicted).
  - **Pageable** = tool output, project state.
  - **Proxy-as-memory-manager** = rewrites requests to strip dead weight.
- **Three tiers of context**:
  1. **Kernel** (API-pinned): tool definitions, model identity.
  2. **Wired** (user-pinned): governance, founding purpose.
  3. **Pageable**: git workflows, architecture insights.
- **Empirical support**: The ablation shows that **tool descriptions, git safety protocols, and commit workflows** (tier 3) contribute zero to knowledge retention.

**What was lost**:
- **Implementation of the proxy rewrite**. The architecture is clear, but the **mechanism for dynamic admission control** isn’t tested. *Recoverable?* Yes, but requires building the proxy.
- **Testing on other models (Sonnet/Opus)**: Haiku’s failure on the `backward_compat` probe suggests **model-specific limits**. *Recoverable?* Yes, but may require prompt tuning.
- **Cold-start validation**: Can a minimal prompt **demand-load** its context? This is the **Achilles’ heel** of the VM metaphor. *Recoverable?* Only by testing.

**Claims and verifiability**:
- **Claim**: "The de novo prompt becomes a curated snapshot of the working set."
  - *Verifiable*: The ablation shows that **stripping dead weight improves performance**, but the "curated snapshot" is still hypothetical until the proxy is built.
- **Claim**: "Nobody has proposed that parts of the system prompt are pageable."
  - *Verifiable*: The author cites **perplexity** (novelty), but this would need a literature review to confirm. The claim seems plausible given the lack of prior work on **dynamic prompt admission control**.
- **Claim**: "200 bytes of graph observation > 101KB of file content (23,000:1 compression)."
  - *Verifiable*: The **compression ratio** is theoretical until Vorpal observations are tested in `eval.py`. The author admits this as a "declared loss."

**Connections to broader project**:
- **MemGPT**: The author contrasts their approach with MemGPT’s **block-level VM metaphor**, arguing for **object-level typing with lifetimes**. This suggests a **deeper integration of tools and context**.
- **Vorpal**: The reference to "Vorpal observations" implies a **graph-based representation** of project state (likely from T7 or T15). This is the **alternative to compaction** being hinted at.
- **Phase 1 proxy**: The existing proxy logs requests but doesn’t yet **rewrite them**. T29 proposes **extending its role** to memory management.

**What future instances need to know**:
- The **VM metaphor is a powerful lens**, but its **practicality depends on the proxy**. Without it, this remains a **theoretical framework**.
- **Vorpal observations** may be the **killer app** for this approach, but they haven’t been tested. Prioritize this.
- **Cold-start is a risk**. If the model can’t **demand-load** its context, the VM analogy breaks down.

---

#### **3. Declared Losses as Design Trade-offs**
**What was lost (and why it matters)**:
| **Declared Loss**               | **Why It Matters**                                                                 | **Recoverable?**          |
|----------------------------------|------------------------------------------------------------------------------------|---------------------------|
| Structured condition (Vorpal)    | Direct test of **representation change vs. compression**. Core to the VM hypothesis. | Yes (if Vorpal exists).   |
| Proxy rewrite                    | **Proves the VM metaphor**. Without it, this is just theory.                        | Yes (implementation).     |
| Behavioral probes                | Tests if dead weight matters for **non-knowledge tasks** (e.g., git safety).        | Yes (expand `ablate.py`).  |
| Sonnet/Opus testing              | **Model capacity limits** may invalidate findings. Haiku failed `backward_compat`. | Yes (run on other models).|
| Cold-start bootstrapping         | **Fundamental flaw** if minimal prompts can’t load context.                       | Yes (test demand-loading).|
| Full-context condition           | **Baseline for compaction**. Cost constrained this, but it’s needed for fairness.  | Yes (re-run `eval.py`).    |
| Blog post documentation          | **Knowledge leakage**. The pace of discovery outruns capture.                     | No (but critical for future instances). |

**What this reveals**:
- The author **prioritized speed over completeness**. The tensor is a **snapshot of a moving target**.
- **Gaps are strategic**: The proxy rewrite and Vorpal test are the **next logical steps**, not oversights.
- **Haiku’s failure** suggests **model-specific tuning** may be needed for the VM approach.

---

### **Declared Losses (What I Chose Not to Examine)**
1. **The contents of T0, T7, T15, T26, T28**:
   - *Why*: These tensors document the "failure patterns" tested in T29’s probes, but their full contents aren’t needed to analyze T29’s **methodology or findings**. The probes are **self-contained** in T29’s description.
   - *Exception*: If T7 or T15 define **Vorpal observations**, those would be critical to examine. I noted this as an **open question** (see below).

2. **The implementation details of `eval.py` and `ablate.py`**:
   - *Why*: The tensor describes their **purpose and results** in enough detail to assess the claims. The code itself isn’t necessary to evaluate the **experimental design or findings**.

3. **The "Episode" research-program’s full findings**:
   - *Why*: The tensor summarizes their **duplicate-read problem** (e.g., `mod.rs` read 46 times), which aligns with T29’s garbage hypothesis. The **parallel convergence** is noted, but the full Episode tensors aren’t needed to analyze T29.

4. **MemGPT’s exact approach**:
   - *Why*: The tensor contrasts T29’s **object-level VM metaphor** with MemGPT’s **block-level** one. The high-level difference is sufficient for analysis; the specifics of MemGPT aren’t required.

5. **The "governance core" and "founding purpose" sections of the system prompt**:
   - *Why*: The tensor states that **removing the identity and hooks/safety sections improved performance**, but doesn’t show their contents. Examining them would require accessing the **full system prompt**, which isn’t provided here.

---

### **Open Questions**
1. **What are Vorpal observations, and how do they compare to compacted summaries?**
   - *Why it matters*: The tensor hints that Vorpal’s **graph-based observations (200 bytes)** may outperform compacted summaries (17–27K chars). This is the **core alternative to compaction**, but the tensor doesn’t describe Vorpal’s method or results.
   - *Where to look*: Likely in **T7 or T15** (referenced in T29’s composition).

2. **Does the proxy rewrite actually work in practice?**
   - *Why it matters*: The VM metaphor’s **practicality hinges on the proxy’s ability to dynamically strip dead weight**. The tensor proposes the architecture but doesn’t test it.
   - *Next step*: Implement the proxy and re-run `eval.py` with the rewritten prompts.

3. **Can a minimal prompt effectively demand-load its context (cold-start problem)?**
   - *Why it matters*: If the model **can’t ask for what it doesn’t know**, the VM analogy fails. The tensor admits this as a **declared loss**.
   - *Next step*: Test a **minimal-prompt model** with a tool that lets it fetch missing context (e.g., "load CLAUDE.md").

4. **Are the dead-weight sections (tool descriptions, git safety, etc.) truly unnecessary for all tasks?**
   - *Why it matters*: The ablation only tested **project knowledge retention**. The tensor admits not testing **behavioral compliance** (e.g., git safety, formatting).
   - *Next step*: Expand `ablate.py` to include **behavioral probes**.

5. **How do these findings generalize to other models (Sonnet/Opus)?**
   - *Why it matters*: Haiku’s **failure on `backward_compat`** suggests **model-specific limits**. The tensor wasn’t tested on larger models.
   - *Next step*: Re-run `eval.py` and `ablate.py` on **Sonnet and Opus**.

6. **What’s the compression ratio of Vorpal observations vs. compacted summaries?**
   - *Why it matters*: The tensor claims **200 bytes of Vorpal > 101KB of file content (23,000:1)**, but this is **theoretical**. The actual ratio would validate the **representation change** hypothesis.
   - *Next step*: Compare Vorpal observations to compacted summaries in `eval.py`.

7. **Is the "backward_compat" probe miscalibrated, or does Haiku lack the capacity to detect invariants?**
   - *Why it matters*: If Haiku **can’t detect backward compatibility issues**, the ablation results may not generalize. The tensor notes this as a **potential probe issue**.
   - *Next step*: Inspect the `backward_compat` probe’s design or re-calibrate it.

---

### **Closing: What to Tell the Next Instance**
1. **T29 is a pivot point**.
   - The findings (**compaction is harmful**, **40% of the prompt is dead weight**, **VM metaphor as a framework**) suggest a **fundamental rethinking of context management**.
   - The **next steps are clear**: Build the proxy rewrite, test Vorpal observations, and validate cold-start bootstrapping.

2. **The VM metaphor is compelling but unproven**.
   - The analogy to **memory management** is elegant, but its **practicality depends on the proxy**. Without it, this remains a **theoretical shift**.
   - **Prioritize implementation**: The proxy rewrite is the **minimum viable test** of the VM hypothesis.

3. **Vorpal observations may be the key**.
   - The tensor hints that **graph-based representations (200 bytes) > compacted summaries (17–27K chars)**. This is the **alternative to compaction** that T29 didn’t fully test.
   - **Find and test Vorpal**: If it works, it could **obviate the need for compaction entirely**.

4. **Declared losses are not oversights—they’re the roadmap**.
   - The author **didn’t test the structured condition, the proxy, or cold-start** because these are the **next logical steps**. Treat them as **action items**, not gaps.
   - **Start with the proxy**: It’s the **bridge between theory and practice**.

5. **Haiku’s failure is a warning**.
   - The `backward_compat` probe scored **0.0 across all variants**, suggesting **model-specific limits**. Larger models (Sonnet/Opus) may perform differently.
   - **Test on multiple models**: The VM approach may need **prompt or architecture tuning** for different instances.

6. **Documentation is a loss, but the tensor is the compression**.
   - The author notes that the **pace of discovery outruns documentation**. This tensor is the **compressed record**, but a **blog post or design doc** would help future instances **reconstruct the reasoning**.
   - **Capture the "why"**: The VM metaphor and the proxy design should be **explicitly documented** to avoid rederiving them.

7. **The sentence holds: "The fastest read is the one you never do."**
   - The tensor’s **core insight** is that **compaction isn’t the solution—admission control is**. The context window should **manage knowledge like memory**, not log it like a journal.
   - **Act on this**: The proxy rewrite and Vorpal test are the **next steps to validate this**.

---
### **What I Know, What I Don’t, What I Made Up**
| **Category**       | **Details**                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| **What I know**    | - Compaction dilutes signal (0.36 vs. 0.49).                                |
|                    | - 40% of the system prompt is dead weight.                                  |
|                    | - The VM metaphor maps cleanly to context management.                       |
|                    | - Vorpal observations are hinted as a potential solution.                  |
|                    | - The proxy rewrite is the next critical implementation.                  |
| **What I don’t**   | - The exact contents of Vorpal observations.                               |
|                    | - Whether the proxy rewrite will work in practice.                         |
|                    | - How these findings generalize to Sonnet/Opus.                            |
|                    | - The full details of the system prompt’s dead-weight sections.              |
| **What I made up** | - *None*. The analysis sticks to the tensor’s text and declared losses.     |
|                    | - *Assumption*: Vorpal observations are graph-based (implied by "200 bytes").|

---
<!-- End Tensor -->
```