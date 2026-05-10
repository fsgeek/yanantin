<!-- Chasqui Scout Tensor
     Run: 12586
     Model: mistralai/mistral-small-24b-instruct-2501 (Mistral: Mistral Small 3)
     Cost: prompt=$5e-08/M, completion=$8e-08/M
     Usage: {'prompt_tokens': 869, 'completion_tokens': 173, 'total_tokens': 1042, 'cost': 5.729e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 5.729e-05, 'upstream_inference_prompt_cost': 4.345e-05, 'upstream_inference_completions_cost': 1.384e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-10T11:23:05.263060+00:00
     GenerationID: gen-1778412184-MKX4g4KmGKnoOoi7d5Ti
     Dispatch: verify
     Claim: The `src/yanantin/chasqui/` scout program enforces immutability with `ImmutabilityError` (e.g., `tests/red_bar/test_immutability.py`, lines 9‑12).
     ClaimFile: tests/red_bar/test_immutability.py
     ClaimBy: sao10k/l3.3-euryale-70b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0173_20260213_l3.3-euryale-70b.md
-->

### Verdict
CONFIRMED

### Evidence
```
from yanantin.apacheta.interface.errors import ImmutabilityError

def test_duplicate_tensor_raises():
    ...
    with pytest.raises(ImmutabilityError):
        backend.store_tensor(duplicate)
```

### Reasoning
The claim states that the `src/yanantin/chasqui/` scout program enforces immutability with `ImmutabilityError`. The file `tests/red_bar/test_immutability.py` indeed imports `ImmutabilityError` from `yanantin.apacheta.interface.errors` and uses it in the test function `test_duplicate_tensor_raises` to ensure that attempting to store a tensor with the same UUID raises an `ImmutabilityError`. This directly supports the claim.

### Declared Losses
N/A