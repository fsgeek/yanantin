<!-- Chasqui Scout Tensor
     Run: 3837
     Model: qwen/qwen-turbo (Qwen: Qwen-Turbo)
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 812, 'completion_tokens': 299, 'total_tokens': 1111, 'cost': 0.0001004, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0001004, 'upstream_inference_prompt_cost': 4.06e-05, 'upstream_inference_completions_cost': 5.98e-05}, 'completion_tokens_details': {'reasoning_tokens': 0}}
     Timestamp: 2026-03-01T12:44:07.177883+00:00
     Dispatch: verify
     Claim: Evidence:   - `src/yanantin/apacheta/operators/bootstrap.py` (as quoted in the previous scout) passes `context_budget` to the instance.
     ClaimFile: src/yanantin/apacheta/operators/bootstrap.py
     ClaimBy: allenai/olmo-3.1-32b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1336_20260218_olmo-3.1-32b-instruct.md
-->

### Verdict
CONFIRMED

### Evidence
The function definition for `bootstrap` includes the parameter `context_budget`:

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

Additionally, the `BootstrapRecord` is initialized with `context_budget`:

```python
record = BootstrapRecord(
    instance_id=instance_id,
    context_budget=context_budget,
    task=task,
    tensors_selected=tensor_ids,
    strands_selected=strand_indices or [],
    what_was_omitted=what_was_omitted,
    provenance=provenance or ProvenanceEnvelope(),
)
```

### Reasoning
The claim states that the file passes `context_budget` to the instance. The evidence shows that the `bootstrap` function receives `context_budget` as a parameter and uses it to construct a `BootstrapRecord` object, which is stored via `interface.store_bootstrap(record)`. This confirms that the `context_budget` is indeed passed to the instance.

### Declared Losses
None. The claim is fully supported by the source code.