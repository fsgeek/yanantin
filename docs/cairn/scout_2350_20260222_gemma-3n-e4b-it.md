<!-- Chasqui Scout Tensor
     Run: 2350
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 607, 'completion_tokens': 189, 'total_tokens': 796, 'cost': 1.97e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 1.97e-05, 'upstream_inference_prompt_cost': 1.214e-05, 'upstream_inference_completions_cost': 7.56e-06}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-22T17:47:30.293845+00:00
     Dispatch: verify
     Claim: `src/yanantin/apacheta/models/base.py` (line 3) sets `frozen=True, extra="forbid"` for Apacheta entities, which creates immutable, strictly-typed records.
     ClaimFile: src/yanantin/apacheta/models/base.py
     ClaimBy: minimax/minimax-m2-her
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0131_20260212_minimax-m2-her.md
-->

### Verdict
**CONFIRMED**

### Evidence
```
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        ser_json_bytes="base64",
        validate_default=True,
    )
```

### Reasoning
The file shows that the `model_config` is set with `frozen=True` and `extra="forbid"`. This directly supports the claim that `src/yanantin/apacheta/models/base.py` (line 3) sets `frozen=True, extra="forbid"` for Apacheta entities. The `frozen=True` setting in Pydantic models makes them immutable, and `extra="forbid"` ensures that any fields not defined in the model will raise an error.

### Declared Losses
None. The claim is directly verifiable from the provided file content.