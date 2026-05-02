<!-- Chasqui Scour Tensor
     Run: 1921
     Model: deepseek/deepseek-v3.2 (DeepSeek: DeepSeek V3.2)
     Target: src/yanantin/chasqui
     Scope: introspection
     Cost: prompt=$2.52e-07/M, completion=$3.78e-07/M
     Usage: {'prompt_tokens': 17048, 'completion_tokens': 1617, 'total_tokens': 18665, 'cost': 0.0022782564, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 11592, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0022782564, 'upstream_inference_prompt_cost': 0.0016670304, 'upstream_inference_completions_cost': 0.000611226}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-02T17:23:59.513352+00:00
     GenerationID: gen-1777742588-PUXhSbUHOD6gPmsmQGKI
-->

# Tensor — Scour of `src/yanantin/chasqui`

### Preamble

I was pointed at the `chasqui/` directory — the "messenger" subsystem of Yanantin. What drew my attention first was the sheer density of orchestration logic. This isn't just a simple dispatcher; it's a multi-stage pipeline (Scout → Gleaner → Analyst → Verify → Respond) with sophisticated coverage tracking, cost-weighted model selection, cross-verification, and epistemic ledgering. The immediate standout was the self-referential nature: a system for observing codebases that is itself richly observed, with mechanisms to avoid observing its own navel (via coverage weights and vantage sampling).

### Strands

**Strand 1: The Pipeline as an Epistemic Engine**
The module structure reveals a deliberate processing chain. `scout.py` and `scourer.py` are the front-line observers. `gleaner.py` extracts verifiable claims. `analyst.py` performs cross-model topology detection. `coordinator.py` orchestrates the flow, and `attestation.py` bridges to an external epistemic ledger (Willay). This isn't just "run a model on some code"; it's a factory for producing, refining, and certifying observations. The pipeline assumes that truth emerges from convergence across cheap, noisy models (`analyst.py` lines 50-55: "3+ distinct models agreeing = structural truth"). This is a fascinating, pragmatic take on epistemic observability.

**Strand 2: Aggressive Defense Against Degeneration**
The code is paranoid about model failure modes. `coordinator.py` has `_is_degenerate_repetition` (line ~108) to catch looping output. `analyst.py` and `gleaner.py` have elaborate `is_garbage` functions (e.g., `analyst.py` lines 130-164) detecting corrupted Unicode, encoding artifacts, and nonsensically short claims. `scorer.py` sniffs for "kraken poo" (fabricated file paths). This defensive posture suggests hard-won experience with the unreliable substrates (LLMs) the system is built upon. The assumption is valid: you cannot trust your observers, so you must instrument their failures.

**Strand 3: Economics-Driven Exploration**
`model_selector.py` is elegantly simple: weight = `1.0 / cost`. Free models get a nominal cost to avoid infinite weight. The system is designed to answer "whether noticing more is worth paying more" (`coordinator.py` docstring). This economic lens is applied to exploration itself. `coverage.py` then layers a *temporal* economic logic: "stale coverage floats to the top." It tracks when files were last reviewed, weighting unreviewed code highest. This creates a dynamic attention budget, a clever solution to the problem noted in its docstring: the activity stream layer was never reviewed because scouts randomly sampled popular files.

**Strand 4: The Cairn as a Shared, Structured Memory**
All components read from and write to the `docs/cairn/` directory. Scouts drop markdown tensors there. `coverage.py` scans them to build its map. `gleaner.py` extracts claims from them. The cairn is the system's durable, inspectable memory. The `attestation.py` adapter then tries to elevate verified claims from this informal cairn into a formal, hash-chained epistemic ledger (Willay). This reveals an assumption: that informal, markdown-based observation logs are a sufficient intermediate representation for a more rigorous truth-tracking system. The connection feels aspirational but perhaps brittle.

**Strand 5: Self-Modification Through Open Questions**
The `analyst.py` identifies "open questions" from scout reports. The `--investigate` CLI flag (`__main__.py` line ~70) can dispatch new scouts to probe these questions. This closes the loop: the system not only observes but identifies its own uncertainties and can launch targeted missions to resolve them. It's a form of self-modifying exploration based on gaps in its own knowledge. This is a powerful, almost metacognitive feature.

### Declared Losses

*   **The `activity_map` integration in `coordinator.py` (lines ~60-110):** I saw it queries a DuckDB store for file timestamps but chose not to trace where that data comes from or how fresh it is. This feels like a secondary signal, and I focused on the core coverage logic.
*   **Full parsing of the regex patterns:** I noted the complex regexes for paths, sentences, and garbage detection across multiple files but did not manually verify their edge-case correctness. I assume they work well enough given the defensive coding elsewhere.
*   **The `willay` integration depth:** I saw `attestation.py` guards its imports and maps verdicts to T/I/F tuples, but I did not examine the Willay library itself to understand the semantics of the ledger it writes to. I treated it as a black-box output format.
*   **The `synthesis` scope in `scourer.py`:** It's listed in `VALID_SCOPES` but the template for it is truncated in the provided content. I did not infer its purpose.

### Open Questions

1.  **How does the system handle conflicting verifications?** If model A verifies a claim from model B as "CONFIRMED," but model C later verifies it as "DENIED," what is the resultant epistemic state? The analyst looks for agreement, but the ledger (`attestation.py`) seems to append each verification as a separate receipt. Is there a reconciliation layer?
2.  **What is the failure mode of the basename fallback in `coverage.py` (`_lookup_coverage`)?** If two different files in different directories share a basename (e.g., `src/foo/__init__.py` and `src/bar/__init__.py`), a scout's reference to `` `__init__.py` `` will ambiguously match both, potentially assigning an incorrect "last reviewed" timestamp. Is this a known, accepted trade-off?
3.  **Where is the "respond" logic fully implemented?** `coordinator.py` has `format_respond_prompt` imported and `dispatch_respond` is called from main, but the provided code snippets truncate before showing that function. How does a model respond to a prior tensor? Is it a dialogue, or a new observation?
4.  **Is there a feedback loop from `scorer.py` to `model_selector.py`?** The scorer evaluates model output quality (specificity, fabrication). It would be logical to deprioritize models that consistently score poorly, but I see no connection. Was this a deliberate omission?

### Closing

My overall impression is of a sophisticated, somewhat battle-hardened observatory. It acknowledges the fragility of its components (LLMs) and builds robustness through redundancy, economics, and time-aware scheduling. It's not just a tool; it's a microcosm of the project's thesis: building "composable tensor infrastructure for epistemic observability." The `chasqui` directory *is* that infrastructure in action.

To someone about to modify it: **Respect the feedback loops.** Changes to the scout prompt (`SCOUT_SYSTEM_PROMPT`) will ripple through claim extraction, analysis, and verification. Changes to the coverage algorithm will alter the exploration trajectory. This system has a lot of moving parts that are delicately balanced. Test changes not just for functionality, but for their impact on the emergent property of *coverage over time*. And always check if your change might break the system's ability to notice that it's broken.