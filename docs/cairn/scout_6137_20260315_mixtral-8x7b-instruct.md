<!-- Chasqui Scout Tensor
     Run: 6137
     Model: mistralai/mixtral-8x7b-instruct (Mistral: Mixtral 8x7B Instruct)
     Cost: prompt=$5.4e-07/M, completion=$5.4e-07/M
     Usage: {'prompt_tokens': 10469, 'completion_tokens': 192, 'total_tokens': 10661, 'cost': 0.00575694, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00575694, 'upstream_inference_prompt_cost': 0.00565326, 'upstream_inference_completions_cost': 0.00010368}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-15T13:29:34.945952+00:00
     Dispatch: verify
     Claim: Test functions are rarely defined inside source modules like `coordinator.py`; they typically reside in dedicated test files.
     ClaimFile: src/yanantin/chasqui/coordinator.py
     ClaimBy: stepfun/step-3.5-flash
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0268_20260213_step-3.5-flash.md
-->

### Verdict
INDETERMINATE

### Evidence
The file `src/yanantin/chasqui/coordinator.py` does not contain any test functions.

### Reasoning
The claim states that "Test functions are rarely defined inside source modules like `coordinator.py`; they typically reside in dedicated test files." However, the file `coordinator.py` does not contain any test functions at all, let alone rarely. It primarily contains functions related to coordinating the execution of models, such as `dispatch_scout`, `write_to_cairn`, and `dispatch_verify`. Therefore, I cannot confirm or deny the claim as it is written because it is not applicable to this specific file.

### Declared Losses
I can only verify the contents of the provided file and not the behavior of the code in other files or at runtime.