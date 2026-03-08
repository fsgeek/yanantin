<!-- Chasqui Scout Tensor
     Run: 5024
     Model: essentialai/rnj-1-instruct (EssentialAI: Rnj 1 Instruct)
     Cost: prompt=$1.5e-07/M, completion=$1.5e-07/M
     Usage: {'prompt_tokens': 790, 'completion_tokens': 391, 'total_tokens': 1181, 'cost': 0.00017715, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00017715, 'upstream_inference_prompt_cost': 0.0001185, 'upstream_inference_completions_cost': 5.865e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-08T07:07:37.679584+00:00
     Dispatch: verify
     Claim: **What I know:** - The code implements a "duality" principle (`correct.py` preserves the original).
     ClaimFile: src/yanantin/apacheta/operators/correct.py
     ClaimBy: z-ai/glm-4.7-flash
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1327_20260218_glm-4.7-flash.md
-->

THOUGHT: I need to verify the claim that the `correct` function in `correct.py` preserves the original claim. The function creates a `CorrectionRecord`, which includes both the original and corrected claims, so the original is indeed stored and preserved. The docstring explicitly states "Original is preserved — always queryable," which directly supports the claim. Since the code clearly implements this preservation by storing the original in the record, I confirm the claim is accurate.

RESPONSE: ### Verdict  
**CONFIRMED**  

### Evidence  
```python
def correct(
    interface: ApachetaInterface,
    target_tensor: UUID,
    original_claim: str,
    corrected_claim: str,
    *,
    correcting_tensor: UUID | None = None,
    target_strand_index: int | None = None,
    target_claim_id: UUID | None = None,
    evidence: str = "",
    provenance: ProvenanceEnvelope | None = None,
) -> CorrectionRecord:
    """Correct a prior claim. Original is preserved — always queryable.
    """
    prov = provenance or ProvenanceEnvelope()
    correction = CorrectionRecord(
        target_tensor=target_tensor,
        target_strand_index=target_strand_index,
        target_claim_id=target_claim_id,
        original_claim=original_claim,  # Original preserved here
        corrected_claim=corrected_claim,
        evidence=evidence,
        provenance=prov,
    )
    interface.store_correction(correction)
```

### Reasoning  
The function explicitly creates a `CorrectionRecord` that includes the `original_claim` parameter as a field, ensuring the original claim is stored and preserved. The docstring further affirms this behavior: *"Original is preserved — always queryable."* This directly implements the "duality" principle described in the claim.

### Declared Losses  
None. The claim aligns directly with the code's behavior and documentation.