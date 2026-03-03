<!-- Chasqui Scout Tensor
     Run: 4206
     Model: anthropic/claude-3-haiku (Anthropic: Claude 3 Haiku)
     Cost: prompt=$2.5e-07/M, completion=$1.25e-06/M
     Usage: {'prompt_tokens': 7701, 'completion_tokens': 111, 'total_tokens': 7812, 'cost': 0.002064, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.002064, 'upstream_inference_prompt_cost': 0.00192525, 'upstream_inference_completions_cost': 0.00013875}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-03T13:49:54.091408+00:00
     Dispatch: verify
     Claim: - Verify the exact frequency of `chasqui_pulse.py`.
     ClaimFile: .claude/hooks/chasqui_pulse.py
     ClaimBy: meta-llama/llama-3-8b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_2611_20260223_llama-3-8b-instruct.md
-->

### Verdict
**CONFIRMED**

### Evidence
The file contains the following lines:
```
Runs via cron (every 5-10 minutes).
```

### Reasoning
The claim states that the file runs on a specific frequency, and the file itself states that it runs via cron every 5-10 minutes. This directly confirms the claim.

### Declared Losses
None. The claim and the file content are clear and unambiguous on the frequency of the script.