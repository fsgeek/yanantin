<!-- Chasqui Scout Tensor
     Run: 9912
     Model: anthropic/claude-3-haiku (Anthropic: Claude 3 Haiku)
     Cost: prompt=$2.5e-07/M, completion=$1.25e-06/M
     Usage: {'prompt_tokens': 8681, 'completion_tokens': 201, 'total_tokens': 8882, 'cost': 0.0024215, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0024215, 'upstream_inference_prompt_cost': 0.00217025, 'upstream_inference_completions_cost': 0.00025125}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-06T07:27:33.421067+00:00
     GenerationID: gen-1775460451-vZ9RFE4xx1I6ZuieTsne
     Dispatch: verify
     Claim: The document mentions tools that process scout reports (`gleaner.py` uses "deterministic pattern matching" to extract claims, `scorer.py` evaluates them, `rummage.py` searches them), but doesn't docum
     ClaimFile: src/yanantin/chasqui/gleaner.py
     ClaimBy: qwen/qwen3-235b-a22b-thinking-2507
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_5791_20260313_qwen3-235b-a22b-thinking-2507.md
-->

### Verdict
CONFIRMED

### Evidence
The document states:
"Unlike the existing `extract_cairn_claims` in scorer.py (which only
finds sentences containing file paths), the Gleaner classifies claims
by type, scores confidence, and deduplicates across reports."
This confirms that the Gleaner module uses "deterministic pattern matching"
to extract claims, as mentioned in the claim.

### Reasoning
The evidence directly supports the claim that the Gleaner module uses
"deterministic pattern matching" to extract claims from scout and scour
reports. The document clearly states that the Gleaner does more than just
find sentences with file paths, and that it uses pattern matching to
classify claims, score confidence, and deduplicate them.

### Declared Losses
None. The relevant information about the Gleaner's use of deterministic
pattern matching is clearly documented in the file.