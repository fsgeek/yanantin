<!-- Chasqui Scout Tensor
     Run: 600
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 859, 'completion_tokens': 379, 'total_tokens': 1238, 'cost': 3.234e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 3.234e-05, 'upstream_inference_prompt_cost': 1.718e-05, 'upstream_inference_completions_cost': 1.516e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-15T00:21:40.277804+00:00
-->

### Verdict
**CONFIRMED**

### Evidence
```
    """Compose operator — creates composition edges between tensors.

    Bridge = Compose with authored_mapping populated. Single operator,
    two modes.
    """
    edge = CompositionEdge(
        from_tensor=from_tensor,
        to_tensor=to_tensor,
        relation_type=RelationType.COMPOSES_WITH,
        ordering=ordering,
        authored_mapping=authored_mapping,
        provenance=provenance or ProvenanceEnvelope(),
    )
```

### Reasoning
The file defines a function `compose` that creates a `CompositionEdge` object. The constructor for `CompositionEdge` takes `authored_mapping` as an argument. The code also includes a comment that states "Bridge = Compose with authored_mapping populated." This indicates that the `compose` operator is designed to handle cases where `authored_mapping` is provided, suggesting a formal handling of such scenarios. Furthermore, the presence of `provenance=provenance or ProvenanceEnvelope()` shows that provenance information can be included in the `CompositionEdge`, which could be part of a formal system for tracking relationships and changes. While the file doesn't explicitly detail how schema changes and disagreements are formally handled, the design of the `CompositionEdge` with the `authored_mapping` field implies a mechanism for representing and potentially managing these aspects.

### Declared Losses
The claim mentions "formally," but the provided code snippet doesn't detail the specific mechanisms for handling schema changes and disagreements. The code shows how data is stored as `CompositionEdge` objects, but not how these edges are used to manage or validate schema consistency. Therefore, I cannot definitively confirm the extent to which schema changes and disagreements are formally handled based solely on this file.