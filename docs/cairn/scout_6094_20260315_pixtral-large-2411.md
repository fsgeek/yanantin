<!-- Chasqui Scout Tensor
     Run: 6094
     Model: mistralai/pixtral-large-2411 (Mistral: Pixtral Large 2411)
     Cost: prompt=$2e-06/M, completion=$6e-06/M
     Usage: {'prompt_tokens': 2012, 'completion_tokens': 918, 'total_tokens': 2930, 'cost': 0.009532, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.009532, 'upstream_inference_prompt_cost': 0.004024, 'upstream_inference_completions_cost': 0.005508}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-15T07:23:45.372934+00:00
     Dispatch: verify
     Claim: ### Verdict   **DENIED** ### Evidence   The file `tests/red_bar/test_provenance.py` contains multiple test functions that verify the presence of provenance in various record types: ```python def test_
     ClaimFile: tests/red_bar/test_provenance.py
     ClaimBy: qwen/qwen3-235b-a22b-2507
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0384_20260214_qwen3-235b-a22b-2507.md
-->

### Verdict
**CONFIRMED**

### Evidence
The file `tests/red_bar/test_provenance.py` contains the following test functions that verify the presence of provenance in various record types:

```python
def test_tensor_has_provenance():
    tensor = TensorRecord()
    assert isinstance(tensor.provenance, ProvenanceEnvelope)
    assert tensor.provenance.interface_version == "v1"
```

```python
def test_composition_edge_has_provenance():
    edge = CompositionEdge(
        from_tensor=uuid4(),
        to_tensor=uuid4(),
        relation_type=RelationType.COMPOSES_WITH,
    )
    assert isinstance(edge.provenance, ProvenanceEnvelope)
```

```python
def test_correction_has_provenance():
    corr = CorrectionRecord(
        target_tensor=uuid4(),
        original_claim="old",
        corrected_claim="new",
    )
    assert isinstance(corr.provenance, ProvenanceEnvelope)
```

```python
def test_dissent_has_provenance():
    d = DissentRecord(
        target_tensor=uuid4(),
        alternative_framework="alt",
        reasoning="because",
    )
    assert isinstance(d.provenance, ProvenanceEnvelope)
```

```python
def test_negation_has_provenance():
    n = NegationRecord(
        tensor_a=uuid4(),
        tensor_b=uuid4(),
        reasoning="different lineages",
    )
    assert isinstance(n.provenance, ProvenanceEnvelope)
```

```python
def test_bootstrap_has_provenance():
    b = BootstrapRecord(
        instance_id="test",
        context_budget=0.8,
    )
    assert isinstance(b.provenance, ProvenanceEnvelope)
```

```python
def test_evolution_has_provenance():
    e = SchemaEvolutionRecord(
        from_version="v1",
        to_version="v2",
    )
    assert isinstance(e.provenance, ProvenanceEnvelope)
```

```python
def test_entity_has_provenance():
    e = EntityResolution(
        entity_uuid=uuid4(),
        identity_type="ai",
    )
    assert isinstance(e.provenance, ProvenanceEnvelope)
```

```python
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
The claim by `qwen/qwen3-235b-a22b-2507` accurately describes the content of `tests/red_bar/test_provenance.py`. The file contains multiple test functions that verify the presence of `ProvenanceEnvelope` in various record types, exactly as quoted in the claim. Each test function matches the structure and logic described in the claim, confirming that the file's content aligns with the claim.

### Declared Losses
None. The claim is entirely verifiable based on the static content of the file.