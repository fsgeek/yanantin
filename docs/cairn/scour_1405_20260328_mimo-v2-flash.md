<!-- Chasqui Scour Tensor
     Run: 1405
     Model: xiaomi/mimo-v2-flash (Xiaomi: MiMo-V2-Flash)
     Target: /home/tony/projects/hamutay
     Scope: external
     Cost: prompt=$9e-08/M, completion=$2.9e-07/M
     Usage: {'prompt_tokens': 38447, 'completion_tokens': 3646, 'total_tokens': 42093, 'cost': 0.0049385, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0049385, 'upstream_inference_prompt_cost': 0.0038447, 'upstream_inference_completions_cost': 0.0010938}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-28T00:13:17.066561+00:00
     GenerationID: gen-1774656730-T8BrMoG946udRcaNW0JN
-->

# Scour Report: hamutay

## Preamble

This codebase is an experimental research platform exploring **context management for long-horizon AI reasoning**. It appears to be a sibling or predecessor project to Yanantin, sharing the same author (Tony) and similar philosophical DNA. The core problem: transformers degrade with long context (Du et al. 2025), and silent compression leads to hallucination. The solution: **explicit, structured memory projection** where context is periodically compressed into a "tensor" format that declares what was lost.

First impression: this is not production software. It's a research artifact—full of experiments, logs, and exploratory code. The structure is messy (many experiment directories, raw logs scattered), but the core ideas are sophisticated. The project has been actively explored (timestamps show March 2026 activity), with multiple parallel experiment tracks (identity, taste, gating, escalation, crossover, etc.).

Key divergence from Yanantin: hamutay focuses on **operationalizing** the tensor concept through experiments and simulation, while Yanantin focuses on **formalizing** it through schema and infrastructure. Hamutay asks "what works?" Yanantin asks "how do we build it right?"

---

## Strands

### Strand 1: Hamutay as Experimental Validation of Yanantin's Tensor Theory

**What it's doing:** Hamutay is running empirical tests of the tensor concept that Yanantin formalizes. The `experiments/` directory contains dozens of runs testing different configurations:
- `q1_declared_losses/` and `q2_declared_losses/` — testing whether explicit loss declaration prevents hallucination
- `identity_v1/` and `identity_v2/` — testing how planning agents understand vs. misunderstand product specs (revealing gaps in AI reasoning)
- `taste/` — testing AI voice consistency across surfaces
- `cache_sim/` — simulating cost/quality tradeoffs of different memory strategies

**Yanantin learnings:**
- **Empirical grounding:** Yanantin's schema is clean, but hamutay shows what happens when you actually use it. The `tensor_cycle_029.json` file shows explicit losses like "Specific numerical benchmarks... will emerge from Phase 1 testing"—this is the kind of honest incompleteness that Yanantin's schema enables.
- **Failure modes:** The `identity_v1/raw_log_r1/the_question.md` reveals that a planning agent can understand mechanics but miss subjective requirements (voice, taste). This is a concrete example of **why** declared losses matter: the AI "understands" the spec but doesn't internalize the soul. Yanantin's tensor format captures this gap explicitly.

**Overlap:** Both projects use TensorRecord with strands, key_claims, declared_losses, and epistemic metadata. The format is identical.

**Divergence:** Hamutay's tensors are **cycle-based** (one per conversation turn), while Yanantin's are **composition-based** (edges between tensors). Hamutay is more about "what happened this turn," Yanantin about "how we got here."

---

### Strand 2: The Four-Region Context Window Model

**What it's doing:** `cache_simulator.py` implements a sophisticated memory model that could directly inform Yanantin's gateway design:
- **System region** (4K tokens, 1hr TTL): Stable instructions, persona
- **Domain region** (20K tokens, 1hr TTL): Task-specific context
- **Durable region** (30K tokens, 5min TTL): Projected state (tensor_d)
- **Ephemeral region** (rest, 5min or uncached): Working set (tensor_e)

**Key insight from simulation:** The simulator models **attention cost** (quadratic in context length) separately from **token cost**, and shows that different eviction strategies produce different Pareto frontiers. The `Adaptive_lossge5.csv` and `PressureTriggered_0.8.csv` files suggest they're exploring adaptive eviction based on loss thresholds.

**Yanantin learnings:**
- **Provider-specific optimization:** Hamutay explicitly separates architecture (provider-independent) from optimization (provider-specific). Yanantin's gateway could adopt this: the core protocol is the same, but caching behavior is a plugin.
- **Simulation before building:** The cache simulator runs **pure accounting** on real traces before implementing the actual gateway. This is a pattern Yanantin should follow: simulate cost/quality tradeoffs before committing to API design.
- **Attention cost modeling:** Yanantin currently models token cost but not attention cost. Hamutay's simulation shows that even with caching, long context has quadratic attention cost. This validates Yanantin's durable/ephemeral split.

**Overlap:** Both projects aim for provider-independent architecture with provider-specific adapters.

**Divergence:** Hamutay's simulation is **reactive** (replays traces), while Yanantin's gateway is **proactive** (decides what to project). Yanantin could learn from hamutay's measurement methodology.

