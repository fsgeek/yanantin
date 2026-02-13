<!-- Chasqui Scout Tensor
     Run: 167
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 881, 'completion_tokens': 355, 'total_tokens': 1236, 'cost': 3.182e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 3.182e-05, 'upstream_inference_prompt_cost': 1.762e-05, 'upstream_inference_completions_cost': 1.42e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-13T00:28:17.291419+00:00
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
    """Select tensors for a new instance's context budget.

    Always persisted. Storage cost ≈ 0. Provenance value > 0.
    """
```

### Reasoning
The claim states that `bootstrap.py` selects tensors for the context budget. The provided file shows that the function `bootstrap` selects tensors based on the input `tensor_ids`. The docstring explicitly states, "Select tensors for a new instance's context budget." Therefore, the first part of the claim is accurate.

However, the claim also states that `correct.py` records corrections and automatically creates a correction edge. The provided file is for `bootstrap.py`. There is no mention of `correct.py` or any functionality related to recording corrections or creating correction edges within the `bootstrap.py` file.

### Declared Losses
The claim mentions the behavior of `correct.py`, which is not present in the provided file. I cannot determine the accuracy of the second part of the claim as it references a different file.