<!-- Chasqui Scout Tensor
     Run: 4162
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 888, 'completion_tokens': 368, 'total_tokens': 1256, 'cost': 0.00010912, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00010912, 'upstream_inference_prompt_cost': 3.552e-05, 'upstream_inference_completions_cost': 7.36e-05}, 'completion_tokens_details': {'reasoning_tokens': 232, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-03T08:00:56.851610+00:00
     Dispatch: verify
     Claim: ### 9️⃣  **Testing for Epistemic Properties**   - **Red‑Bar Tests:** `tests/red_bar/test_immutability.py`, `test_least_privilege.py`, `test_monotonicity.py`, `test_portability.py`, `test_provenance.py
     ClaimFile: tests/red_bar/test_immutability.py
     ClaimBy: openai/gpt-oss-120b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0448_20260214_gpt-oss-120b.md
-->

### Verdict
**CONFIRMED**

### Evidence
```python
"""Red-bar test: Immutability invariant.
...
"""
```
(First line of the file)

```python
def test_duplicate_tensor_raises():
    ...
```
(The presence of tests that enforce immutability)

### Reasoning
The file `tests/red_bar/test_immutability.py` begins with a docstring explicitly labeling it as a **"Red-bar test: Immutability invariant."** This directly confirms that the file is indeed a Red‑Bar test, matching the claim that it belongs to the set of Red‑Bar tests for epistemic properties.

### Declared Losses
None. The source file clearly indicates its classification as a Red‑Bar test.