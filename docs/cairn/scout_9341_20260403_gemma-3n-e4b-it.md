<!-- Chasqui Scout Tensor
     Run: 9341
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 892, 'completion_tokens': 244, 'total_tokens': 1136, 'cost': 2.76e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 2.76e-05, 'upstream_inference_prompt_cost': 1.784e-05, 'upstream_inference_completions_cost': 9.76e-06}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-03T03:31:57.360206+00:00
     GenerationID: gen-1775187109-kXL3REcKjqLYTQQw4uSa
     Dispatch: verify
     Claim: ### Verdict   **DENIED** ### Evidence   The file contains no mention of `src/yanantin/apacheta/operators/bootstrap.py`, nor does it define or reference any file or content by that path.
     ClaimFile: src/yanantin/apacheta/operators/bootstrap.py
     ClaimBy: liquid/lfm2-8b-a1b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_4307_20260304_lfm2-8b-a1b.md
-->

### Verdict
**DENIED**

### Evidence
```
"""Bootstrap operator — selects tensors/strands for a new instance's budget."""
```
```
def bootstrap(
    interface: ApachetaInterface,
    instance_id: str,
    context_budget: float,
    *,
    task: str = "",
    tensor_ids: list[UUID] | None = None,
    strand_indices: list[int] | None = None,
    what_was_omitted: str = "",
    provenance: ProvenanceEnvelope | None = None,
) -> tuple[BootstrapRecord, list[TensorRecord]]:
```

### Reasoning
The file clearly defines a function named `bootstrap`. The claim states the file contains no mention of `src/yanantin/apacheta/operators/bootstrap.py`. However, the provided file *is* `src/yanantin/apacheta/operators/bootstrap.py`. Therefore, the claim that the file contains no mention of this specific file path is inaccurate.

### Declared Losses
None. The file content is directly provided and the claim is about this file.