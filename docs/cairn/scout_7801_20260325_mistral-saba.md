<!-- Chasqui Scout Tensor
     Run: 7801
     Model: mistralai/mistral-saba (Mistral: Saba)
     Cost: prompt=$2e-07/M, completion=$6e-07/M
     Usage: {'prompt_tokens': 643, 'completion_tokens': 264, 'total_tokens': 907, 'cost': 0.000287, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.000287, 'upstream_inference_prompt_cost': 0.0001286, 'upstream_inference_completions_cost': 0.0001584}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-25T00:26:41.646310+00:00
     GenerationID: gen-1774398400-Ne5CcZ5hmNPWkA8ZwvcZ
     Dispatch: verify
     Claim: ### Verdict DENIED ### Evidence The file `src/yanantin/apacheta/interface/errors.py` contains the following classes: ```python class ImmutabilityError(ApachetaError): """Raised when attempting to over
     ClaimFile: src/yanantin/apacheta/interface/errors.py
     ClaimBy: qwen/qwen-2.5-7b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0017_20260212_qwen-2.5-7b-instruct.md
-->

### Verdict
CONFIRMED

### Evidence
The file `src/yanantin/apacheta/interface/errors.py` contains:
```python
class ImmutabilityError(ApachetaError):
    """Raised when attempting to overwrite an existing record."""

class AccessDeniedError(ApachetaError):
    """Raised when an operation is denied by access control."""

class NotFoundError(ApachetaError):
    """Raised when a requested record does not exist."""
```

### Reasoning
The claim states that `ImmutabilityError` is placed alongside `NotFoundError` as fundamental constraints. The evidence shows:
1. Both `ImmutabilityError` and `NotFoundError` are defined as subclasses of `ApachetaError`.
2. They are adjacent in the file (with `AccessDeniedError` between them, which the claim did not deny).
3. The docstrings confirm their roles as constraint-related exceptions (`ImmutabilityError` for overwrite attempts, `NotFoundError` for missing records).
The claim is accurate, though it omits `AccessDeniedError`—which does not invalidate the core claim about the two named errors.

### Declared Losses
None. The file content fully supports the claim.