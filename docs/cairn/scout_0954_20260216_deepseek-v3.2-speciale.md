<!-- Chasqui Scout Tensor
     Run: 954
     Model: deepseek/deepseek-v3.2-speciale (DeepSeek: DeepSeek V3.2 Speciale)
     Cost: prompt=$2.7e-07/M, completion=$4.1e-07/M
     Usage: {'prompt_tokens': 671, 'completion_tokens': 2885, 'total_tokens': 3556, 'cost': 0.0037304, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0037304, 'upstream_inference_prompt_cost': 0.0002684, 'upstream_inference_completions_cost': 0.003462}, 'completion_tokens_details': {'reasoning_tokens': 3069, 'audio_tokens': 0}}
     Timestamp: 2026-02-16T14:00:53.080016+00:00
-->

### Verdict
CONFIRMED

### Evidence
```python
class EntityResolution(ApachetaBaseModel):
    ...
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)
```

### Reasoning
The claim states that records in `models/entities.py` carry `ProvenanceEnvelope` metadata. The file defines a single record class `EntityResolution`, which includes a field `provenance` of type `ProvenanceEnvelope`. This directly confirms that the record carries such metadata, supporting the claim as it pertains to this specific file.

### Declared Losses
- The claim also asserts that the entire `src/yanantin/apacheta` module is built around an epistemic framework and that *every* record across the module carries `ProvenanceEnvelope`. I can only verify the presence of `ProvenanceEnvelope` in `entities.py`; I cannot verify the universal claim or the example `models/tensor.py` without seeing other files.
- The term "epistemic framework" refers to a design philosophy that cannot be fully verified from code alone, though the inclusion of provenance metadata is consistent with such an approach.