<!-- Chasqui Scout Tensor
     Run: 623
     Model: qwen/qwen-turbo (Qwen: Qwen-Turbo)
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 1455, 'completion_tokens': 169, 'total_tokens': 1624, 'cost': 0.00010655, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00010655, 'upstream_inference_prompt_cost': 7.275e-05, 'upstream_inference_completions_cost': 3.38e-05}, 'completion_tokens_details': {'reasoning_tokens': 0}}
     Timestamp: 2026-02-15T02:56:34.211017+00:00
-->

### Verdict
**CONFIRMED**

### Evidence
The file contains the following lines:

```python
prompt_cost: float  # $/M tokens
completion_cost: float  # $/M tokens
```

and later:

```python
def select(self) -> ModelInfo:
    """Pick a model weighted inversely by cost."""
```

### Reasoning
The file explicitly tracks both `prompt_cost` and `completion_cost` as part of the `ModelInfo` class, with comments indicating they are measured in dollars per million tokens. The `ModelSelector` class uses these costs to weight model selection inversely by cost, which directly supports the claim that the file includes model-selection logic that tracks prompt and completion token costs.

### Declared Losses
None. The claim is fully supported by the source code.