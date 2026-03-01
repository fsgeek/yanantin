<!-- Chasqui Scout Tensor
     Run: 3804
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 1584, 'completion_tokens': 399, 'total_tokens': 1983, 'cost': 4.764e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 4.764e-05, 'upstream_inference_prompt_cost': 3.168e-05, 'upstream_inference_completions_cost': 1.596e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-01T08:32:11.838136+00:00
     Dispatch: verify
     Claim: Similar frozen models appear in `src/yanantin/chasqui/model_selector.py` (the `ModelInfo` dataclass).
     ClaimFile: src/yanantin/chasqui/model_selector.py
     ClaimBy: openai/gpt-oss-120b:exacto
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1702_20260219_gpt-oss-120b:exacto.md
-->

### Verdict
**CONFIRMED**

### Evidence
```
@dataclass(frozen=True)
class ModelInfo:
    """A model available through OpenRouter."""

    id: str
    name: str
    prompt_cost: float  # $/M tokens
    completion_cost: float  # $/M tokens
    context_length: int = 0

    @property
    def total_cost_per_million(self) -> float:
        return self.prompt_cost + self.completion_cost
```
The `ModelInfo` dataclass is defined with fields `prompt_cost` and `completion_cost`. The `total_cost_per_million` property calculates their sum. This indicates that the `ModelInfo` dataclass is designed to store and represent pricing information for models, which aligns with the claim that similar frozen models appear in `src/yanantin/chasqui/model_selector.py` (the `ModelInfo` dataclass).

### Reasoning
The code defines a `ModelInfo` dataclass, which is a class used to hold information about a model. The dataclass includes fields for `prompt_cost` and `completion_cost`, both representing costs associated with using the model. The `total_cost_per_million` property further aggregates these costs. This structure strongly suggests that the file contains information about models, and the `ModelInfo` dataclass is the mechanism for storing that information. Therefore, the claim that similar frozen models appear in `src/yanantin/chasqui/model_selector.py` (specifically in the `ModelInfo` dataclass) is accurate.

### Declared Losses
The claim mentions the behavior of the `ModelInfo` dataclass in the context of model selection, but I can only inspect the definition of the dataclass itself and not the code where it is used or populated with data.