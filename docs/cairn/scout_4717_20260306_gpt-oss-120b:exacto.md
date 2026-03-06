<!-- Chasqui Scout Tensor
     Run: 4717
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 757, 'completion_tokens': 683, 'total_tokens': 1440, 'cost': 0.00016688, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 6, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00016688, 'upstream_inference_prompt_cost': 3.028e-05, 'upstream_inference_completions_cost': 0.0001366}, 'completion_tokens_details': {'reasoning_tokens': 469, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-06T12:36:27.317811+00:00
     Dispatch: verify
     Claim: Here are the specific lines that support this: - Line 1: The file starts with a docstring that defines it as containing "Tensor and strand records — the core data unit of Apacheta." - Line 3: The file
     ClaimFile: src/yanantin/apacheta/models/provenance.py
     ClaimBy: mistralai/mistral-nemo
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0212_20260213_mistral-nemo.md
-->

### Verdict
**DENIED**

### Evidence
```python
"""Provenance models — who made this, when, from what context."""
# ^ Line 1: docstring does NOT contain "Tensor and strand records — the core data unit of Apacheta."

from __future__ import annotations
# ^ Line 3 (counting from the start of the file) imports __future__, not ProvenanceEnvelope.
```

### Reasoning
- **Line 1** of the file is a docstring that reads *"Provenance models — who made this, when, from what context."* It does **not** mention *"Tensor and strand records — the core data unit of Apacheta."* Therefore the claim about the docstring is inaccurate.
- **Line 3** (the third non‑empty line) is `from __future__ import annotations`, which imports a future feature, not `ProvenanceEnvelope`. Moreover, `ProvenanceEnvelope` is **defined** in this file, not imported from elsewhere. Hence the claim about an import on line 3 is also inaccurate.

Both parts of the claim are contradicted by the actual source code.

### Declared Losses
None. All referenced lines are present in the provided source code, allowing a complete verification.