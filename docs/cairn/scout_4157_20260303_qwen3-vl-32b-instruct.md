<!-- Chasqui Scout Tensor
     Run: 4157
     Model: qwen/qwen3-vl-32b-instruct (Qwen: Qwen3 VL 32B Instruct)
     Cost: prompt=$1.04e-07/M, completion=$4.16e-07/M
     Usage: {'prompt_tokens': 797, 'completion_tokens': 534, 'total_tokens': 1331, 'cost': 0.000305032, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00046928, 'upstream_inference_prompt_cost': 0.00012752, 'upstream_inference_completions_cost': 0.00034176}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-03T07:27:48.636862+00:00
     Dispatch: verify
     Claim: The `bootstrap.py` operator selects tensors for context budget, while `correct.py` records corrections and automatically creates a correction edge.
     ClaimFile: src/yanantin/apacheta/operators/correct.py
     ClaimBy: ibm-granite/granite-4.0-h-micro
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0082_20260212_granite-4.0-h-micro.md
-->

### Verdict
CONFIRMED

### Evidence
> """Correct operator — creates a correction record and composition edge."""

> def correct(
>     interface: ApachetaInterface,
>     target_tensor: UUID,
>     original_claim: str,
>     corrected_claim: str,
>     *,
>     correcting_tensor: UUID | None = None,
>     target_strand_index: int | None = None,
>     target_claim_id: UUID | None = None,
>     evidence: str = "",
>     provenance: ProvenanceEnvelope | None = None,
> ) -> CorrectionRecord:
>     """Correct a prior claim. Original is preserved — always queryable.
>
>     Creates both a CorrectionRecord and a CompositionEdge (type=corrects).
>     """
>     prov = provenance or ProvenanceEnvelope()
>     correction = CorrectionRecord(
>         target_tensor=target_tensor,
>         target_strand_index=target_strand_index,
>         target_claim_id=target_claim_id,
>         original_claim=original_claim,
>         corrected_claim=corrected_claim,
>         evidence=evidence,
>         provenance=prov,
>     )
>     interface.store_correction(correction)
>
>     if correcting_tensor is not None:
>         edge = CompositionEdge(
>             from_tensor=correcting_tensor,
>             to_tensor=target_tensor,
>             relation_type=RelationType.CORRECTS,
>             provenance=prov,
>         )
>         interface.store_composition_edge(edge)
>
>     return correction

### Reasoning
The claim states that `correct.py` "records corrections and automatically creates a correction edge." The file’s docstring explicitly states: “Creates both a CorrectionRecord and a CompositionEdge (type=corrects).” The function `correct` creates a `CorrectionRecord` object and stores it via `interface.store_correction(correction)`. It then conditionally creates and stores a `CompositionEdge` with `relation_type=RelationType.CORRECTS` if `correcting_tensor` is provided. This directly supports the claim that the file records corrections and creates a correction edge.

The claim also references `bootstrap.py` selecting tensors for context budget — this is outside the scope of the provided file and not verifiable here, but the part of the claim referring to `correct.py` is fully supported.

### Declared Losses
I cannot verify the behavior of `bootstrap.py` or whether it selects tensors for context budget, as that file is not provided. However, the claim about `correct.py` is fully verifiable from the given file.