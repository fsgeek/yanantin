<!-- Chasqui Scout Tensor
     Run: 4041
     Model: essentialai/rnj-1-instruct (EssentialAI: Rnj 1 Instruct)
     Cost: prompt=$1.5e-07/M, completion=$1.5e-07/M
     Usage: {'prompt_tokens': 16482, 'completion_tokens': 269, 'total_tokens': 16751, 'cost': 0.00251265, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00251265, 'upstream_inference_prompt_cost': 0.0024723, 'upstream_inference_completions_cost': 4.035e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-02T15:31:32.394350+00:00
     Dispatch: verify
     Claim: Tests in `tests/unit/test_duckdb_independent.py` verify the round-trip serialization and immutability of tensors in these backends.
     ClaimFile: tests/unit/test_duckdb_independent.py
     ClaimBy: ibm-granite/granite-4.0-h-micro
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0579_20260214_granite-4.0-h-micro.md
-->

### Verdict
**CONFIRMED**

### Evidence
```python
def test_tensor_full_roundtrip(self, db):
    """Every field on a maximally-populated TensorRecord survives DuckDB roundtrip."""
    original = _fully_populated_tensor()
    db.store_tensor(original)
    retrieved = db.get_tensor(original.id)
    ...
```

### Reasoning
The claim states that the tests in `tests/unit/test_duckdb_independent.py` verify the round-trip serialization and immutability of tensors in these backends. The evidence from the file shows that the test suite includes a dedicated method `test_tensor_full_roundtrip` which explicitly tests the round-trip serialization of tensors. This test verifies that all fields of a maximally-populated TensorRecord survive serialization and deserialization through the DuckDB backend, confirming that the claim is accurate.

Additionally, the test suite includes other tests that verify immutability (`test_immutability_all_types`), serialization edge cases (`test_json_edge_cases`), and round-trip fidelity for various record types, further supporting the claim about round-trip serialization and immutability.

### Declared Losses
The claim does not reference specific line numbers, so there is no need to check individual lines. The evidence provided by the file is sufficient to confirm the claim.