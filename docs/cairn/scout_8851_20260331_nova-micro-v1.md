<!-- Chasqui Scout Tensor
     Run: 8851
     Model: amazon/nova-micro-v1 (Amazon: Nova Micro 1.0)
     Cost: prompt=$3.5e-08/M, completion=$1.4e-07/M
     Usage: {'prompt_tokens': 1122, 'completion_tokens': 334, 'total_tokens': 1456, 'cost': 8.603e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 8.603e-05, 'upstream_inference_prompt_cost': 3.927e-05, 'upstream_inference_completions_cost': 4.676e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-31T09:57:32.079786+00:00
     GenerationID: gen-1774951051-qkkA1XKS2yVriPVwXQ1h
     Dispatch: verify
     Claim: ### Verdict DENIED ### Evidence The file `docs/signing.md` contains no mention of "tensor-level provenance" or `ProvenanceEnvelope` in `src/yanantin/models/base.py`.
     ClaimFile: docs/signing.md
     ClaimBy: qwen/qwen3-14b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1758_20260220_qwen3-14b.md
-->

### Verdict
**DENIED**

### Evidence
The file `docs/signing.md` does not contain any mention of "tensor-level provenance" or `ProvenanceEnvelope` in `src/yanantin/models/base.py`.

### Reasoning
The claim made by `qwen/qwen3-14b` states that "the file `docs/signing.md` contains no mention of 'tensor-level provenance' or `ProvenanceEnvelope` in `src/yanantin/models/base.py`."

To verify this, I have read through the entire content of the `docs/signing.md` file. Here are the relevant excerpts:

```
# Code Signing

## Principle

Every commit carries provenance. AI-authored commits are signed with
an AI key, distinct from human signing keys. The git log becomes an
epistemic observability layer — you can see who authored what,
verifiably.

## Current Keys

### Human (Tony Mason)
...

### AI (Claude Opus)
...

## How Signing Works

...

## Decisions Made

...

## OpenTimestamps

In progress (Tony). Adds signed timestamps to commits for
tamper-resistant temporal provenance. Not tamper-proof, but raises
the cost of falsification.
```

None of these sections contain any mention of "tensor-level provenance" or `ProvenanceEnvelope`. Therefore, the claim made is accurate.

### Declared Losses
There are no losses declared as the verification pertains to a static document, and no runtime behavior was queried or required to be examined.