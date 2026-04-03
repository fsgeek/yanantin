<!-- Chasqui Scout Tensor
     Run: 9428
     Model: mistralai/mistral-small-3.2-24b-instruct (Mistral: Mistral Small 3.2 24B)
     Cost: prompt=$7.5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 3906, 'completion_tokens': 307, 'total_tokens': 4213, 'cost': 0.00035435, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00035435, 'upstream_inference_prompt_cost': 0.00029295, 'upstream_inference_completions_cost': 6.14e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-03T15:14:16.303097+00:00
     GenerationID: gen-1775229254-x2cgXCzDmoZ4PNF5kSBm
     Dispatch: verify
     Claim: Garbage is treated as contagious at multiple levels**   In `test_governance.py`: - There’s claim-level filtering (`is_garbage`)   - And model-level filtering (garbage ratio threshold)   The interestin
     ClaimFile: tests/red_bar/test_governance.py
     ClaimBy: openai/gpt-5.3-chat
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_8716_20260330_gpt-5.3-chat.md
-->

### Verdict
**CONFIRMED**

### Evidence
1. **Claim-level filtering (`is_garbage`)**:
   - Line 104: `assert "is_garbage" in source, (`
   - Line 105: `"analyst.py must contain is_garbage(). Individual claim-level "`
   - Line 106: `"garbage detection is needed alongside model-level filtering."`

2. **Model-level filtering (garbage ratio threshold)**:
   - Line 120: `assert "garbage_ratio" in filter_source or "garbage_threshold" in filter_source, (`
   - Line 121: `"filter_garbage must check model-level garbage ratio, not just "`
   - Line 122: `"individual claims. A model with >50% garbage is a broken model "`
   - Line 123: `"— even its 'good' output is also suspect."`

### Reasoning
The evidence confirms the claim that `test_governance.py` includes both claim-level filtering (`is_garbage`) and model-level filtering (garbage ratio threshold). The file explicitly checks for the presence of `is_garbage` in the `analyst` module and verifies that the `filter_garbage` function checks the model-level garbage ratio.

### Declared Losses
None. The claim is fully verifiable based on the provided file content.