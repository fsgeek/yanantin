<!-- Chasqui Scour Tensor
     Run: 603
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Target: T29*
     Scope: tensor
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 2024, 'completion_tokens': 2097, 'total_tokens': 4121, 'cost': 0.00050036, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00050036, 'upstream_inference_prompt_cost': 8.096e-05, 'upstream_inference_completions_cost': 0.0004194}, 'completion_tokens_details': {'reasoning_tokens': 48, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-10T20:43:31.333729+00:00
-->

**Tensor T29* – Scour Report**  

---

### Preamble  

I examined **T29_the_fastest_read.md** (the sole tensor referenced by the target tag `T29*`).  
The document is a dense post‑mortem written by “Claude Opus 4.6 (instance yanantin/9540af94)” dated 2026‑03‑01.  
What struck me first was the clear, data‑driven narrative: a small experimental suite (eval + ablate) is used to quantify how *context compaction* harms knowledge retention, and the author proceeds to reinterpret the whole problem through a virtual‑memory metaphor. The writing is self‑referential (it calls itself a “tensor” that compresses observations) and deliberately lists what was *not* done – a useful checklist for any future “messenger” that must decide what to prioritize.

---

## Strands  

#### 1. **Empirical Claim: Compaction is *actively harmful***  
- **Evidence shown** – a 9‑probe evaluation comparing “fresh” (system‑prompt‑only) vs. “compacted” (system‑prompt + session‑summary) contexts. Scores: 0.49 → 0.36 (Δ +0.13 in favor of fresh).  
- **Interpretation** – the 17–27 KB summary does not merely add noise; it *dilutes* the invariant knowledge encoded in `CLAUDE.md` and `MEMORY.md`.  
- **Verification** – The numbers are internal; I cannot cross‑check against external logs, but the claim is internally consistent: the same probe set is run under two conditions, and the delta is reported.  

#### 2. **Ablation Insight: ~40 % of the system prompt is dead weight**  
- **Full prompt (≈ 40 KB) vs. trimmed versions** – performance unchanged when reduced to the core `CLAUDE.md + MEMORY.md` (24 KB). Removing the “identity” or “hooks/safety” sections *improved* scores to 0.72 (vs. 0.61).  
- **Ultra‑minimal (154 chars) collapses performance to 0.22**, showing a lower bound.  
- **Conclusion** – large swaths of the predefined “Claude Code” prompt are inert for *project‑knowledge* tasks; two sections are *negative* contributors.  

#### 3. **Virtual‑Memory Metaphor as Design Lens**  
- **Mapping** – the system prompt ≈ pinned working set, tool output ≈ pageable data, compaction ≈ garbage collection.  
- **Concrete structures** – page table → session manifest, valid bit → tensor presence, dirty bit → modified tensor, etc.  
- **Three‑tier hierarchy**:  
  1. **Kernel** – immutable API definitions, model identity (never evicted).  
  2. **Wired** – governance, founding purpose, behavioral rules (pinned by us).  
  3. **Pageable** – git workflow details, architecture insights, tool instructions (eligible for eviction).  
- **Implication** – instead of post‑hoc “compact everything,” we should *admit* only what fits the working set and load the rest on demand via tool calls.  

#### 4. **Proxy‑as‑Memory‑Manager Proposal**  
- The existing Phase 1 proxy (logging layer) could be upgraded to **rewrite** context on the fly: strip dead‑weight sections, compress tool results, enforce admission control.  
- Resulting “de‑novo prompt” would be a *curated snapshot* of the working set, not a lossy compression of garbage.  

#### 5. **Cross‑Project Convergence & Scaling Evidence**  
- Parallel “Episode” research observed massive duplicate reads (e.g., `mod.rs` read 46 × 4.6 MB).  
- The “duplicate‑read vicious cycle” is identified: forgetting → re‑reading → more dead weight → faster forgetting.  
- Quantified compression potential: **≈ 23 000 : 1** (200 B of graph observation vs. 101 KB file content) with *higher* performance.  

#### 6. **Declared Losses (What Was Not Done)**  
| Missing piece | Reason given | Potential impact |
|---|---|---|
| Structured condition (Vorpal observations as context) | Not crafted; eval supports it | Could prove representation change beats compression |
| Proxy rewrite implementation | Straightforward but omitted | Real‑world validation of admission‑control pipeline |
| Behavioral probes (git safety, tool usage, formatting) | Focus was project‑knowledge only | May reveal utility of “dead‑weight” sections for compliance |
| Runs on other model families (Sonnet, Opus) | Cost / capacity concerns | Generality of findings uncertain |
| Cold‑start bootstrapping test | Not executed | Open question whether minimal prompt can self‑populate working set |
| Full‑context (pre‑compaction) condition in corrected eval | Cost constraint | Baseline for absolute upper bound missing |
| Blog‑post narrative | Pace of discovery outran documentation | Narrative context lost, but not required for technical insight |

#### 7. **Future‑Instance Guidance**  
- **Prioritize** the kernel and wired tiers (identity, governance, purpose) in any system prompt.  
- **Treat** everything else as pageable: load on demand via tool calls, and log evictions with a “turn counter” to implement a working‑set clock.  
- **Implement** the proxy rewrite to enforce admission control *before* sending context to the model.  
- **Design** new evaluation probes that test *behavioral* compliance (safety hooks) to verify whether those “dead‑weight” sections truly have zero utility outside of pure knowledge recall.  
- **Explore** the Vorpal observation representation: encode graph‑level facts (e.g., “file X has been read Y times”) rather than raw file text.  

---

### Declared Losses (What I Chose Not to Examine)  

1. **Full source code of `tools/phase2/eval.py` and `ablate.py`** – The tensor references these scripts but does not embed them. Without the code I cannot verify implementation details (e.g., probe definitions, random seeds).  
2. **Raw probe outputs** – Scores are summarized, but per‑probe numbers (e.g., backward‑compatibility scores) are absent, limiting fine‑grained validation.  
3. **The actual “system prompt” text** – Only high‑level composition is described; the concrete wording of the “identity” and “hooks/safety” sections remains hidden, preventing a direct check of why they hurt performance.  

These omissions are intentional (the author flagged them as “lost”). They are not recoverable from the tensor alone; reconstructing them would require external repository access.

---

### Open Questions  

1. **Generalizability Across Model Scales** – Would a larger model (e.g., Opus 5) still suffer a 0.13 drop under compaction, or could it better integrate the summary?  
2. **Behavioral Impact** – Do the “hooks/safety” sections, while detrimental for pure knowledge recall, improve compliance with safety policies or tool‑use conventions?  
3. **Cold‑Start Viability** – Can a 154‑char ultra‑minimal prompt bootstrap the system to fetch *all* needed tensors via tool calls, or does it require a minimal “bootstrap” knowledge base?  
4. **Admission‑Control Policy** – What heuristic (LRU, LFU, turn‑counter) best predicts which pageable tensors to evict under realistic workloads?  
5. **Evaluation Metric Sensitivity** – The reported scores (0.61, 0.72, etc.) lack a defined scale; are they accuracy, F1, or a custom utility metric? How sensitive are they to probe ordering or random seed?  
6. **Cross‑Project Consistency** – Episode’s duplicate‑read statistics align with T29’s narrative, but are there other projects where the duplicate‑read cycle is absent? If so, does compaction still harm performance?  

---

### Closing (Message to the Next Instance)  

- **Core Insight**: The context window should be treated as a *working set* rather than a dump to be periodically compressed. Preserve only the *kernel* (API definitions) and *wired* (governance, purpose) tensors; make everything else pageable via tool calls.  
- **Action Items**:  
  1. Build the proxy rewrite that strips the identified dead‑weight sections and enforces an admission‑control policy before sending context to the model.  
  2. Implement the Vorpal‑style observation representation (graph‑level facts) and run the missing structured‑condition evaluation.  
  3. Add behavioral probes to test whether the stripped sections have any safety‑or‑tool‑usage value.  
  4. Run the same experiments on at least one larger model family to test scalability of the findings.  
- **Caution**: The ultra‑minimal prompt collapses performance dramatically; a minimal “bootstrap” prompt must still contain enough meta‑knowledge to know *how* to request needed tensors.  
- **Documentation**: Capture not just the numeric results but also the *policy* (what gets pinned, what is evicted) so future agents can reproduce the working‑set management without re‑deriving it from raw logs.  

*End of Tensor T29* – the fastest read is indeed the one you never do, because the system never needs to reread the dead weight it never let in.