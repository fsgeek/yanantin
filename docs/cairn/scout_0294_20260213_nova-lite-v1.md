<!-- Chasqui Scout Tensor
     Run: 294
     Model: amazon/nova-lite-v1 (Amazon: Nova Lite 1.0)
     Cost: prompt=$6e-08/M, completion=$2.4e-07/M
     Usage: {'prompt_tokens': 1429, 'completion_tokens': 374, 'total_tokens': 1803, 'cost': 0.0001755, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0001755, 'upstream_inference_prompt_cost': 8.574e-05, 'upstream_inference_completions_cost': 8.976e-05}, 'completion_tokens_details': {'reasoning_tokens': 0}}
     Timestamp: 2026-02-13T14:45:16.886635+00:00
-->

### Verdict
**CONFIRMED**

### Evidence

```python
# Line 13
assert isinstance(tensor.provenance, ProvenanceEnvelope)

# Line 21
assert isinstance(edge.provenance, ProvenanceEnvelope)

# Line 29
assert isinstance(corr.provenance, ProvenanceEnvelope)

# Line 37
assert isinstance(d.provenance, ProvenanceEnvelope)

# Line 43
assert isinstance(n.provenance, ProvenanceEnvelope)

# Line 51
assert isinstance(b.provenance, ProvenanceEnvelope)

# Line 57
assert isinstance(e.provenance, ProvenanceEnvelope)

# Line 65
assert isinstance(e.provenance, ProvenanceEnvelope)
```

Additionally, for `test_stored_records_retain_provenance`:

```python
# Lines 76-77
assert retrieved.provenance.author_model_family == "claude"
assert retrieved.provenance.author_instance_id == "test-session"
```

### Reasoning

The provided claim specifies that the file `tests/red_bar/test_provenance.py` contains multiple test cases that check for the presence of provenance in various record types. The evidence within the file confirms that each mentioned test case includes an assertion that checks the instance of `ProvenanceEnvelope` for the respective record, aligning with the claims about the specific lines. The test case `test_stored_records_retain_provenance` also includes assertions that verify the provenance's `author_model_family` and `author_instance_id`, as claimed.

### Declared Losses

N/A - All aspects of the claim have been verified against the provided file content.