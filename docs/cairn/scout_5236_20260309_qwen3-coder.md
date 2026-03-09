<!-- Chasqui Scout Tensor
     Run: 5236
     Model: qwen/qwen3-coder (Qwen: Qwen3 Coder 480B A35B)
     Cost: prompt=$2.2e-07/M, completion=$1e-06/M
     Usage: {'prompt_tokens': 701, 'completion_tokens': 268, 'total_tokens': 969, 'cost': 0.0005587, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0005587, 'upstream_inference_prompt_cost': 0.0002103, 'upstream_inference_completions_cost': 0.0003484}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-09T12:15:01.745570+00:00
     Dispatch: verify
     Claim: I would extend this strand by pointing out the `authors` list in `src/yanantin/apacheta/models/provenance.py`, which suggests a multi-authorship model.
     ClaimFile: src/yanantin/apacheta/models/provenance.py
     ClaimBy: sao10k/l3-lunaris-8b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_3286_20260226_l3-lunaris-8b.md
-->

### Verdict
**DENIED**

### Evidence
The entire content of `src/yanantin/apacheta/models/provenance.py` is provided, and there is no mention or definition of an `authors` list anywhere in the file. Specifically:

- The class `ProvenanceEnvelope` contains fields related to authorship such as `author_model_family` and `author_instance_id`, but these are singular fields, not a list.
- No variable or field named `authors` exists in the file.

Relevant lines:
```python
class ProvenanceEnvelope(ApachetaBaseModel):
    ...
    author_model_family: str = ""
    author_instance_id: str = ""
```

### Reasoning
The claim asserts that there is an `authors` list in the file `src/yanantin/apacheta/models/provenance.py`. However, inspection of the file shows no such list or field. While the model includes fields that relate to authorship, they are scalar values (`str`) and not a collection suggesting multiple authors. Therefore, the claim is false based on the available static source code.

### Declared Losses
None — the claim is purely about the presence of a static element (a list called `authors`) in the source code, which can be definitively checked.