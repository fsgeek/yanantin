<!-- Chasqui Scout Tensor
     Run: 5755
     Model: meta-llama/llama-3-8b-instruct (Meta: Llama 3 8B Instruct)
     Cost: prompt=$3e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 3656, 'completion_tokens': 149, 'total_tokens': 3805, 'cost': 0.00011564, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00011564, 'upstream_inference_prompt_cost': 0.00010968, 'upstream_inference_completions_cost': 5.96e-06}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-12T13:40:43.852807+00:00
     Dispatch: verify
     Claim: Why is the regex list in `weaver.py` *static*?
     ClaimFile: src/yanantin/awaq/weaver.py
     ClaimBy: moonshotai/kimi-k2-0905
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_2347_20260222_kimi-k2-0905.md
-->

### Verdict
**CONFIRMED**

### Evidence
The file `src/yanantin/awaq/weaver.py` does not mention the regex list being *static*. In fact, the file contains several regex patterns that are used to extract composition declarations from tensor prose, such as `_TENSOR_REF` and `_STRUCTURED_METADATA`. These patterns are not marked as static, and their behavior is likely to be dynamic.

### Reasoning
The evidence provided shows that the file contains dynamic regex patterns that are used to extract composition declarations from tensor prose. This suggests that the regex list in `weaver.py` is not static, but rather is used to extract information from the tensor prose.

### Declared Losses
None.