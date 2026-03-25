<!-- Chasqui Scout Tensor
     Run: 7889
     Model: inception/mercury-coder (Inception: Mercury Coder)
     Cost: prompt=$2.5e-07/M, completion=$7.5e-07/M
     Usage: {'prompt_tokens': 799, 'completion_tokens': 261, 'total_tokens': 1060, 'cost': 0.000394825, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 3, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.000394825, 'upstream_inference_prompt_cost': 0.000199075, 'upstream_inference_completions_cost': 0.00019575}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-25T12:03:25.866018+00:00
     GenerationID: gen-1774440205-geQjZwYx9qEGRpMWQfmP
     Dispatch: verify
     Claim: It highlights the project's commitment to immutability, as evidenced by the `tests/red_bar/test_immutability.py` file, which contains tests ensuring tensors cannot be overwritten.
     ClaimFile: tests/red_bar/test_immutability.py
     ClaimBy: amazon/nova-micro-v1
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1865_20260220_nova-micro-v1.md
-->

### Verdict
**CONFIRMED**

### Evidence
```python
def test_duplicate_tensor_raises():
    backend = InMemoryBackend()
    tensor = TensorRecord(preamble="First version")
    backend.store_tensor(tensor)

    # Same UUID = ImmutabilityError. Compose, don't overwrite.
    duplicate = TensorRecord(
        id=tensor.id,
        preamble="Attempted overwrite",
    )
    with pytest.raises(ImmutabilityError):
        backend.store_tensor(duplicate)
```

### Reasoning
The file defines a test `test_duplicate_tensor_raises` that attempts to store a second `TensorRecord` with the same UUID as an existing tensor. The test expects an `ImmutabilityError` to be raised, indicating that the backend does not allow overwriting an existing tensor. This directly demonstrates the project's commitment to immutability. Additionally, the file contains other tests (`test_duplicate_edge_raises`, `test_no_delete_method`, `test_no_update_method`) that further enforce immutability by preventing updates, deletions, or overwrites of stored objects. Therefore, the claim that the file contains tests ensuring tensors cannot be overwritten is fully supported by the code.

### Declared Losses
None. The source file provides all necessary information to assess the claim.