<!-- Chasqui Scout Tensor
     Run: 6925
     Model: nousresearch/hermes-2-pro-llama-3-8b (NousResearch: Hermes 2 Pro - Llama-3 8B)
     Cost: prompt=$1.4e-07/M, completion=$1.4e-07/M
     Usage: {'prompt_tokens': 1143, 'completion_tokens': 286, 'total_tokens': 1429, 'cost': 0.00020006, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00020006, 'upstream_inference_prompt_cost': 0.00016002, 'upstream_inference_completions_cost': 4.004e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-20T03:55:30.784519+00:00
     Dispatch: verify
     Claim: **Evidence from Files:** - `scout_0800_20260215_gemma-3n-e4b-it.md` discusses the `bootstrap` function’s role in selecting tensors for a "context budget." A self-referential claim like this one would 
     ClaimFile: docs/cairn/scout_0800_20260215_gemma-3n-e4b-it.md
     ClaimBy: mistralai/mistral-small-creative
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1355_20260218_mistral-small-creative.md
-->

### Verdict
DENIED

### Evidence
The claim states that the file discusses the `bootstrap` function's role in selecting tensors for a "context budget." However, the provided file does not mention or imply any self-referential claim. Instead, it defines the `bootstrap` function and its return values, but does not discuss a "context budget" or imply that its truth value is undefined.

### Reasoning
The file defines the `bootstrap` function and its return values, which are the `BootstrapRecord` and a list of `TensorRecord` objects. However, the claim's mention of a "context budget" is not supported by the provided file. The file does not discuss a "context budget" or imply that the function's truth value is undefined. The function does select tensors based on the provided `tensor_ids` or by listing all available tensors if none are provided, but this selection process is not explicitly related to a "context budget" in the provided file.

### Declared Losses
I could not determine the exact nature of the "context-bound" selection without examining the implementation of the `interface.list_tensors()` and `interface.get_tensor(tid)` methods, or further code within the `bootstrap` function. This limitation does not affect the accuracy of my verdict on the claim, as the provided file does not discuss a "context budget" or imply that its truth value is undefined.