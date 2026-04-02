<!-- Chasqui Scout Tensor
     Run: 9309
     Model: nvidia/nemotron-3-nano-30b-a3b (NVIDIA: Nemotron 3 Nano 30B A3B)
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 1021, 'completion_tokens': 451, 'total_tokens': 1472, 'cost': 0.00014125, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00014125, 'upstream_inference_prompt_cost': 5.105e-05, 'upstream_inference_completions_cost': 9.02e-05}, 'completion_tokens_details': {'reasoning_tokens': 334, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-02T23:11:14.576639+00:00
     GenerationID: gen-1775171468-UDtLntqghNToZRNOF0MK
     Dispatch: verify
     Claim: In `scout_6572_20260318_llama-3-8b-instruct.md`, it’s claimed to use regex-only parsing.
     ClaimFile: docs/cairn/scout_6572_20260318_llama-3-8b-instruct.md
     ClaimBy: qwen/qwen-plus-2025-07-28
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_8126_20260326_qwen-plus-2025-07-28.md
-->

### Verdict
**CONFIRMED**

### Evidence
The file contains the following explicit statement:

```
Deterministic: regex and keyword matching only, no LLM calls.
```

This line directly asserts that the parsing is performed using only regex (and keyword matching), with no reliance on language‑model calls.

### Reasoning
The claim states that the document “uses regex-only parsing.” The quoted line confirms that the parsing method is “regex and keyword matching only,” which is precisely regex‑only parsing. No contradictory statements appear elsewhere in the file, so the evidence fully supports the claim.

### Declared Losses
None. The relevant line is present and clearly expresses the parsing approach, so nothing remains unverifiable.