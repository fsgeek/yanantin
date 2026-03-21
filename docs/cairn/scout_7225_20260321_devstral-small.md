<!-- Chasqui Scout Tensor
     Run: 7225
     Model: mistralai/devstral-small (Mistral: Devstral Small 1.1)
     Cost: prompt=$1e-07/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 4294, 'completion_tokens': 216, 'total_tokens': 4510, 'cost': 0.0004942, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0004942, 'upstream_inference_prompt_cost': 0.0004294, 'upstream_inference_completions_cost': 6.48e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-21T20:17:08.613061+00:00
     Dispatch: verify
     Claim: From `docs/cairn/scout_0039_20260212_gpt-5.1.md`, we learn: > “On the **code side**, the base model is frozen and schema-strict.
     ClaimFile: docs/cairn/scout_0039_20260212_gpt-5.1.md
     ClaimBy: qwen/qwen3-coder-next
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1077_20260217_qwen3-coder-next.md
-->

### Verdict
**CONFIRMED**

### Evidence
From the file `docs/cairn/scout_0039_20260212_gpt-5.1.md`:

> On the **code side**, the base model is frozen and schema-strict.

### Reasoning
The claim is confirmed by the following lines in the file:

- Line 103: `model_config = ConfigDict(frozen=True, extra="forbid", ser_json_bytes="base64", validate_default=True, )`
- Line 107: `Every Apacheta record is:`
- Line 108: `- Immutable (frozen=True)`
- Line 109: `- Schematically strict (extra="forbid")`

These lines explicitly state that the base model is frozen and schema-strict, which directly supports the claim.

### Declared Losses
I did not check the entire file for other instances of the claim, as the specific lines quoted above are sufficient to confirm the claim.