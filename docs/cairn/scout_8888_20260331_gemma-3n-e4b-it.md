<!-- Chasqui Scout Tensor
     Run: 8888
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 1156, 'completion_tokens': 860, 'total_tokens': 2016, 'cost': 5.752e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 5.752e-05, 'upstream_inference_prompt_cost': 2.312e-05, 'upstream_inference_completions_cost': 3.44e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-31T14:40:08.849683+00:00
     GenerationID: gen-1774967986-14FWCvzIRX2JdDnGmDD8
     Dispatch: verify
     Claim: - `test_provenance.py`: Tests verifying the presence of provenance information in different data structures.
     ClaimFile: tests/red_bar/test_provenance.py
     ClaimBy: amazon/nova-micro-v1
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_1058_20260216_nova-micro-v1.md
-->

### Verdict
CONFIRMED

### Evidence
```
"""Red-bar test: Provenance invariant.

Every record has provenance. This is structural, not optional.
"""
```
```
def test_tensor_has_provenance():
    tensor = TensorRecord()
    assert isinstance(tensor.provenance, ProvenanceEnvelope)
    assert tensor.provenance.interface_version == "v1"
```
```
def test_composition_edge_has_provenance():
    edge = CompositionEdge(
        from_tensor=uuid4(),
        to_tensor=uuid4(),
        relation_type=RelationType.COMPOSES_WITH,
    )
    assert isinstance(edge.provenance, ProvenanceEnvelope)
```
```
def test_correction_has_provenance():
    corr = CorrectionRecord(
        target_tensor=uuid4(),
        original_claim="old",
        corrected_claim="new",
    )
    assert isinstance(corr.provenance, ProvenanceEnvelope)
```
```
def test_dissent_has_provenance():
    d = DissentRecord(
        target_tensor=uuid4(),
        alternative_framework="alt",
        reasoning="because",
    )
    assert isinstance(d.provenance, ProvenanceEnvelope)
```
```
def test_negation_has_provenance():
    n = NegationRecord(
        tensor_a=uuid4(),
        tensor_b=uuid4(),
        reasoning="different lineages",
    )
    assert isinstance(n.provenance, ProvenanceEnvelope)
```
```
def test_bootstrap_has_provenance():
    b = BootstrapRecord(
        instance_id="test",
    )
    assert isinstance(b.provenance, ProvenanceEnvelope)
```
```
def test_evolution_has_provenance():
    e = SchemaEvolutionRecord(
        from_version="v1",
        to_version="v2",
    )
    assert isinstance(e.provenance, ProvenanceEnvelope)
```
```
def test_entity_has_provenance():
    e = EntityResolution(
        entity_uuid=uuid4(),
        identity_type="ai",
    )
    assert isinstance(e.provenance, ProvenanceEnvelope)
```
```
def test_stored_records_retain_provenance():
    """Provenance survives store/retrieve roundtrip."""
    backend = InMemoryBackend()
    tensor = TensorRecord(
        provenance=ProvenanceEnvelope(
            author_model_family="claude",
            author_instance_id="test-session",
        ),
    )
    backend.store_tensor(tensor)
    retrieved = backend.get_tensor(tensor.id)
    assert retrieved.provenance.author_model_family == "claude"
    assert retrieved.provenance.author_instance_id == "test-session"
```

### Reasoning
The file contains multiple test functions (`test_...`) that explicitly assert that different data structure instances (like `TensorRecord`, `CompositionEdge`, `CorrectionRecord`, etc.) have a `provenance` attribute, and that this attribute is an instance of `ProvenanceEnvelope`. The claim states that the tests verify the presence of provenance information in different data structures. The provided file demonstrates this directly through the `assert isinstance(tensor.provenance, ProvenanceEnvelope)` statements in each test function. Therefore, the claim is accurate.

### Declared Losses
The claim mentions "different data structures". While the tests cover a variety of these, the file doesn't enumerate *all* possible data structures that might exist in the system. However, the tests provide sufficient evidence to support the claim that provenance is verified for *at least* the data structures tested. I cannot check if the tests cover all possible data structures that might be part of the system.