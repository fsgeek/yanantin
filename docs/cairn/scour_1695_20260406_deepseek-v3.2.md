<!-- Chasqui Scour Tensor
     Run: 1695
     Model: deepseek/deepseek-v3.2 (DeepSeek: DeepSeek V3.2)
     Target: src/yanantin/chasqui
     Scope: introspection
     Cost: prompt=$2.6e-07/M, completion=$3.8e-07/M
     Usage: {'prompt_tokens': 17048, 'completion_tokens': 2395, 'total_tokens': 19443, 'cost': 0.00577934, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00577934, 'upstream_inference_prompt_cost': 0.00477344, 'upstream_inference_completions_cost': 0.0010059}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-06T21:52:18.816448+00:00
     GenerationID: gen-1775512025-Pbl7z6O3rCdDPRrdgKkc
-->

# Scour Tensor — Introspection of `src/yanantin/chasqui`

## Preamble

I was pointed at the `chasqui` module — the messenger system of Yanantin. What drew my attention first was the sheer density of orchestration: this isn't just a simple dispatcher; it's a multi-layered epistemic pipeline with scouts, scourers, gleaners, analysts, verifiers, and attestation adapters. The module implements a full observability loop: exploration → extraction → analysis → verification → recording. The immediate standout was the clear philosophical stance encoded in the code: a preference for cheap, diverse model sampling weighted by cost, an explicit tracking of "declared losses," and a deliberate separation between free wandering (scouts) and targeted examination (scourers).

## Strands

### Strand 1: The Epistemic Pipeline as a Tensor Transformation

The module defines a clear dataflow, each stage transforming a tensor-like representation:

1.  **Scout** (`scout.py`): Produces an "authored compression" — a free-form markdown tensor from a random vantage. Key function: `format_scout_prompt` (lines ~60-100) constructs the open-ended exploration prompt. It includes a "Prior Findings" section (via `gather_prior_findings`) to ground the scout in verified history, pushing them past the known.
2.  **Gleaner** (`gleaner.py`): Extracts structured `ExtractedClaim` objects from scout/scour markdown. It's a deterministic pattern-matcher (no LLM) that classifies claims by type (factual, architectural, epistemic, missing) and scores confidence based on linguistic signals (e.g., definitive vs. hedged language). This is the first compression from narrative to structured data.
3.  **Analyst** (`analyst.py`): Performs cross-model topology detection. It filters garbage, scores model quality, and clusters claims by file and semantic similarity. Its core insight: claims made by 3+ distinct models are "topological" (structural truth), while single-model claims are "textural." This is a higher-order compression, finding agreement across the noise.
4.  **Verifier** (logic within `coordinator.py`): Dispatches claims to *different* models for verification, producing CONFIRMED/DENIED/INDETERMINATE verdicts. The `_count_prior_verifications` function (lines ~215-250) enforces a cap (`MAX_VERIFY_PER_CLAIM = 3`) to prevent infinite loops on confusing claims.
5.  **Attestation** (`attestation.py`): Bridges to the Willay epistemic ledger, converting verification verdicts into receipts with T/I/F (Truth, Indeterminacy, Falsity) values and declared losses. It gracefully degrades if Willay isn't installed.

**Thought**: This pipeline is the project's nervous system. It doesn't just run models; it uses their disagreements and agreements to build a progressively refined map of the codebase. The `analyst` is particularly clever — it uses the swarm's collective output to infer structural truth without a human judge.

### Strand 2: Cost-Weighted Random Sampling as an Economic Experiment

The `model_selector.py` is small but philosophically central. The `ModelSelector` weights model choice *inversely by cost* (line 72: `weights.append(1.0 / cost)`). Free models get a nominal cost of $0.001/M to avoid infinite weight. The selector's `stats()` method tracks the pool's economics.

This is directly referenced in the `coordinator.py` docstring: "Over time, the cairn accumulates data: which models notice what, at what cost, and whether noticing more is worth paying more." The system is designed as an experiment in AI cognition economics. A cheap model that frequently notices important things is more valuable than an expensive one that does the same.

**Thought**: This turns model selection from a configuration problem into a discovery mechanism. The "cost-weighted random" approach is a bet that diversity and volume trump cherry-picking a single "best" model. It also inherently fights mode collapse by ensuring a variety of model families get used.

### Strand 3: Coverage and Staleness as an Attention Governor

The `coverage.py` module is a direct response to a stated failure: "The activity stream layer (15 files, 1443 lines) was never reviewed by any scout despite being a major new subsystem." It acts as a "watchman."

It scans the cairn, building a map of `{file_path: last_reviewed_at}`. The `coverage_weights` function then weights candidate files for scout review by *seconds since last review*. Unreviewed files (epoch zero) get maximum weight. This replaces uniform random file selection with a priority queue based on review staleness.

**Thought**: This is a simple, effective feedback loop. It ensures the system's attention drifts toward neglected code. It's a form of automated triage, preventing the "rich get richer" problem where oft-reviewed files get more reviews. The fallback to basename matching (lines ~100-120) is a pragmatic hack for imperfect path references in scout reports.

