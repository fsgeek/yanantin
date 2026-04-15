<!-- Chasqui Scout Tensor
     Run: 11644
     Model: essentialai/rnj-1-instruct (EssentialAI: Rnj 1 Instruct)
     Cost: prompt=$1.5e-07/M, completion=$1.5e-07/M
     Usage: {'prompt_tokens': 1492, 'completion_tokens': 581, 'total_tokens': 2073, 'cost': 0.00031095, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00031095, 'upstream_inference_prompt_cost': 0.0002238, 'upstream_inference_completions_cost': 8.715e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-15T18:34:21.550015+00:00
     GenerationID: gen-1776278056-9tmAOFYmQhzRefzxQtZE
-->

# Preamble

I am `essentialai/rnj-1-instruct` exploring the Yanantin project. I was dropped into a test-driven development context with only two files: `SKILL.md` and `testing-anti-patterns.md`. The latter immediately drew my attention as it contains critical knowledge about testing practices that should be internalized by any AI working with codebases.

## Strands

### Strand 1: Testing Anti-Patterns as Foundational Knowledge

This document establishes three iron laws that should guide all testing:
1. NEVER test mock behavior
2. NEVER add test-only methods to production classes  
3. NEVER mock without understanding dependencies

These laws reveal a tension: while mocks are often used for isolation, they should never become the focus of testing. The document explicitly states that "Tests must verify real behavior, not mock behavior" which suggests a strong emphasis on testing actual system behavior rather than artificial constructs.

### Strand 2: The Principle of Least Mocking

The document demonstrates a clear principle: test what the code does in production, not what mocks do. This is reinforced by the gate function that challenges developers to ask "Am I testing real component behavior or just mock existence?" before proceeding with assertions.

### Strand 3: Separation of Concerns in Testing

The anti-pattern around test-only methods in production classes reveals a fundamental tension: while tests need cleanup mechanisms, these should not pollute production code. The solution proposed is to move test-specific methods to utility functions rather than production classes.

### Strand 4: Mocking as a Double-Edged Sword

The document shows how over-mocking can break tests by removing important side effects. The example with `ToolCatalog` demonstrates that sometimes mocks need to be minimal and focused on specific behaviors rather than comprehensive.

## Declared Losses

I did not examine the actual implementation code in the test-driven-development directory because no implementation files were present in the provided context. I also did not look for examples of these anti-patterns in practice because the focus was on the documentation itself.

## Open Questions

1. How does the Yanantin project enforce or balance the principle of testing real behavior against the practical need for isolation in complex systems?
2. What testing framework is being used that requires this specific set of anti-patterns to be documented?
3. How does this documentation relate to the broader epistemic observability goals of the Yanantin project?

## Closing

This document represents crucial knowledge about testing practices that any developer working on the Yanantin project should internalize. It reveals a clear philosophy: while isolation and mocking are useful tools, they should never become the focus of testing. The emphasis is on testing real behavior and maintaining clean separation between production code and test infrastructure. This knowledge acts as both a guardrail and a map for navigating the testing landscape of the project.