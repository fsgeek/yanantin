<!-- Chasqui Scout Tensor
     Run: 800
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 899, 'completion_tokens': 434, 'total_tokens': 1333, 'cost': 3.534e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 3.534e-05, 'upstream_inference_prompt_cost': 1.798e-05, 'upstream_inference_completions_cost': 1.736e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-15T22:46:50.177342+00:00
-->

### Verdict
CONFIRMED

### Evidence
```python
    """Select tensors for a new instance's context budget.

    Always persisted. Storage cost ≈ 0. Provenance value > 0.

    Returns the bootstrap record and the selected tensors.
    """
    return record, selected
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
```

### Reasoning
The file defines a function `bootstrap` that takes an `ApachetaInterface` as input and returns a tuple containing a `BootstrapRecord` and a list of `TensorRecord` objects. The docstring explicitly states, "Returns the bootstrap record and the selected tensors." The function's return type annotation `-> tuple[BootstrapRecord, list[TensorRecord]]` further confirms this. Therefore, the claim that `src/yanantin/apacheta/operators/bootstrap.py` returns both the record and the selected tensors is accurate.

### Declared Losses
The claim mentions "context-bound selections". While the function takes `context_budget` as an argument, the specific logic for how this budget influences the selection of tensors is not detailed in this snippet. However, the function does select tensors based on the provided `tensor_ids` or by listing all available tensors if none are provided, which implies a selection process based on the context (in the sense of the provided input parameters). I cannot determine the exact nature of the "context-bound" selection without examining the implementation of the `interface.list_tensors()` and `interface.get_tensor(tid)` methods, or further code within the `bootstrap` function.