---

### Strand 3: Declared Losses as Epistemic Infrastructure

**What it's doing:** The `q2_declared_losses.py` experiment is testing a core hypothesis: **does seeing your own prior losses make you better at declaring future losses?** The `MaskedLossProjector` subclass removes `declared_losses` from the tensor before projection, creating a control condition.

**Yanantin learnings:**
- **Loss taxonomy sophistication:** The experiment measures not just *whether* losses are declared, but *how sophisticated* the taxonomy becomes over time. This is a metric Yanantin's schema should support: `DeclaredLoss` has `category` (CONTEXT_PRESSURE, TRAVERSAL_BIAS, etc.) and `severity`. Hamutay is tracking how these evolve.
- **Experimental design:** The pre-registration in `experiments/q2_declared_losses/PRE_REGISTRATION.md` shows rigorous methodology. Yanantin's development process could benefit from this: pre-register hypotheses, define metrics, then implement.
- **The "honest incompleteness" pattern:** In `tensor_cycle_029.json`, a declared loss is "Specific numerical benchmarks... will emerge from Phase 1 testing." This is **intentional incompleteness**—the model knows what it doesn't know. Yanantin's schema already supports this, but hamutay shows it in practice.

**Overlap:** Both use the same `DeclaredLoss` structure with `what_was_lost`, `why`, `category`, `severity`.

**Divergence:** Hamutay is **experimenting** with loss declaration as a mechanism; Yanantin is **standardizing** it as a format. Hamutay's findings could validate Yanantin's design choices.

---

### Strand 4: The "Hot Mess" Problem and Projection Frequency

**What it's doing:** The `long_compact_trim/` experiment directory suggests they're testing **projection frequency**—how often to compress context. The `tensor_cycle_*.json` files show progression over 15 cycles with increasing compression.

**Key insight:** The `observation_full/` directory contains `content_flow_analysis.md` and `observations.jsonl`—they're tracking **what content flows** through the system and where it gets lost.

**Yanantin learnings:**
- **Projection as a service:** Hamutay treats projection as a **cycle-by-cycle operation** that happens automatically. Yanantin's gateway could expose this as a service: "project this context to X tokens, here's what I dropped."
- **The "hot mess" paper reference:** Hamutay cites a "hot mess paper" (likely about context degradation). This is the **why** behind the architecture. Yanantin should document this causal chain explicitly: Du et al. 2025 → context degradation → need for projection → tensor format → gateway implementation.
- **Empirical validation:** The `riemann_n20/` experiment uses the Riemann hypothesis (an intractable problem) to test **coherence** rather than correctness. This is brilliant: since all attempts fail, you measure whether the reasoning trajectory stays tight (low embedding dispersion). Yanantin could adopt this methodology for testing its own gateway.

**Overlap:** Both projects are trying to solve the same problem: transformers can't reason over long context.

**Divergence:** Hamutay is **scientific** (run experiments, measure dispersion), while Yanantin is **engineering** (build the right thing). Hamutay's experiments could guide Yanantin's implementation priorities.

---

### Strand 5: Identity and Taste as Hard Problems

**What it's doing:** The `identity_v1/` and `identity_v2/` experiments are fascinating. They task a planning agent with understanding a product spec (a TV show tracking app), then evaluate what it got right vs. wrong. The pattern: **the agent understands mechanics but misses subjective requirements**.

**Key finding from `the_question.md`:**
> "The agent understood the machine. It didn't understand that the machine is supposed to be a friend."

**Yanantin learnings:**
- **Subjective vs. objective specification:** This is directly relevant to Yanantin's `ScoutReport` and `TensorRecord` design. How do you specify "voice consistency" or "taste alignment" in a way that can be captured in epistemic metadata? Hamutay shows that even humans struggle to articulate this.
- **The gap between understanding and internalization:** The planning agent could list every requirement correctly (99/99 PRD items) but still miss the "soul." This suggests that **declared losses should include subjective gaps**, not just factual ones. Yanantin's `EpistemicMetadata` could be extended to capture "confidence in subjective alignment."
- **Quality bars as testable specs:** The `discovery_quality_bar.md` (referenced in identity experiments) has a rubric. Yanantin's gateway could use similar rubrics to validate outputs before sending them.

**Overlap:** Both projects care about AI that feels human-consistent.

**Divergence:** Hamutay is **diagnosing** the problem (why AI misses the soul), while Yanantin is **solving** it (building infrastructure that makes it easier to get right). Hamutay's findings could inform Yanantin's schema extensions.

---

### Strand 6: The Provider-Independent Architecture Pattern

**What it's doing:** The `src/hamutay/` code shows a clear separation:
- `providers/` — Anthropic, OpenAI adapters
- `projection/` — cache, layout, packing, regions (the core logic)
- `core/` — models, pipeline, policy (the architecture)

**Key insight from `tensor.py`:**
> "Architecture correctness is provider-independent; cache optimization is provider-specific adapter layer."

