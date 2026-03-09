<!-- Chasqui Scout Tensor
     Run: 5258
     Model: deepseek/deepseek-v3.2 (DeepSeek: DeepSeek V3.2)
     Cost: prompt=$2.5e-07/M, completion=$4e-07/M
     Usage: {'prompt_tokens': 1397, 'completion_tokens': 317, 'total_tokens': 1714, 'cost': 0.00048368, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00048368, 'upstream_inference_prompt_cost': 0.00036322, 'upstream_inference_completions_cost': 0.00012046}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-09T15:38:24.154694+00:00
     Dispatch: verify
     Claim: The `model_selector.py` exists, but the policy isn’t documented.
     ClaimFile: src/yanantin/chasqui/model_selector.py
     ClaimBy: qwen/qwen3-235b-a22b-2507
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_2782_20260224_qwen3-235b-a22b-2507.md
-->

### Verdict
**DENIED**

### Evidence
The file begins with a docstring and includes a detailed class docstring:
```
"""Model selection for Chasqui scouts.

Picks models weighted inversely by cost. Cheap models get dispatched
more often. Over time, the cairn accumulates data on which models
notice what — and whether noticing more is worth paying more.
"""
```

```
@dataclass
class ModelSelector:
    """Cost-weighted random model selection.

    Models are weighted inversely by cost: a model at $0.10/M is
    10x more likely to be selected than one at $1.00/M. Free models
    get a small nominal cost to avoid division by zero.

    The selector can be filtered by constraints (minimum context length,
    excluded families, etc.) and seeded for reproducibility.
    """
```

### Reasoning
The claim states "the policy isn't documented," but the file contains clear documentation of the policy in two places:
1. The module docstring at the top explains the overall approach: "Picks models weighted inversely by cost. Cheap models get dispatched more often."
2. The `ModelSelector` class docstring provides detailed documentation of the policy: "Cost-weighted random model selection. Models are weighted inversely by cost..." with specific examples and explanations of how free models are handled.

Both docstrings explicitly document the selection policy, making the claim that "the policy isn't documented" factually incorrect.

### Declared Losses
None. The claim is directly verifiable from the source code content provided.