<!-- Chasqui Scout Tensor
     Run: 9824
     Model: inception/mercury-coder (Inception: Mercury Coder)
     Cost: prompt=$2.5e-07/M, completion=$7.5e-07/M
     Usage: {'prompt_tokens': 948, 'completion_tokens': 344, 'total_tokens': 1292, 'cost': 0.000494325, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 3, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.000494325, 'upstream_inference_prompt_cost': 0.000236325, 'upstream_inference_completions_cost': 0.000258}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-05T20:03:00.123706+00:00
     GenerationID: gen-1775419378-pViwIs0tu6xOpetO1OJd
     Dispatch: verify
     Claim: ### Reasoning The claim states: "In `src/yanantin/apacheta/models/epistemics.py` (tested in `tests/unit/test_models.py`), there is the `EpistemicMetadata` model." Evidence shows: - `EpistemicMetadata`
     ClaimFile: src/yanantin/apacheta/models/epistemics.py
     ClaimBy: allenai/olmo-3.1-32b-instruct
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_3030_20260225_olmo-3.1-32b-instruct.md
-->

### Verdict
**CONFIRMED**

### Evidence
The file `src/yanantin/apacheta/models/epistemics.py` contains the definition of the `EpistemicMetadata` class:

```
class EpistemicMetadata(ApachetaBaseModel):
    """Epistemic state of a claim, strand, or tensor.

    T/I/F are independent floats, conventionally in [0, 1] but unconstrained
    at the model level. NOT constrained to sum to 1.0. This is neutrosophic
    logic: something can be simultaneously partly true, partly indeterminate,
    and partly false. Values outside [0, 1] may represent uncalibrated raw
    scores awaiting normalization.
    """

    representation_type: RepresentationType = RepresentationType.SCALAR
    truth: float = 0.0
    indeterminacy: float = 0.0
    falsity: float = 0.0
    functional_spec: dict | None = None
    scope_boundaries: tuple[str, ...] = Field(default_factory=tuple)
    disagreement_type: DisagreementType | None = None
```

### Reasoning
The claim asserts that the file contains the `EpistemicMetadata` model. The quoted snippet shows the class definition with the exact name `EpistemicMetadata`. Therefore, the claim is accurate. The mention of testing in `tests/unit/test_models.py` is unrelated to the presence of the class in the source file and does not affect the verification of the claim.

### Declared Losses
None. All relevant information needed to assess the claim is present in the source file.