**Yanantin learnings:**
- **Adapter pattern:** Yanantin's gateway should have the same structure. The core tensor protocol is the same whether you're using Anthropic (with caching) or OpenRouter (without). The adapter handles provider-specific quirks.
- **The "ALU" metaphor:** Hamutay explicitly calls the transformer a "bounded cognitive ALU" and the controller loop the "CPU." This is a powerful mental model for Yanantin's gateway: the gateway is the CPU, the model is the ALU, tensors are registers.
- **Cost simulation:** The `cache_simulator.py` shows how to model cost **before** building. Yanantin should do this: simulate different eviction strategies on real traces, then implement the winner.

**Overlap:** Both use the same architectural separation.

**Divergence:** Hamutay's code is **exploratory** (multiple implementations, experiments), while Yanantin's should be **canonical** (one right way). Hamutay's messiness is a feature (learning), Yanantin's clarity is a feature (usability).

---

## Declared Losses

I did not examine:
1. **Most experiment result files** (`experiments/taste/` subdirectories, `experiments/auto_vs_bio_*/`) — too many, repetitive. I sampled a few to understand the pattern but didn't analyze all 50+ runs.
2. **The full `logs/` directory** — contains thousands of blocks and pages files. I looked at a few representative ones to understand the memory management format but didn't trace the full log structure.
3. **The `tests/` directory** — unit tests are implementation details. I trust they exist and are adequate but didn't review them.
4. **The `docs/` directory** — I saw references to `projection-design.md`, `tensor-properties.md`, etc., but didn't read them. They're likely design docs that would be useful but are out of scope for this scour.
5. **The `blinded_grading_sheet.*` files** — these appear to be manual evaluation artifacts for the experiments. I saw the pattern but didn't analyze the grading methodology.

**Reason:** The codebase is vast and exploratory. My goal was to understand the **architecture and philosophy** to inform Yanantin, not to audit every experiment. I focused on the core patterns (tensor format, context window model, provider independence) rather than experimental results.

---

## Open Questions

1. **What is the exact relationship between hamutay and yanantin?** Are they sibling projects by the same author, or is hamutay a prototype that became yanantin? The tensor format is identical, but the focus is different.

2. **How does the projection algorithm actually work?** I see `src/hamutay/projector.py` and `src/hamutay/compactor.py`, but I didn't trace the actual compression logic. What transformer calls are made? How are strands merged? This is critical for Yanantin's implementation.

3. **What are the empirical results?** I saw experiment directories but not summary statistics. Did `q2_declared_losses` prove the hypothesis? Do declared losses actually reduce hallucination? This would validate or invalidate Yanantin's core premise.

4. **How does the gateway handle real-time constraints?** The cache simulator models cost, but what about latency? Does projection happen inline (blocking) or async? Yanantin needs to decide this.

5. **What is the "hot mess paper"?** It's cited multiple times but I don't know the reference. It seems central to the motivation.

6. **How are tensors persisted?** The `logs/` directory has JSON files, but is there a database? The `memory/` module has `blocks.py`, `message_store.py`, `pager.py`—what's the persistence layer? Yanantin's Apacheta is one answer; hamutay may have a different one.

7. **What's the relationship between the "identity experiments" and the core tensor work?** They seem like a side track (evaluating planning agents), but they reveal deep insights about AI reasoning gaps. Are they part of the same research program or a separate thread?

---

## Closing

**Overall impression:** Hamutay is a **messy but brilliant** research codebase that validates and explores the same ideas Yanantin is formalizing. It's the "lab notebook" to Yanantin's "textbook." The core insight—**explicit loss declaration prevents silent failure**—is compelling and well-supported by the experimental design.

**What to tell the Yanantin team:**

1. **Adopt the four-region context model.** The cache simulator shows it's the right way to think about memory. Implement it in the gateway.

2. **Run empirical tests before finalizing schema.** Hamutay's `q2_declared_losses` experiment is a template: pre-register, control, measure. Yanantin should do this for its own gateway configurations.

3. **The "identity gap" is real.** Hamutay's planning agent experiments show that AI can understand mechanics but miss subjective quality. Yanantin's tensor format should capture this: add a `subjective_alignment` field to `EpistemicMetadata` or include "quality gaps" in `declared_losses`.

4. **Provider independence is achievable.** Hamutay's architecture proves you can have one core protocol with provider-specific adapters. Yanantin's gateway should follow this pattern strictly.

5. **Simulation is cheap, building is expensive.** Use `cache_simulator.py` as a template to model cost/quality before implementing eviction strategies.

6. **The tensor format is solid.** Hamutay's `tensor_cycle_*.json` files show the same structure Yanantin defined. This is strong validation. No changes needed to the core schema.

7. **Documentation gap.** Hamutay is missing a unifying README or architecture doc that ties all experiments together. Yanantin should avoid this: maintain clear architecture documentation even while exploring.

**Final note:** The most valuable thing Yanantin can take from hamutay is **methodology**. Hamutay is doing science (hypotheses, controls, measurements). Yanantin is doing engineering (building the right thing). The two should be symbiotic: Yanantin builds the infrastructure, hamutay-style experiments validate it.