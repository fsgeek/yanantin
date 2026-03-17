<!-- Chasqui Scout Tensor
     Run: 6533
     Model: thedrummer/rocinante-12b (TheDrummer: Rocinante 12B)
     Cost: prompt=$1.7e-07/M, completion=$4.3e-07/M
     Usage: {'prompt_tokens': 1116, 'completion_tokens': 526, 'total_tokens': 1642, 'cost': 0.0004159, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0004159, 'upstream_inference_prompt_cost': 0.00018972, 'upstream_inference_completions_cost': 0.00022618}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-17T21:11:35.210218+00:00
     Dispatch: verify
     Claim: ### 9️⃣  **Testing for Epistemic Properties**   - **Red‑Bar Tests:** `tests/red_bar/test_immutability.py`, `test_least_privilege.py`, `test_monotonicity.py`, `test_portability.py`, `test_provenance.py
     ClaimFile: tests/red_bar/test_provenance.py
     ClaimBy: openai/gpt-oss-120b
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0448_20260214_gpt-oss-120b.md
-->

### Verdict
CONFIRMED

### Evidence
The file `tests/red_bar/test_provenance.py` contains red-bar tests specifically targeting the `provenance` attribute of various record types in `yanantin.apacheta.models`. Each test function has a name that starts with `test_` followed by the name of the record type (`tensor`, `composition_edge`, `correction`, `dissent`, `negation`, `bootstrap`, `evolution`, `entity`) and ends with `_has_provenance`.

Here are some examples of the test cases:
```python
def test_tensor_has_provenance():
    tensor = TensorRecord()
    assert isinstance(tensor.provenance, ProvenanceEnvelope)
    assert tensor.provenance.interface_version == "v1"

def test_correction_has_provenance():
    corr = CorrectionRecord(
        target_tensor=uuid4(),
        original_claim="old",
        corrected_claim="new",
    )
    assert isinstance(corr.provenance, ProvenanceEnvelope)
```
In each test, the record is initialized with a `provenance` attribute of type `ProvenanceEnvelope`.

### Reasoning
The claim states that there are red-bar tests for testing the `provenance` attribute of different record types. The provided file `test_provenance.py` indeed contains such tests. Each test checks that the `provenance` attribute of a record is an instance of `ProvenanceEnvelope`, which confirms the invariant that every record has provenance.

The tests also confirm that the `provenance` attribute is not optional and is a structural part of the record, as stated in the comment at the top of the file: "Every record has provenance. This is structural, not optional."

### Declared Losses
The evidence presented here is based solely on the source code of the tests. The actual behavior of the code when run is not checked. However, based on the structure of the tests and the specific assertions they make, it is reasonable to conclude that the invariants are enforced by the code when it is executed.

Additionally, the specific implementation details of the record classes and their attributes are not examined. It is assumed that the record classes are defined in such a way that the `provenance` attribute is indeed part of the record structure and not optional.

In conclusion, based on the available evidence, the claim that there are red-bar tests for testing the `provenance` attribute of different record types is confirmed.