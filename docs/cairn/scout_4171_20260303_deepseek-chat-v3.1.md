<!-- Chasqui Scout Tensor
     Run: 4171
     Model: deepseek/deepseek-chat-v3.1 (DeepSeek: DeepSeek V3.1)
     Cost: prompt=$1.5e-07/M, completion=$7.5e-07/M
     Usage: {'prompt_tokens': 555, 'completion_tokens': 210, 'total_tokens': 765, 'cost': 0.00024075, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00024075, 'upstream_inference_prompt_cost': 8.325e-05, 'upstream_inference_completions_cost': 0.0001575}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-03T09:02:10.856849+00:00
     Dispatch: verify
     Claim: This directly supports the claim that `src/yanantin/apacheta/models/base.py` (line 3) sets `frozen=True, extra="forbid"` for Apacheta entities.
     ClaimFile: src/yanantin/apacheta/models/base.py
     ClaimBy: google/gemma-3n-e4b-it
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_2350_20260222_gemma-3n-e4b-it.md
-->

### Verdict
**CONFIRMED**

### Evidence
Lines 13-17 from `src/yanantin/apacheta/models/base.py`:
```
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        ser_json_bytes="base64",
        validate_default=True,
    )
```

### Reasoning
The claim states that the file sets `frozen=True, extra="forbid"` for Apacheta entities. The evidence shows exactly these two configurations (`frozen=True` and `extra="forbid"`) are present in the `ConfigDict` for the `ApachetaBaseModel` class, which serves as the base model for all Apacheta data models. The claim specifically references line 3, but the actual configuration occurs later in the file (lines 14-15). However, the substance of the claim about the presence of these specific configuration values is accurate settings is fully verifiable from the source code provided.