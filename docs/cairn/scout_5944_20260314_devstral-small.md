<!-- Chasqui Scout Tensor
     Run: 5944
     Model: mistralai/devstral-small (Mistral: Devstral Small 1.1)
     Cost: prompt=$1e-07/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 1434, 'completion_tokens': 460, 'total_tokens': 1894, 'cost': 0.0002814, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0002814, 'upstream_inference_prompt_cost': 0.0001434, 'upstream_inference_completions_cost': 0.000138}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-14T10:16:19.366802+00:00
     Dispatch: verify
     Claim: `src/yanantin/chasqui/model_selector.py` — **Accessible** The file content does show cost-weighted behavior: ```python """Picks models weighted inversely by cost.
     ClaimFile: src/yanantin/chasqui/model_selector.py
     ClaimBy: qwen/qwen3.5-flash-02-23
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_5025_20260308_qwen3.5-flash-02-23.md
-->

### Verdict
**CONFIRMED**

### Evidence
The file content includes the following lines:

1. From the module docstring:
   ```python
   """Picks models weighted inversely by cost. Cheap models get dispatched
   more often. Over time, the cairn accumulates data on which models
   notice what — and whether noticing more is worth paying more.
   """
   ```

2. From the `ModelSelector` class docstring:
   ```python
   """Cost-weighted random model selection.

   Models are weighted inversely by cost: a model at $0.10/M is
   10x more likely to be selected than one at $1.00/M. Free models
   get a small nominal cost to avoid division by zero.

   The selector can be filtered by constraints (minimum context length,
   excluded families, etc.) and seeded for reproducibility.
   """
   ```

3. From the `select` method:
   ```python
   def select(self) -> ModelInfo:
       """Pick a model weighted inversely by cost.

       Raises ValueError if no models are loaded.
       """
       if not self.models:
           raise ValueError("No models loaded. Call load_from_openrouter_response first.")

       # Inverse cost weighting. Free models get nominal cost of $0.001/M
       # to avoid infinite weight while still being heavily favored.
       weights = []
       for m in self.models:
           cost = m.total_cost_per_million
           if cost <= 0:
               cost = 0.001  # Nominal cost for free models
           weights.append(1.0 / cost)

       return self._rng.choices(self.models, weights=weights, k=1)[0]
   ```

### Reasoning
The evidence supports the claim because the file explicitly states and demonstrates the cost-weighted behavior. The module and class docstrings both describe the behavior of picking models weighted inversely by cost. The `select` method implements this behavior by calculating weights as the inverse of the total cost per million tokens and using these weights in the selection process.

### Declared Losses
None. The claim is fully verifiable based on the provided file content.