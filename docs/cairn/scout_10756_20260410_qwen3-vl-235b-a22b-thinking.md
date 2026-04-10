<!-- Chasqui Scout Tensor
     Run: 10756
     Model: qwen/qwen3-vl-235b-a22b-thinking (Qwen: Qwen3 VL 235B A22B Thinking)
     Cost: prompt=$2.6e-07/M, completion=$2.6e-06/M
     Usage: {'prompt_tokens': 985, 'completion_tokens': 6599, 'total_tokens': 7584, 'cost': 0.02353975, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.02353975, 'upstream_inference_prompt_cost': 0.00044325, 'upstream_inference_completions_cost': 0.0230965}, 'completion_tokens_details': {'reasoning_tokens': 5994, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-10T22:32:29.450953+00:00
     GenerationID: gen-1775859805-TmFh7THLH9zQWBsrVAZx
     Dispatch: verify
     Claim: ### Verdict CONFIRMED ### Evidence > The claim states that "model invocation logic may reside in `src/yanantin/apacheta/operators/` (e.g., `bootstrap.py` or `compose.py`)." > The file `src/yanantin/ap
     ClaimFile: src/yanantin/apacheta/operators/bootstrap.py
     ClaimBy: openai/gpt-4.1-nano
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_5731_20260312_gpt-4.1-nano.md
-->

### Verdict
INDETERMINATE

### Evidence
The provided file `src/yanantin/apacheta/operators/bootstrap.py` contains:
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

    record = BootstrapRecord(
        instance_id=instance_id,
        context_budget=context_budget,
        task=task,
        tensors_selected=tensor_ids,
        strands_selected=strand_indices or [],
        what_was_omitted=what_was_omitted,
        provenance=provenance or ProvenanceEnvelope(),
    )
    interface.store_bootstrap(record)

    return record, selected
```

### Reasoning
The claim states that "model invocation logic may reside in `src/yanantin/apacheta/operators/` (e.g., `bootstrap.py` or `compose.py`)." The provided file (`bootstrap.py`) contains a `bootstrap()` function that handles tensor selection and record creation for context budget initialization. However:
- The function **does not contain model invocation logic** (no model calls, predictions, or inference steps are present).
- The claim references *both* `bootstrap.py` and `compose.py` as examples, but **only `bootstrap.py` was provided**. Without `compose.py` or other files in the directory, it is impossible to verify whether model invocation logic exists elsewhere in `src/yanantin/apacheta/operators/`.
- The claim’s phrasing ("may reside") implies possibility, but the evidence from the single provided file neither confirms nor denies the existence of model invocation logic in the directory. The absence of such logic in `bootstrap.py` does not rule out its presence in unprovided files.

### Declared Losses
- Could not verify the entire directory `src/yanantin/apacheta/operators/` (only `bootstrap.py` was provided). Specifically, `compose.py` and other files in the directory were unavailable for inspection.
- Cannot determine if model invocation logic exists in unprovided files (e.g., `compose.py`), making it impossible to confirm or deny the claim's assertion about the directory.