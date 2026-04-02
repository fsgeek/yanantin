<!-- Chasqui Scour Tensor
     Run: 1527
     Model: arcee-ai/trinity-large-thinking (Arcee AI: Trinity Large Thinking)
     Target: /home/tony/projects/tinkuy
     Scope: external
     Cost: prompt=$2.5e-07/M, completion=$9e-07/M
     Usage: {'prompt_tokens': 230549, 'completion_tokens': 2083, 'total_tokens': 232632, 'cost': 0.05951195, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.05951195, 'upstream_inference_prompt_cost': 0.05763725, 'upstream_inference_completions_cost': 0.0018747}, 'completion_tokens_details': {'reasoning_tokens': 393, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-02T06:19:48.704019+00:00
     GenerationID: gen-1775110753-BTVNYqylRjAYyGuNp1RG
-->


## Preamble

This codebase, named **tinkuy**, appears to be experimental infrastructure for running ablation studies and prompt engineering experiments with large language models. It's built around a system of "regions" (SYSTEM, TOOLS, DURABLE, EPHEMERAL) that manage different types of content blocks, with a strong emphasis on checkpoint-based session tracking and telemetry. The project seems to be exploring how instruction adherence varies with different prompt configurations, using Claude Code as an agent for systematic file exploration and analysis.

My initial impression is that tinkuy shares philosophical DNA with Yanantin—both are concerned with structured interaction between humans and AI, both use tensor-like representations (tinkuy's blocks vs Yanantin's tensors), and both emphasize systematic experimentation. However, tinkuy appears more focused on ablation methodology and prompt engineering, while Yanantin's duality framework suggests a broader architectural vision.

## Strands

### Strand 1: Region-Based Content Management
tinkuy organizes content into distinct regions (SYSTEM, TOOLS, DURANT, EPHEMERAL) with clear semantic boundaries. This is reminiscent of Yanantin's tensor structure but more operational—each region has specific rules about what can be stored and how it's accessed. The SYSTEM region contains immutable system prompts, TOOLS holds tool definitions, DURANT seems to be for persistent data, and EPHEMERAL for transient conversation.

**Yanantin could learn:** This regional abstraction provides a clean separation of concerns that could inform Yanantin's tensor dimensions. The checkpoint mechanism (with turn-based updates) offers a concrete implementation of state persistence that Yanantin might adapt for its own session tracking.

**Problems solved:** tinkuy has solved the problem of organizing heterogeneous content types with different access patterns and lifetimes, something Yanantin's tensor model could incorporate.

### Strand 2: Ablation Experiment Infrastructure
The codebase contains extensive infrastructure for running ablation experiments, including:
- `src/arbiter/ablation.py` with `AblationConfig` class
- `src/arbiter/scoring.py` for probe evaluation
- Experiment directories with config files (`config.py`) and block variants
- Telemetry and checkpoint systems for tracking experiment progress

**Yanantin could learn:** The systematic approach to experimental design—using covering arrays to generate ablation combinations, storing results in structured JSONL files, and maintaining detailed telemetry—could be adapted for Yanantin's own evaluation framework. The separation of baseline, removal, and rewriting conditions is particularly elegant.

**Problems solved:** tinkuy has built a complete pipeline for running controlled experiments with LLMs, including configuration management, execution tracking, and result storage—addressing reproducibility challenges.

### Strand 3: Block Rewriting vs Removal
The user's query specifically asks about supporting both block REMOVAL (removing instruction blocks entirely) and REWRITING (replacing text while keeping the block present). The infrastructure appears to support both: ablation conditions include "tone-concise removed" (removal) and "tone-concise rewritten declarative" (rewriting).

**Yanantin could learn:** The declarative rewrite approach aligns well with Yanantin's focus on complementary duality—transforming instruction style while preserving semantic content. This could be a powerful technique for exploring instruction adherence without losing critical constraints.

**Problems solved:** tinkuy has recognized that ablation isn't just about removal; rewriting can isolate specific linguistic features (like imperative vs declarative mood) while maintaining overall structure.

### Strand 4: Probe-Based Evaluation
The project uses "probes" (test cases) to evaluate instruction adherence, with scoring mechanisms in `scoring.py`. There are references to "probe batteries" and evaluation across multiple models.

**Yanantin could learn:** The systematic probe-based evaluation approach could inform Yanantin's own assessment framework. The use of covering arrays to test multiple factors simultaneously is a sophisticated experimental design that Yanantin could adopt.

**Problems solved:** tinkuy has created a methodology for quantifying instruction adherence across different prompt configurations, moving beyond anecdotal evaluation.

### Strand 5: Model Configuration and Telemetry
The system prompts reveal use of Claude Haiku 4.5 and Opus 4.6, with OpenRouter IDs referenced. There's extensive telemetry logging (`telemetry.jsonl`) and checkpointing (`checkpoint.json`).

**Yanantin could learn:** The detailed telemetry capture (including access patterns, fault counts, and timestamps) provides a rich dataset for analyzing system behavior. Yanantin's tensor-based approach could benefit from similar granular tracking.

**Problems solved:** tinkuy has addressed the challenge of monitoring complex, multi-step LLM interactions with comprehensive logging.

### Strand 6: Experimental Design Patterns
The directory structure shows multiple experimental runs (`prd-benchmark-01`, `prd-benchmark-02`, etc.) with consistent organization: `pages`, `sessions`, `tensors`, `gateway.log`, `wire.jsonl`. This suggests a template-based approach to experiment management.

**Yanantin could learn:** The standardized experiment directory structure makes it easy to compare results across runs and could be adapted for Yanantin's own experimental framework.

**Problems solved:** tinkuy has created a reproducible experiment template that ensures consistency across multiple runs and conditions.

## Declared Losses

I chose **not** to examine:
1. **The actual content of all 1000+ block files** in `/home/tony/projects/tinkuy/.tinkuy-data/pages` — while comprehensive, this would be too voluminous and the patterns are likely consistent across files.
2. **The full implementation details of `src/arbiter/conflict_detector.py`** — I focused on the ablation infrastructure rather than the conflict detection mechanism itself.
3. **The LaTeX paper draft in `docs/paper/social_register/`** — this is more about the research findings than the experimental infrastructure.
4. **The `tinkuy` package's `__main__.py` and CLI entry points** — my focus was on the ablation experiment infrastructure rather than the command-line interface.

I also avoided diving into the **tensor file formats** (`*.tensor.json`) in `/home/tony/projects/tinkuy/.tinkuy-data/tensors` since the user's questions were more about the experimental methodology than the specific tensor representations.

## Open Questions

1. **How exactly are covering arrays generated?** The infrastructure mentions "covering arrays" for ablation combinations, but I couldn't find the specific implementation. Is it using a library like `tmar` or a custom solution?

2. **What's the exact probe scoring mechanism?** The `scoring.py` file exists, but I couldn't access its contents. Is it binary (correct/incorrect) or does it use a continuous score?

3. **How are model API calls actually made?** The system prompts mention OpenRouter IDs, but I couldn't find the API client implementation. Is it using `litellm`, `anthropic`, or a custom wrapper?

4. **What's the relationship between tinkuy and arbiter?** The codebase references both "tinkuy" and "arbiter" — are they separate projects or different components of the same system?

5. **How are the experimental results analyzed?** The data files exist, but I couldn't find analysis scripts. Is there a separate analysis pipeline?

## Closing

tinkuy presents a sophisticated experimental infrastructure for ablation studies in prompt engineering, with strong parallels to Yanantin's goals of systematic human-AI interaction. The region-based content management, checkpoint-driven state tracking, and systematic ablation methodology are particularly relevant.

For the Yanantin team, I'd highlight:
- The **regional abstraction** could inform Yanantin's tensor dimensions
- The **block rewriting approach** offers a powerful technique for isolating linguistic features while preserving semantic content
- The **telemetry and checkpoint system** provides a model for tracking complex interactions
- The **covering array experimental design** is a best-in-class approach for multifactorial experiments

The main gap I see is that tinkuy appears to be more narrowly focused on prompt ablation, while Yanantin's duality framework suggests broader architectural ambitions. However, the patterns here are highly transferable. I'd recommend studying tinkuy's ablation infrastructure as a concrete implementation that Yanantin could adapt and extend for its own experimental needs.

The codebase demonstrates that thoughtful experimental design and systematic evaluation are achievable, and many of its patterns could enhance Yanantin's own development without requiring reinvention.