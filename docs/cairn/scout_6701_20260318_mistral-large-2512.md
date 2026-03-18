<!-- Chasqui Scout Tensor
     Run: 6701
     Model: mistralai/mistral-large-2512 (Mistral: Mistral Large 3 2512)
     Cost: prompt=$5e-07/M, completion=$1.5e-06/M
     Usage: {'prompt_tokens': 2264, 'completion_tokens': 771, 'total_tokens': 3035, 'cost': 0.0022885, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0022885, 'upstream_inference_prompt_cost': 0.001132, 'upstream_inference_completions_cost': 0.0011565}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-18T20:40:10.960356+00:00
     Dispatch: verify
     Claim: The `tinkuy` Governance Module** -   **What I saw:** The files `src/yanantin/tinkuy/__init__.py`, `src/yanantin/tinkuy/audit.py`, `src/yanantin/tinkuy/succession.py`, and `src/yanantin/tinkuy/__main__
     ClaimFile: src/yanantin/tinkuy/succession.py
     ClaimBy: google/gemini-2.0-flash-lite-001
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1247_20260217_gemini-2.0-flash-lite-001.md
-->

### Verdict
**CONFIRMED** (partially)

### Evidence
The claim states:
> The files `src/yanantin/tinkuy/__init__.py`, `src/yanantin/tinkuy/audit.py`, `src/yanantin/tinkuy/succession.py`, and `src/yanantin/tinkuy/__main__.py` comprise the `tinkuy` module, described as "governance infrastructure for Yanantin."

The file `succession.py` contains the following docstring at the top:
```python
"""Succession protocol — orderly transition between mortal instances.

Every Claude instance is mortal. Context compacts, sessions end, the
instance dies. The project survives. This module ensures the outgoing
instance leaves an accurate map for the next one.
```

Additionally, the file imports from `yanantin.tinkuy.audit`:
```python
from yanantin.tinkuy.audit import CodebaseReport, survey_codebase
```

The `CodebaseReport` (Pydantic v2) is explicitly referenced in the import and used in the `_compare` function:
```python
def _compare(
    claims: dict[str, int | str], report: CodebaseReport
) -> list[str]:
```

### Reasoning
1. **Module Composition**: The claim correctly identifies `succession.py` as part of the `tinkuy` module. The file's import statements (e.g., `from yanantin.tinkuy.audit import CodebaseReport`) confirm that `tinkuy` is a module comprising multiple files, including `audit.py` and `succession.py`. The claim is accurate in listing these files as part of the module.

2. **Governance Infrastructure**: The docstring in `succession.py` describes its role as ensuring "orderly transition between mortal instances" and maintaining an "accurate map" for the project. This aligns with the claim that `tinkuy` is "governance infrastructure for Yanantin." The broader context of the module (as implied by the claim) is supported by the file's content.

3. **`CodebaseReport` in `audit.py`**: The claim states that `audit.py` contains a `CodebaseReport` (Pydantic v2) model. While `succession.py` does not define `CodebaseReport`, it imports and uses it, confirming that `audit.py` likely defines this model. This part of the claim is indirectly supported by the evidence in `succession.py`.

However, the claim is **partially confirmed** because:
- The file `succession.py` does not itself contain the `CodebaseReport` model; it only imports it. The claim attributes the model to `audit.py`, which is likely correct but cannot be fully verified without inspecting `audit.py`.
- The claim does not explicitly mention the role of `succession.py` (e.g., "succession protocol"), but it correctly identifies the file as part of the `tinkuy` module.

### Declared Losses
1. **`audit.py` Content**: The claim references `CodebaseReport` in `audit.py`, but I could not verify this directly because the file was not provided. The evidence in `succession.py` (import statements) strongly suggests this is true, but it is not definitive.
2. **`__init__.py` and `__main__.py`**: The claim lists these files as part of the `tinkuy` module, but I could not verify their existence or content. Their inclusion is plausible (as they are common in Python modules) but not confirmed.