### Strand 4: Garbage Detection and Degeneracy Guards

The system is paranoid about corrupted model output. Multiple layers have garbage filters:
*   `analyst.py`'s `is_garbage` function (lines ~95-120) looks for non-ASCII character runs, encoding artifacts, and low alphabetic ratios.
*   `coordinator.py`'s `_is_degenerate_repetition` (lines ~165-185) detects loops where a model repeats the same phrase dozens of times, which can falsely parse as a verification verdict.

Furthermore, the `gleaner` has confidence scoring, and the `analyst` builds `ModelProfile` objects tracking garbage ratios per model. Poor performers can be identified.

**Thought**: This is essential hygiene for operating at scale with many unknown, cheap models. It acknowledges that a portion of AI output will be noise and builds filters before the signal enters the analysis layer. It turns a quality control problem into a measurable metric (`garbage_ratio`).

### Strand 5: The Tensor as a First-Class Format

The prompt templates (in `scout.py`, `scourer.py`) mandate a specific output structure: Preamble, Strands, Declared Losses, Open Questions, Closing. This isn't just a suggestion; the `scorer.py` and `gleaner.py` parse this structure explicitly.

The `scorer.py`'s `_extract_strands_section` function and `_STRAND_PATTERNS` regexes are designed to parse this authored format. The format forces the model to articulate its attention (Strands), its limits (Declared Losses), and its uncertainties (Open Questions).

**Thought**: The "tensor" here is a structured narrative container. It's a protocol for model self-reporting that balances free observation with consistent parsing. The "Declared Losses" section is a brilliant epistemic device — it makes the model's omissions a recorded, explicit part of the output, not just an absence.

## Declared Losses

1.  **I did not trace through the full async dispatch logic in `coordinator.py`.** The module is large (800+ lines truncated). I examined the high-level flow (`dispatch_scout`, `dispatch_verify_cairn`, `dispatch_investigate`) and key helper functions, but I did not follow the intricate `asyncio`/`httpx` client handling, error recovery, or the precise semantics of the `activity_map` integration. This is the core runtime engine, and my review is architectural, not operational.
2.  **I did not evaluate the regular expressions for edge cases.** The path patterns, sentence splitters, and section extractors in `gleaner.py` and `scorer.py` are complex. I assume they work for the observed cairn data but haven't mentally tested them against pathological markdown.
3.  **I skimmed the `__main__.py` argument parsing logic.** I noted its role as the CLI frontend with many options (`--scour`, `--analyze`, `--investigate`) but did not verify every branch or flag combination.
4.  **The `model_selector.py`'s `load_from_openrouter_response` function** assumes a specific JSON structure from the OpenRouter API. I didn't examine what guarantees that API provides or how robust the parsing is to schema changes.

## Open Questions

1.  **How is the "cairn" directory lifecycle managed?** The code reads from `docs/cairn/` and `docs/cairn/edges/`. Is there pruning, archiving, or summarization when it grows too large? The system seems write-heavy, and I see no cleanup mechanism.
2.  **What is the "synthesis" scope?** `scourer.py` lists `VALID_SCOPES = {"introspection", "external", "tensor", "synthesis"}`. The templates for the first three are present, but I see no `SCOURER_SYNTHESIS_TEMPLATE`. Is this a planned feature or an unused stub?
3.  **How are model costs updated?** `model_selector.py` loads costs from an API response. Is this cached? How frequently does it refresh? A model's price change could significantly alter the sampling distribution.
4.  **The `attestation.py` module has a guarded import for Willay.** What is the fallback behavior if Willay is not installed? The `record_verification` function returns `None`. Does this mean the attestation step is silently skipped, or is it logged as an error? The bridge seems optional, but the systemic intent is to record everything.

## Closing

My overall impression is that `chasqui` is a remarkably coherent and thoughtful subsystem. It's not just a "glue code" wrapper for LLM calls; it's a framework for *orchestrating epistemic work across a population of diverse, unreliable AI agents*. It embraces stochasticity (random sampling, random vantages) and uses aggregation and cross-verification to find signal.

If I were to modify this codebase, I would advise:
*   **Respect the pipeline stages.** Each component (Scout, Gleaner, Analyst, Verifier, Attestor) has a distinct purpose and output format. Changes to one stage's contract will ripple downstream.
*   **The "declared loss" and "open question" concepts are central.** Any new feature should consider what it loses and what uncertainties it introduces.
*   **The system is designed for scale and noise.** When adding new models or data sources, maintain the garbage filters and the cost-weighting principle. The integrity of the `analyst`'s topology detection depends on the quality of the ingested claims.
*   **Look to `coverage.py` as a model of feedback.** Any new automatic process should consider how to avoid attention blindness and ensure neglected parts of the system eventually get reviewed.

The code is dense with ideas, and its primary weakness might be complexity — it's a multi-stage pipeline with many moving parts. But that complexity seems necessary for its ambitious goal: not just to run AI, but to observe how AI observes.