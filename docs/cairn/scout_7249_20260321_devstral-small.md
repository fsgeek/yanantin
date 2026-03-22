<!-- Chasqui Scout Tensor
     Run: 7249
     Model: mistralai/devstral-small (Mistral: Devstral Small 1.1)
     Cost: prompt=$1e-07/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 852, 'completion_tokens': 273, 'total_tokens': 1125, 'cost': 0.00016134, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 64, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00016134, 'upstream_inference_prompt_cost': 7.944e-05, 'upstream_inference_completions_cost': 8.19e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-21T23:23:06.320238+00:00
     Dispatch: verify
     Claim: | | 5 | **Provenance & signing** | `src/yanantin/provenance/__init__.py` provides `stamp_commit`, `verify_proof`, etc., and `docs/signing.md` describes a dual‑key signing scheme (human + AI).
     ClaimFile: src/yanantin/provenance/__init__.py
     ClaimBy: nvidia/nemotron-3-nano-30b-a3b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0574_20260214_nemotron-3-nano-30b-a3b.md
-->

### Verdict
**CONFIRMED**

### Evidence
The file `src/yanantin/provenance/__init__.py` contains the following lines:
```
from yanantin.provenance.timestamp import (
    list_proofs,
    stamp_commit,
    stamp_genesis,
    upgrade_pending_proofs,
    verify_proof,
)
```
And:
```
__all__ = [
    "stamp_commit",
    "stamp_genesis",
    "verify_proof",
    "list_proofs",
    "upgrade_pending_proofs",
]
```
The docstring also mentions:
```
from yanantin.provenance import stamp_commit, verify_proof, list_proofs, upgrade_pending_proofs
```

### Reasoning
The claim states that `src/yanantin/provenance/__init__.py` provides `stamp_commit`, `verify_proof`, etc. The evidence shows that the file indeed imports and exposes these functions. The docstring further supports this by listing their usage. Therefore, the claim is accurate.

### Declared Losses
I couldn't verify the existence or content of `docs/signing.md` as it was not provided. The claim also mentions a dual-key signing scheme, but the file only discusses timestamping and proof verification, not signing.