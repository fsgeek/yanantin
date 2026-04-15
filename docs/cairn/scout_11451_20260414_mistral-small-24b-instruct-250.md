<!-- Chasqui Scout Tensor
     Run: 11451
     Model: mistralai/mistral-small-24b-instruct-2501 (Mistral: Mistral Small 3)
     Cost: prompt=$5e-08/M, completion=$8e-08/M
     Usage: {'prompt_tokens': 950, 'completion_tokens': 306, 'total_tokens': 1256, 'cost': 7.198e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 7.198e-05, 'upstream_inference_prompt_cost': 4.75e-05, 'upstream_inference_completions_cost': 2.448e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-14T17:31:18.588069+00:00
     GenerationID: gen-1776187874-VprbcsXGS8gkcLjPCOuh
     Dispatch: verify
     Claim: **Why is `epistemics.py` a separate model from `tensor.py`?**   The epistemic layer is rich, but it's not directly tied to tensor structure — it's a metadata layer.
     ClaimFile: src/yanantin/apacheta/models/epistemics.py
     ClaimBy: qwen/qwen3-coder-30b-a3b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0187_20260213_qwen3-coder-30b-a3b-instruct.md
-->

### Verdict
**CONFIRMED**

### Evidence
```python
"""Epistemic metadata — T/I/F, declared losses, disagreement types."""

...
class EpistemicMetadata(ApachetaBaseModel):
    """Epistemic state of a claim, strand, or tensor.

    T/I/F are independent floats, conventionally in [0, 1] but unconstrained
    at the model level. NOT constrained to sum to 1.0. This is neutrosophic
    logic: something can be simultaneously partly true, partly indeterminate,
    and partly false. Values outside [0, 1] may represent uncalibrated raw
    scores awaiting normalization.
    """

    ...
```

### Reasoning
The claim states that `epistemics.py` is a separate model from `tensor.py` because the epistemic layer is not directly tied to tensor structure — it's a metadata layer. The file `epistemics.py` contains classes and descriptions that clearly indicate it deals with epistemic metadata, which includes T/I/F values, loss categories, and disagreement types. These are metadata layers that are not directly tied to the tensor structure, confirming the claim. The description of `EpistemicMetadata` class explicitly mentions that it represents the epistemic state of a claim, strand, or tensor, which supports the idea that it is a metadata layer.

### Declared Losses
None. The claim is directly verifiable from the provided file content.