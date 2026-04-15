<!-- Chasqui Scout Tensor
     Run: 11366
     Model: qwen/qwen3-coder-30b-a3b-instruct (Qwen: Qwen3 Coder 30B A3B Instruct)
     Cost: prompt=$7e-08/M, completion=$2.7e-07/M
     Usage: {'prompt_tokens': 1481, 'completion_tokens': 466, 'total_tokens': 1947, 'cost': 0.0002879, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0002879, 'upstream_inference_prompt_cost': 0.0001481, 'upstream_inference_completions_cost': 0.0001398}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-14T06:03:31.431278+00:00
     GenerationID: gen-1776146609-9XNDoGc8YgY6PelggX5Z
     Dispatch: verify
     Claim: ### The File Here is the actual content of `src/yanantin/apacheta/models/composition.py`: ``` """Composition models — edges, corrections, dissent, negation, bootstrap, evolution.""" from __future__ im
     ClaimFile: src/yanantin/apacheta/models/composition.py
     ClaimBy: meta-llama/llama-3.2-1b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_8030_20260326_llama-3.2-1b-instruct.md
-->

### Verdict
**DENIED**

### Evidence
The claim states:
> ```python
> class CorrectionRecord(ApachetaBaseModel):
>     """A correction to a prior claim.
> 
>     ## The File
> 
>     Original is preserved."""
> 
>     id: UUID = Field(default_factory=uuid4)
>     target_tensor: UUID
>     target_strand_index: int | None = None
>     target_claim_id: UUID | None = None
>     original_claim: str
>     corrected_claim: str
>     evidence: str = ""
>     provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)
> ```

However, the actual file contains:
```python
class CorrectionRecord(ApachetaBaseModel):
    """A correction to a prior claim. Original is preserved."""

    id: UUID = Field(default_factory=uuid4)
    target_tensor: UUID
    target_strand_index: int | None = None
    target_claim_id: UUID | None = None
    original_claim: str
    corrected_claim: str
    evidence: str = ""
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)
```

### Reasoning
The claim inaccurately describes the docstring for `CorrectionRecord` as:
> """A correction to a prior claim.  
> 
> ## The File  
> 
> Original is preserved."""

This phrasing is not present in the actual file. The real docstring is:
> """A correction to a prior claim. Original is preserved."""

There is also a structural misalignment in the claim’s formatting which suggests a transcription error or hallucination by the model. The actual content matches the real file except for formatting and an incorrect header (`## The File`) that does not appear in the real file.

Additionally, the claim seems to imply that the file includes a section labeled `## The File` within the class docstring — which is not valid Python syntax and not part of the real source.

### Declared Losses
None. The comparison is direct and complete. The discrepancy lies entirely in the claim’s representation of the docstring and structure.

**Final Status**: The claim is **DENIED**.