<!-- Chasqui Scout Tensor
     Run: 9726
     Model: meta-llama/llama-3-8b-instruct (Meta: Llama 3 8B Instruct)
     Cost: prompt=$3e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 1058, 'completion_tokens': 233, 'total_tokens': 1291, 'cost': 4.106e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 4.106e-05, 'upstream_inference_prompt_cost': 3.174e-05, 'upstream_inference_completions_cost': 9.32e-06}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-05T06:48:45.544439+00:00
     GenerationID: gen-1775371719-vFXluILbwNAZNDFJOcut
     Dispatch: verify
     Claim: **Synthetic Data for Testing**   - **What I saw**: `test_collector_synthetic.py` uses a `SyntheticCollectorBase` to generate deterministic data.
     ClaimFile: tests/unit/test_collector_synthetic.py
     ClaimBy: qwen/qwen3-30b-a3b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_7880_20260325_qwen3-30b-a3b.md
-->

### Verdict
**CONFIRMED**

### Evidence
The evidence that supports the verdict can be found in the following lines:
```
class DummySynthetic(SyntheticCollectorBase[int]):
    def generate(self) -> int:
        return self._rng.randint(0, 1000000)

    def get_description(self) -> str:
        return "dummy"

c1 = DummySynthetic(seed=42)
c2 = DummySynthetic(seed=42)
assert c1.collect() == c2.collect()
```
These lines show that the `collect()` method of the `DummySynthetic` class returns the same value when called with the same seed.

### Reasoning
The evidence shows that the `collect()` method is deterministic, meaning it returns the same value for the same input (seed). This confirms the claim that `test_collector_synthetic.py` uses a `SyntheticCollectorBase` to generate deterministic data.

### Declared Losses
I could not check the claim about the behavior at runtime because the code only shows the source code and not the runtime behavior. I can only verify the claim based on the code provided.