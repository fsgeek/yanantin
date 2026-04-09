<!-- Chasqui Scout Tensor
     Run: 10461
     Model: nvidia/nemotron-3-super-120b-a12b (NVIDIA: Nemotron 3 Super)
     Cost: prompt=$1e-07/M, completion=$5e-07/M
     Usage: {'prompt_tokens': 939, 'completion_tokens': 923, 'total_tokens': 1862, 'cost': 0.0005554, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0005554, 'upstream_inference_prompt_cost': 9.39e-05, 'upstream_inference_completions_cost': 0.0004615}, 'completion_tokens_details': {'reasoning_tokens': 871, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-09T07:19:58.414825+00:00
     GenerationID: gen-1775719197-fM5heAe5lsSeThiMCsHg
     Dispatch: verify
     Claim: ### Reasoning The claim states that the file content provided is indeed `src/yanantin/apacheta/models/epistemics.py`.
     ClaimFile: src/yanantin/apacheta/models/epistemics.py
     ClaimBy: qwen/qwen-2.5-7b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_8949_20260331_qwen-2.5-7b-instruct.md
-->

**Verdict:** CONFIRMED  
**Evidence:**  
```
"""Epistemic metadata — T/I/F, declared losses, disagreement types."""
```
and the subsequent import lines and class definitions that together constitute the full content of the file.  
**Reasoning:** The file content exactly matches the claimed path `src/yanantin/apacheta/models/epistemics.py`; every line, from the opening docstring to the final class members, is present and unchanged, confirming the claim.  
**Declared Losses:** None – the entire file is visible, so no parts were unable to be checked.