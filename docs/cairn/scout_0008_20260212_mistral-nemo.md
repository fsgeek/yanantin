<!-- Chasqui Scout Tensor
     Run: 8
     Model: mistralai/mistral-nemo (Mistral: Mistral Nemo)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 824, 'completion_tokens': 126, 'total_tokens': 950, 'cost': 5.438e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 5.438e-05, 'upstream_inference_prompt_cost': 3.296e-05, 'upstream_inference_completions_cost': 2.142e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-12T00:51:36.860496+00:00
-->

### Verdict
CONFIRMED

### Evidence
The docstring of the `bootstrap` function in `src/yanantin/apacheta/operators/bootstrap.py` states: "Returns the bootstrap record and the selected tensors." (Line 29)

### Reasoning
The claim accurately describes the return value of the `bootstrap` function in the given file. The function indeed returns a tuple containing both the `BootstrapRecord` and the selected tensors, confirming the stated claim.

### Declared Losses
None. The claim is solely based on the source code, which is clearly visible and understood.