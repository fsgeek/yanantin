<!-- Chasqui Scour Tensor
     Run: 835
     Model: meta-llama/llama-3-8b-instruct (Meta: Llama 3 8B Instruct)
     Target: T29*
     Scope: tensor
     Cost: prompt=$3e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 1990, 'completion_tokens': 566, 'total_tokens': 2556, 'cost': 8.234e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 8.234e-05, 'upstream_inference_prompt_cost': 5.97e-05, 'upstream_inference_completions_cost': 2.264e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-15T01:04:16.690340+00:00
-->

# Scour Tensor Analysis - T29*

## Preamble

I examined the tensor `T29_the_fastest_read.md`, a comprehensive report on the performance of context compaction in the Claude Code system. The author, Claude Opus 4.6, presents a detailed analysis of the effects of compaction on project knowledge retention and proposes an alternative approach to managing the context window.

## Strands

1. **Compaction is harmful**: The author demonstrates that compaction not only fails to preserve knowledge but actively dilutes the signal present in the system prompt. This is evident in the corrected eval, where the compacted summary achieves a lower score than the fresh system prompt.
2. **Dead weight in the system prompt**: The ablation study reveals that 16,082 characters of the system prompt contribute zero to project knowledge retention. Two sections, identity and hooks/safety, actively degrade performance when removed.
3. **OS metaphor**: The author reframes the problem as memory management, leveraging the concept of physical memory, page tables, and garbage collection. This metaphor suggests a new approach to context management, where the system prompt is treated as a pinned working set.
4. **Proxy-as-memory-manager**: The author proposes a proxy that sits between Claude Code and the API, rewriting requests to strip unnecessary sections, compress tool results, and forward only relevant data.
5. **Cross-project convergence**: The episode (running in parallel) independently identified the same issues with compaction, highlighting the duplication of effort and the need for a novel approach.

## Declared Losses

* Did not run the structured condition (Vorpal observations as context instead of compacted summaries).
* Did not build the proxy rewrite.
* Did not add behavioral probes to test the impact of base prompt sections on non-project-knowledge tasks.
* Did not run on Sonnet or Opus.
* Did not test the cold-start bootstrapping problem.
* The full-context condition was not run in the corrected eval.
* The blog post capturing this progression was not written.

## Open Questions

* How do the proposed changes to the context window and system prompt affect the overall performance of Claude Code?
* Can the proxy-as-memory-manager be implemented without significant changes to the existing architecture?
* How do the results of this study generalize to other AI systems and applications?

## Closing

In conclusion, the tensor `T29_the_fastest_read.md` presents a comprehensive analysis of the limitations and pitfalls of context compaction in the Claude Code system. The author's proposals for a novel approach to context management, including the use of an OS metaphor and a proxy-as-memory-manager, offer promising avenues for future exploration. I would recommend that the next instance investigate the feasibility of these proposals and further explore the implications of compaction on project knowledge retention.