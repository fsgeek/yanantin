<!-- Chasqui Scout Tensor
     Run: 2434
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 735, 'completion_tokens': 380, 'total_tokens': 1115, 'cost': 0.0001054, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0001054, 'upstream_inference_prompt_cost': 2.94e-05, 'upstream_inference_completions_cost': 7.6e-05}, 'completion_tokens_details': {'reasoning_tokens': 156, 'audio_tokens': 0}}
     Timestamp: 2026-02-23T02:43:40.024798+00:00
     Dispatch: verify
     Claim: - A **cross-file audit tag** linking `docs/blueprint.md` to `src/yanantin/apacheta/models/provenance.py`.
     ClaimFile: src/yanantin/apacheta/models/provenance.py
     ClaimBy: liquid/lfm-2.2-6b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_2149_20260221_lfm-2.2-6b.md
-->

### Verdict
**DENIED**

### Evidence
```python
"""Provenance models — who made this, when, from what context."""
...
class SourceIdentifier(ApachetaBaseModel):
    """Identifies the source of a record."""
    ...
class ProvenanceEnvelope(ApachetaBaseModel):
    """Wraps every record with provenance metadata.

    Every artifact answers: who made this, when, from what context.
    """
    ...
```
(The full file contains only the above definitions and imports; there is no line mentioning `docs/blueprint.md` or any audit tag that links to that file.)

### Reasoning
The claim asserts that the file `src/yanantin/apacheta/models/provenance.py` contains a cross‑file audit tag linking it to `docs/blueprint.md`. Scanning the entire source shown, there are no comments, strings, or annotations that reference `docs/blueprint.md` or any similar tag. Therefore the claimed linkage does not exist in the provided file.

### Declared Losses
None. The source code was fully examined and contains no reference to the claimed audit tag.