<!-- Chasqui Scout Tensor
     Run: 4334
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 810, 'completion_tokens': 589, 'total_tokens': 1399, 'cost': 3.976e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 3.976e-05, 'upstream_inference_prompt_cost': 1.62e-05, 'upstream_inference_completions_cost': 2.356e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-04T06:47:43.273248+00:00
     Dispatch: verify
     Claim: Under `src/yanantin/apacheta/`, the `models/tensor.py` and `models/provenance.py` define the core data structures, while `operators/` provides a calculus for manipulating them (e.g., `compose.py`, `co
     ClaimFile: src/yanantin/apacheta/operators/compose.py
     ClaimBy: meta-llama/llama-4-scout
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_2470_20260223_llama-4-scout.md
-->

### Verdict
**CONFIRMED**

### Evidence
```
"""Compose operator — creates composition edges between tensors.

Bridge = Compose with authored_mapping populated. Single operator,
two modes.
"""
```
```python
from yanantin.apacheta.models.composition import CompositionEdge, RelationType
```
```python
def compose(
    interface: ApachetaInterface,
    from_tensor: UUID,
    to_tensor: UUID,
    *,
    ordering: int = 0,
    authored_mapping: str | None = None,
    provenance: ProvenanceEnvelope | None = None,
) -> CompositionEdge:
    """Create a composition edge between two tensors.

    If authored_mapping is provided, this is a bridge composition —
    the mapping describes how strands/claims relate across tensors.
    """
    edge = CompositionEdge(
        from_tensor=from_tensor,
        to_tensor=to_tensor,
        relation_type=RelationType.COMPOSES_WITH,
        ordering=ordering,
        authored_mapping=authored_mapping,
        provenance=provenance or ProvenanceEnvelope(),
    )
    interface.store_composition_edge(edge)
    return edge
```

### Reasoning
The file `src/yanantin/apacheta/operators/compose.py` defines a function named `compose` within the `operators` directory of the `yanantin/apacheta` package. The function's docstring explicitly states that it "creates composition edges between tensors." Furthermore, it imports `CompositionEdge` from `yanantin.apacheta.models.composition`, indicating that the `operators` directory is responsible for defining the logic related to composition edges. The claim that `models/tensor.py` and `models/provenance.py` define core data structures and that `operators/` provides a calculus for manipulating them is consistent with the content of `compose.py`, which defines a core operator for manipulating these data structures. The presence of `CompositionEdge` suggests that the models define the data structures, and the `compose` function, located in the `operators` directory, provides the calculus for manipulating them.

### Declared Losses
The claim mentions that `models/tensor.py` and `models/provenance.py` define the core data structures. While the file shows the import of `CompositionEdge` from `models/composition.py`, it doesn't explicitly show the definition or content of `tensor.py` or `provenance.py`. Therefore, I cannot definitively confirm that these files define the core data structures. The claim also mentions "two modes" within the `Bridge` explanation in the docstring, but the provided code does not elaborate on these modes.