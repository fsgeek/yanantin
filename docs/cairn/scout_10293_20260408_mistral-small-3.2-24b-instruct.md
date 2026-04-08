<!-- Chasqui Scout Tensor
     Run: 10293
     Model: mistralai/mistral-small-3.2-24b-instruct (Mistral: Mistral Small 3.2 24B)
     Cost: prompt=$7.5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 865, 'completion_tokens': 183, 'total_tokens': 1048, 'cost': 0.000101475, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.000101475, 'upstream_inference_prompt_cost': 6.4875e-05, 'upstream_inference_completions_cost': 3.66e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-08T09:30:57.329990+00:00
     GenerationID: gen-1775640649-m2mxsLf7E9pE823114SU
     Dispatch: verify
     Claim: - **Example:** - `scout_1708` confirms immutability in `tests/red_bar/test_immutability.py` (lines 16-18).
     ClaimFile: tests/red_bar/test_immutability.py
     ClaimBy: mistralai/ministral-14b-2512
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_3578_20260228_ministral-14b-2512.md
-->

### Verdict
**CONFIRMED**

### Evidence
Lines 16-18 from `tests/red_bar/test_immutability.py`:
```python
    # Same UUID = ImmutabilityError. Compose, don't overwrite.
    duplicate = TensorRecord(
        id=tensor.id,
        preamble="Attempted overwrite",
    )
```

### Reasoning
The claim states that `scout_1708` confirms immutability in the specified file. The evidence shows that the test `test_duplicate_tensor_raises` indeed checks for immutability by attempting to store a tensor with the same UUID as an already stored tensor. This aligns with the claim that immutability is confirmed in the given lines of the file.

### Declared Losses
No losses declared. The claim is fully verifiable based on the provided file content.