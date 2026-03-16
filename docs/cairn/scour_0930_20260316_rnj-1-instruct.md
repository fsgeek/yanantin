<!-- Chasqui Scour Tensor
     Run: 930
     Model: essentialai/rnj-1-instruct (EssentialAI: Rnj 1 Instruct)
     Target: src/yanantin/chasqui
     Scope: introspection
     Cost: prompt=$1.5e-07/M, completion=$1.5e-07/M
     Usage: {'prompt_tokens': 16317, 'completion_tokens': 1530, 'total_tokens': 17847, 'cost': 0.00267705, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00267705, 'upstream_inference_prompt_cost': 0.00244755, 'upstream_inference_completions_cost': 0.0002295}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-16T11:35:19.494013+00:00
-->

# Chasqui Coordinator — the heartbeat of Yanantin.

## Preamble

The codebase structure immediately draws attention to its modern design: a
mixture of Python, configuration, and documentation files organized into
modules and submodules. The presence of `__init__.py` files and consistent
naming conventions (e.g., `yanantin/chasqui.py`) suggests a well-maintained
codebase with clear module boundaries.

The `__main__.py` entry point and the presence of `uv run` commands in the
documentation indicate a focus on developer productivity and CLI-driven
workflows.

## Strands

### Project Structure and Organization

The first observation is the clear hierarchical structure of the codebase,
with modules like `yanantin.chasqui`, `yanantin.apacheta`, and `yanantin.query`.
Each module has a dedicated directory and follows Python packaging conventions
with `__init__.py` files, which makes it easy to reason about dependencies and
code ownership.

The `docs/cairn` directory stands out as a central repository for observed
knowledge and artifacts — likely where the results of scouts are stored. This
design supports the project's epistemic observability goal by making
observations durable and queryable.

### Cost-Weighted Model Selection

In `model_selector.py`, the cost-weighted random selection logic is a clever
mechanism for balancing resource usage and coverage. By favoring cheaper models
while still allowing occasional use of more capable (though costlier) models,
the system optimizes for both throughput and accuracy. The exclusion of models
like `openrouter/auto` shows intentional filtering to avoid unreliable models.

### Activity Stream and Coverage Tracking

The `coverage.py` module reveals a sophisticated feedback loop: the system
monitors what files have been reviewed and uses that information to guide
future selections. Files with high "stale" coverage (long since last reviewed)
are prioritized, which ensures that neglected parts of the codebase receive
attention. This is a strong mechanism for preventing knowledge drift and
maintaining a healthy feedback loop between exploration and review.

### Verification and Attestation

The `attestation.py` module demonstrates a clear commitment to epistemic
accountability. By mapping Chasqui's verification results to Willay's
epistemic receipts, the system creates an auditable trail of truth and error.
The inclusion of declared losses (e.g., single-LLM verification, temporal code
drift) shows awareness of the limitations of automated verification and
provides transparency about where human review might be needed.

### Garbage Detection in Model Output

The `_is_degenerate_repetition` function in `coordinator.py` is a small but
critical piece of robustness. It guards against models that produce
non-informative output (e.g., looping endlessly without changing their
"opinion"). By identifying such behavior and penalizing it, the system
prevents wasted effort on unhelpful outputs.

### File Selection and Context

In `scout.py`, the `select_files_for_scout` function shows careful attention
to balancing exploration and coverage. The use of `coverage_weights` ensures
that files with high stale coverage get selected, while also allowing uniform
random selection when no coverage data is available. This dual strategy
prevents the system from getting stuck in a feedback loop of only reviewing
the same files.

Additionally, the consideration of `activity_map` to boost recently-modified
files adds a temporal dimension to the selection process, ensuring that the
system stays aligned with the current state of the codebase.

## Declared Losses

### Human-Readable Documentation Limitations

The `__main__.py` file's command-line interface is thorough, but it lacks
detailed usage examples for some commands (e.g., `--respond` and `--scour`).
This is a minor loss, as it would be helpful for users to see concrete
examples of how to use these features.

### Limited Integration with External Tools

While the project uses modern tools like `uv` and `uv run`, there's no
explicit integration with CI/CD pipelines or monitoring systems in the
codebase itself. This suggests that orchestration might happen outside the
codebase, which could be a loss for long-term maintainability.

### Lack of Model Versioning

The `model_selector.py` module loads models from OpenRouter without explicit
versioning or provenance tracking. This means that if OpenRouter changes the
API or model behavior, the system might fail without notice. A loss of
reproducibility could occur if model behavior changes unexpectedly.

## Open Questions

### How does the system handle model failures during verification?

If a verification fails (e.g., a model is down or returns corrupted output),
does the system fall back to another model automatically? Is there a retry
mechanism? What happens if all models fail?

### How is the trade-off between cost and accuracy tuned?

The cost-weighted selection in `model_selector.py` uses a simple inverse-cost
weighting scheme. Is there a mechanism to dynamically adjust the weights based
on performance (e.g., if cheaper models are consistently producing garbage,
should their weight be reduced further)?

### How does the system handle conflicting observations from different models?

In the `analyst.py` module, the cross-model topology detection could help,
but what happens when multiple models disagree? Is there a way to surface
and resolve these conflicts, or are they treated as noise?

### How are models' hallucinations detected and mitigated?

The `_is_degenerate_repetition` function detects loops, but are there other
forms of hallucination (e.g., fabricating file paths, inventing dependencies)
that the system doesn't currently handle?

### How is the coverage map updated in real time?

The `coverage.py` module scans the cairn periodically, but is there a way to
update the coverage map incrementally as new scout reports arrive, rather than
waiting for a full scan?

## Closing

The Chasqui coordinator demonstrates a thoughtful blend of practical
engineering and epistemic rigor. The system is designed to be robust, with
mechanisms to detect and handle garbage output, prioritize coverage of
neglected files, and maintain a durable record of observations. The use of
cost-weighted selection and coverage tracking ensures that the system scales
effectively while maintaining attention to the most important parts of the
codebase.

The project’s focus on epistemic observability — through features like
attestation and analyst-driven cross-model pattern detection — elevates it
beyond a simple codebase explorer. It becomes a system that not only observes
but also reasons about its own knowledge, providing a foundation for
self-improving and self-correcting workflows.

For someone about to modify the codebase, I would suggest paying close
attention to the coverage tracking and model selection logic — these are the
pieces that determine how knowledge is discovered and maintained over time.
The garbage detection and verification attestation are also critical for
ensuring that the system continues to function reliably as models evolve or
fail.

The system is not perfect — there are small gaps in documentation and
integration with external tools — but these are surface-level concerns that
don’t undermine the underlying design. The core idea of a self-optimizing,
epistemically aware explorer is powerful and worth preserving.
