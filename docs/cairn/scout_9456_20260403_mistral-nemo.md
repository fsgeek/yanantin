<!-- Chasqui Scout Tensor
     Run: 9456
     Model: mistralai/mistral-nemo (Mistral: Mistral Nemo)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 1444, 'completion_tokens': 338, 'total_tokens': 1782, 'cost': 4.24e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 4.24e-05, 'upstream_inference_prompt_cost': 2.888e-05, 'upstream_inference_completions_cost': 1.352e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-03T18:12:34.208144+00:00
     GenerationID: gen-1775239944-rpmcp951EyUu699vOG9K
     Dispatch: verify
     Claim: `scour_0323_20260303_gpt-oss-20b.md` notes cost-weighted sampling in `model_selector.py` (line 1-73), excluding certain models and using nominal costs to avoid division by zero.
     ClaimFile: src/yanantin/chasqui/model_selector.py
     ClaimBy: x-ai/grok-code-fast-1
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_4691_20260306_grok-code-fast-1.md
-->

### Verdict
**CONFIRMED**

### Evidence
The claim mentions cost-weighted sampling in `model_selector.py`, excluding certain models and using nominal costs to avoid division by zero. The following lines from the file support these points:

```python
# Inverse cost weighting. Free models get nominal cost of $0.001/M
# to avoid infinite weight while still being heavily favored.
weights = []
for m in self.models:
    cost = m.total_cost_per_million
    if cost <= 0:
        cost = 0.001  # Nominal cost for free models
    weights.append(1.0 / cost)
```

And the exclusion of certain models is controlled by the `exclude_patterns` list:

```python
# Skip if matches exclude pattern
if any(pat in model_id for pat in self.exclude_patterns):
    continue
```

### Reasoning
The provided file indeed implements cost-weighted sampling in the `select` method of the `ModelSelector` class. The cost is calculated as the sum of `prompt_cost` and `completion_cost` for each model. If a model's total cost is zero or negative, a nominal cost of $0.001/M is used to avoid division by zero. The `exclude_patterns` list is used to filter out certain models during the loading process, supporting the claim of excluding certain models.

### Declared Losses
The claim refers to notes in `scour_0323_20260303_gpt-oss-20b.md`, but I cannot verify the contents of that file.