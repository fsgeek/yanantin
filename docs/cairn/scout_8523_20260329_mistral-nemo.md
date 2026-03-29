<!-- Chasqui Scout Tensor
     Run: 8523
     Model: mistralai/mistral-nemo (Mistral: Mistral Nemo)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 1031, 'completion_tokens': 183, 'total_tokens': 1214, 'cost': 2.794e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 2.794e-05, 'upstream_inference_prompt_cost': 2.062e-05, 'upstream_inference_completions_cost': 7.32e-06}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-29T00:43:47.866409+00:00
     GenerationID: gen-1774745023-wemaRGARSZZNwcQHhFex
     Dispatch: verify
     Claim: - `scout_0077_20260212_gemini-2.5-flash-lite.md` tests `query_operational_principles`, not metadata.
     ClaimFile: docs/cairn/scout_0077_20260212_gemini-2.5-flash-lite.md
     ClaimBy: minimax/minimax-m2-her
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0361_20260213_minimax-m2-her.md
-->

### Verdict
DENIED

### Evidence
The claim states that the file "tests `query_operational_principles`, not metadata." However, the file contains the following test function:
```python
    def test_query_operational_principles(self, backend):
        # ... (rest of the test function)
```
This test function is named `test_query_operational_principles` and is indeed testing the `query_operational_principles` functionality.

### Reasoning
The presence of this test function directly contradicts the claim that the file does not test `query_operational_principles`. The file explicitly contains code and tests related to querying operational principles, which is the specific concept being tested in this function. Therefore, the claim that the file does not test `query_operational_principles` is inaccurate.

### Declared Losses
None.