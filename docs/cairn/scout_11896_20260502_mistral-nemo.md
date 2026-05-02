<!-- Chasqui Scout Tensor
     Run: 11896
     Model: mistralai/mistral-nemo (Mistral: Mistral Nemo)
     Cost: prompt=$2e-08/M, completion=$3e-08/M
     Usage: {'prompt_tokens': 803, 'completion_tokens': 268, 'total_tokens': 1071, 'cost': 2.41e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 2.41e-05, 'upstream_inference_prompt_cost': 1.606e-05, 'upstream_inference_completions_cost': 8.04e-06}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-02T19:50:29.092081+00:00
     GenerationID: gen-1777751425-CJP2AtSNzdgFtBYXWYcO
     Dispatch: verify
     Claim: **Are the operators `compose`, `correct`, and `dissent` defined in `apacheta/operators/bootstrap.py` or `tests/unit/test_operators.py`?**   2.
     ClaimFile: src/yanantin/apacheta/operators/bootstrap.py
     ClaimBy: qwen/qwen3-4b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0596_20260214_qwen3-4b.md
-->

### Verdict
**DENIED**

### Evidence
```python
def bootstrap(  # ...  # No operators `compose`, `correct`, or `dissent` defined
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
    """...  # ...  # No mention of operators `compose`, `correct`, or `dissent`
    ...
    return record, selected
```

### Reasoning
The file `src/yanantin/apacheta/operators/bootstrap.py` does not define any operators named `compose`, `correct`, or `dissent`. Furthermore, there is no mention of these operators anywhere else in the file, including in comments or docstrings. Therefore, the claim that these operators are defined in this file is false.

### Declared Losses
None. The claim was about the content of a specific file, and I was able to verify it by reading that file.