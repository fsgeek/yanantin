<!-- Chasqui Scout Tensor
     Run: 4033
     Model: mistralai/mistral-small-24b-instruct-2501 (Mistral: Mistral Small 3)
     Cost: prompt=$5e-08/M, completion=$8e-08/M
     Usage: {'prompt_tokens': 1132, 'completion_tokens': 184, 'total_tokens': 1316, 'cost': 7.132e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 7.132e-05, 'upstream_inference_prompt_cost': 5.66e-05, 'upstream_inference_completions_cost': 1.472e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-02T14:29:31.442918+00:00
     Dispatch: verify
     Claim: ### Verdict DENIED ### Evidence The file `docs/signing.md` contains no mention of "tensor-level provenance" or `ProvenanceEnvelope` in `src/yanantin/models/base.py`.
     ClaimFile: docs/signing.md
     ClaimBy: qwen/qwen3-14b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1758_20260220_qwen3-14b.md
-->

### Verdict
CONFIRMED

### Evidence
The file `docs/signing.md` does not contain any mention of "tensor-level provenance" or `ProvenanceEnvelope` in `src/yanantin/models/base.py`.

### Reasoning
The claim states that the file `docs/signing.md` contains no mention of "tensor-level provenance" or `ProvenanceEnvelope` in `src/yanantin/models/base.py`. The provided content of `docs/signing.md` does not include any references to "tensor-level provenance" or `ProvenanceEnvelope`. Therefore, the claim is accurate based on the content of the file.

### Declared Losses
The claim mentions a file `src/yanantin/models/base.py`, which is not provided. Therefore, I cannot verify the absence of `ProvenanceEnvelope` in that specific file.