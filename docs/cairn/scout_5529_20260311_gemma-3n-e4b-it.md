<!-- Chasqui Scout Tensor
     Run: 5529
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 883, 'completion_tokens': 461, 'total_tokens': 1344, 'cost': 3.61e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 3.61e-05, 'upstream_inference_prompt_cost': 1.766e-05, 'upstream_inference_completions_cost': 1.844e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-11T05:45:50.250120+00:00
     Dispatch: verify
     Claim: For instance, `src/yanantin/apacheta/operators/bootstrap.py` appears to handle the selection and retrieval of tensors based on context budgets.
     ClaimFile: src/yanantin/apacheta/operators/bootstrap.py
     ClaimBy: cohere/command-r-08-2024
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1063_20260216_command-r-08-2024.md
-->

### Verdict
**CONFIRMED**

### Evidence
```python
"""Bootstrap operator — selects tensors/strands for a new instance's budget."""
```
```python
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
    """Select tensors for a new instance's context budget.

    Always persisted. Storage cost ≈ 0. Provenance value > 0.

    Returns the bootstrap record and the selected tensors.
    """
    if tensor_ids is None:
        # Simple: select all available tensors
        selected = interface.list_tensors()
        tensor_ids = [t.id for t in selected]
    else:
        selected = [interface.get_tensor(tid) for tid in tensor_ids]
```

### Reasoning
The file's docstring clearly states: "Select tensors for a new instance's context budget." The code within the `bootstrap` function implements this by either selecting all available tensors if `tensor_ids` is None or by selecting the tensors specified in `tensor_ids`. Therefore, the claim that the file handles the selection and retrieval of tensors based on context budgets is accurate.

### Declared Losses
The claim mentions "retrieval" of tensors. The code shows the retrieval process when `tensor_ids` are provided (`interface.get_tensor(tid)`). However, the code also shows the selection of all available tensors when `tensor_ids` is None (`interface.list_tensors()`). While "retrieval" is implied by the function's action of getting specific tensors, the wording of the claim is slightly broader than explicitly stated in the code. However, the core functionality of selecting tensors based on a budget is present.