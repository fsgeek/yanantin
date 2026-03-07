<!-- Chasqui Scout Tensor
     Run: 4854
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 1194, 'completion_tokens': 463, 'total_tokens': 1657, 'cost': 4.24e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 4.24e-05, 'upstream_inference_prompt_cost': 2.388e-05, 'upstream_inference_completions_cost': 1.852e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-07T07:28:09.785180+00:00
     Dispatch: verify
     Claim: Not only is it tracked at the data level (as seen in the `ProvenanceEnvelope` classes and the `ProvenanceRecord` in `tests/unit/test_provenance.py`), but it also seems to be a fundamental aspect of th
     ClaimFile: tests/red_bar/test_provenance.py
     ClaimBy: mistralai/mistral-nemo
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0244_20260213_mistral-nemo.md
-->

### Verdict
**CONFIRMED**

### Evidence
```
"""Red-bar test: Provenance invariant.

Every record has provenance. This is structural, not optional.
"""
```
```
assert isinstance(tensor.provenance, ProvenanceEnvelope)
```
```
assert isinstance(edge.provenance, ProvenanceEnvelope)
```
```
assert isinstance(corr.provenance, ProvenanceEnvelope)
```
```
assert isinstance(d.provenance, ProvenanceEnvelope)
```
```
assert isinstance(n.provenance, ProvenanceEnvelope)
```
```
assert isinstance(b.provenance, ProvenanceEnvelope)
```
```
assert isinstance(e.provenance, ProvenanceEnvelope)
```
```
assert isinstance(e.provenance, ProvenanceEnvelope)
```
```
assert isinstance(e.provenance, ProvenanceEnvelope)
```
```
assert isinstance(e.provenance, ProvenanceEnvelope)
```
### Reasoning
The file's docstring explicitly states, "Every record has provenance. This is structural, not optional." This directly supports the claim that provenance is a fundamental aspect of the project's data models.

Furthermore, the test cases within the file demonstrate that various record types (TensorRecord, CompositionEdge, CorrectionRecord, DissentRecord, NegationRecord, BootstrapRecord, SchemaEvolutionRecord, EntityResolution) all have a `provenance` attribute, and this attribute is of type `ProvenanceEnvelope`. This confirms that provenance is indeed a fundamental aspect of these data structures.

The claim also suggests that provenance is part of the project's governance structures. While the provided file only shows the data models, the existence of a `ProvenanceEnvelope` and its inclusion in multiple record types strongly implies that provenance tracking is a core part of how data is managed and potentially governed within the `yanantin.apacheta` project.

### Declared Losses
The claim mentions that provenance is a fundamental aspect of the project's narrative and governance structures. While the code shows provenance tracking at the data level, I cannot determine the extent to which this influences the project's overall narrative or broader governance structures based solely on this file.