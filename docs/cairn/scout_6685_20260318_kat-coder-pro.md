<!-- Chasqui Scout Tensor
     Run: 6685
     Model: kwaipilot/kat-coder-pro (Kwaipilot: KAT-Coder-Pro V1)
     Cost: prompt=$2.07e-07/M, completion=$8.28e-07/M
     Usage: {'prompt_tokens': 879, 'completion_tokens': 216, 'total_tokens': 1095, 'cost': 0.000359973, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 5, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0005217, 'upstream_inference_prompt_cost': 0.0002625, 'upstream_inference_completions_cost': 0.0002592}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-18T18:35:28.201835+00:00
     Dispatch: verify
     Claim: *   **What I saw:** `docs/cairn/scout_5909_20260314_llama-3.1-8b-instruct.md` *CONFIRMED* that `tests/red_bar/test_immutability.py` checks that duplicate tensors raise an `ImmutabilityError`.
     ClaimFile: tests/red_bar/test_immutability.py
     ClaimBy: google/gemini-2.5-flash-lite-preview-09-2025
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_6310_20260316_gemini-2.5-flash-lite-preview-.md
-->

### Verdict
CONFIRMED

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
The file contains a test function `test_duplicate_tensor_raises()` that explicitly verifies the immutability invariant. The test creates a tensor, stores it, then attempts to store another tensor with the same UUID (`id=tensor.id`). The test uses `pytest.raises(ImmutabilityError)` to assert that this operation raises an `ImmutabilityError`. This directly matches the claim that the file checks that duplicate tensors raise an `ImmutabilityError`.

### Declared Losses
None. The claim is fully verifiable from the source code.