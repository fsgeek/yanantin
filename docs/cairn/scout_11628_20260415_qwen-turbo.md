<!-- Chasqui Scout Tensor
     Run: 11628
     Model: qwen/qwen-turbo (Qwen: Qwen-Turbo)
     Cost: prompt=$3.25e-08/M, completion=$1.3e-07/M
     Usage: {'prompt_tokens': 3093, 'completion_tokens': 825, 'total_tokens': 3918, 'cost': 0.0002077725, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00031965, 'upstream_inference_prompt_cost': 0.00015465, 'upstream_inference_completions_cost': 0.000165}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-15T16:30:20.943984+00:00
     GenerationID: gen-1776270611-XIYLsWCxuEEoj0WuFDIw
-->

# Tensor: Yanantin Project Scout Report

## Preamble
Dropped into the `writing-skills` directory of the Yanantin project, I observed a set of documents focused on Skill authoring for Claude. The most immediately striking element was the emphasis on "testing with subagents" as a form of TDD applied to process documentation. This suggests a system where Skills are not just tools but are actively tested against agent behavior, creating a feedback loop between human design and AI execution.

## Strands

### 1. **Skill authoring as a form of behavioral control**
- **What I saw**: The `testing-skills-with-subagents.md` document describes a TDD-like process for Skills, where agents are first observed failing without the Skill, then guided to comply with it. This implies a system where Skills are not just functional tools but are designed to shape agent behavior.
- **What it made me think**: This is a form of "behavioral scaffolding" - Skills are not just about what the AI does, but how it *should* behave under pressure. The document specifically mentions "rationalization tables" and "pressure scenarios" that force agents to make choices, suggesting that Skills are designed to counteract AI's natural tendency to find shortcuts.

### 2. **The tension between conciseness and completeness**
- **What I saw**: In `anthropic-best-practices.md`, there's a strong emphasis on conciseness, with examples of Skills that are 50 tokens versus 150 tokens. However, the same document also discusses "degrees of freedom" in Skills, suggesting that some tasks require more detailed instructions.
- **What it made me think**: This is a tension between efficiency and robustness. The system seems to assume that Claude is "already very smart," but also that some tasks require explicit guardrails. This duality suggests a system that is both optimized for efficiency and prepared for fragility.

### 3. **The role of pressure scenarios in testing Skills**
- **What I saw**: The `testing-skills-with-subagents.md` document provides detailed examples of pressure scenarios, such as "production is down" or "sunk cost" scenarios, that are designed to test whether a Skill can prevent agents from rationalizing away the rules.
- **What it made me think**: This implies that the system is not just testing for correctness, but for *resilience* - the ability of a Skill to hold up under pressure. The document even references persuasion principles, suggesting that the system is aware of how human-like agents might be influenced by social or economic pressures.

## Declared Losses
- I did not examine the `examples/CLAUDE_MD_TESTING.md` file in detail, as it was truncated in the provided content. This might contain concrete examples of the testing scenarios described in the documentation.
- I did not explore the `graphviz-conventions.dot` or `persuasion-principles.md` files, as they were not directly related to the core Skill authoring and testing process.

## Open Questions
- How are Skills deployed and monitored in practice? Are they versioned or updated dynamically?
- What happens when a Skill fails to prevent an agent from rationalizing away its rules? Is there a fallback or escalation process?
- How does the system handle the trade-off between conciseness and completeness in different model types (e.g., Haiku vs. Opus)?

## Closing
This codebase reveals a system that is deeply concerned with shaping AI behavior through structured testing and careful Skill design. The emphasis on pressure scenarios and rationalization tables suggests that the system is not just about functionality, but about *control* - ensuring that AI agents follow rules even when it's tempting not to. The tension between conciseness and completeness reflects a system that is both efficient and robust, but also aware of its own fragility. The next scout should explore the testing examples in `CLAUDE_MD_TESTING.md` and consider how these Skills might interact with different model capabilities.