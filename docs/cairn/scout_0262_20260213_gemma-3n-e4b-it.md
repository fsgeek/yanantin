<!-- Chasqui Scout Tensor
     Run: 262
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 11976, 'completion_tokens': 106, 'total_tokens': 12082, 'cost': 0.00024376, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00024376, 'upstream_inference_prompt_cost': 0.00023952, 'upstream_inference_completions_cost': 4.24e-06}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-13T11:07:16.785192+00:00
-->

### Verdict
CONFIRMED

### Evidence
The file states: "Integration tests for ArangoDB backend against REAL ArangoDB instance."

### Reasoning
The file's docstring explicitly states that the tests are for "Integration tests for ArangoDB backend against REAL ArangoDB instance." This directly confirms the claim that the file's docstring states the file is an integration test for a real ArangoDB instance.

### Declared Losses
The claim is fully supported by the provided file content.