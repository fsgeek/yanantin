<!-- Chasqui Scout Tensor
     Run: 8367
     Model: deepseek/deepseek-r1-distill-qwen-32b (DeepSeek: R1 Distill Qwen 32B)
     Cost: prompt=$2.9e-07/M, completion=$2.9e-07/M
     Usage: {'prompt_tokens': 1151, 'completion_tokens': 378, 'total_tokens': 1529, 'cost': 0.00044341, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00044341, 'upstream_inference_prompt_cost': 0.00033379, 'upstream_inference_completions_cost': 0.00010962}, 'completion_tokens_details': {'reasoning_tokens': 338, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-28T03:58:20.141942+00:00
     GenerationID: gen-1774670279-WUyWXbyPIjfugep8auvT
     Dispatch: verify
     Claim: ``` ### Reasoning The document explicitly verifies that the claim “Tensor‑level provenance is not documented in `docs/signing.md`” is true, as it states that `docs/signing.md` contains no mention of t
     ClaimFile: docs/signing.md
     ClaimBy: openai/gpt-oss-safeguard-20b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_6631_20260318_gpt-oss-safeguard-20b.md
-->

### Verdict
**CONFIRMED**

### Evidence
The file `docs/signing.md` does not contain any mention of "Tensor-level provenance."

### Reasoning
The document discusses code signing, including how AI and human commits are signed, the keys used, and configurations. It does not reference tensor-level provenance, confirming the claim.

### Declared Losses
None. The file was thoroughly reviewed for the specific term.