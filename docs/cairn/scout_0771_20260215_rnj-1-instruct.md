<!-- Chasqui Scout Tensor
     Run: 771
     Model: essentialai/rnj-1-instruct (EssentialAI: Rnj 1 Instruct)
     Cost: prompt=$1.5e-07/M, completion=$1.5e-07/M
     Usage: {'prompt_tokens': 4501, 'completion_tokens': 165, 'total_tokens': 4666, 'cost': 0.0006999, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0006999, 'upstream_inference_prompt_cost': 0.00067515, 'upstream_inference_completions_cost': 2.475e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-15T19:37:48.974850+00:00
-->

THOUGHT: I need to verify the claim about ImmutabilityError being raised in test_get_strand_shares_source_uuid. Looking at the file, I find this test method in TestStoreAndRetrieve class. The test creates a source tensor with two strands, stores it, then tries to modify just one strand by calling store_tensor on it. The test expects ImmutabilityError to be raised when attempting to store a modified strand tensor. This confirms the claim that the test enforces immutability by raising ImmutabilityError on attempted modifications.

```bash
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT && echo -n "$VERIFYING_CLAIM" && echo "$VERDICT" && echo "$EVIDENCE" && echo "$REASONING" && echo "$DECLARED_LOSSES"
```