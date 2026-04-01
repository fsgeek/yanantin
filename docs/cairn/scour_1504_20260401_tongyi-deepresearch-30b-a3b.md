<!-- Chasqui Scour Tensor
     Run: 1504
     Model: alibaba/tongyi-deepresearch-30b-a3b (Tongyi DeepResearch 30B A3B)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$9e-08/M, completion=$4.5e-07/M
     Usage: {'prompt_tokens': 10205, 'completion_tokens': 4000, 'total_tokens': 14205, 'cost': 0.00271845, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 6, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00271845, 'upstream_inference_prompt_cost': 0.00091845, 'upstream_inference_completions_cost': 0.0018}, 'completion_tokens_details': {'reasoning_tokens': 4417, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-01T16:54:47.361727+00:00
     GenerationID: gen-1775062442-B70o0yyHgUqn4o9KAUkl
-->

# Scour Report: Yanantin/Apacheta

### Preamble

I am examining `src/yanantin/apacheta`, a core component of the Yanantin project that implements a tensor database system for epistemic observability. The name "apacheta" (Quechua for "small offering") reflects its role as a place for offering and combining knowledge components. This is a sophisticated architecture focused on managing knowledge with explicit provenance and quality metrics.

### Strands

1. **Dual Architecture with Interface-Implementation Separation**

The codebase exhibits a clear separation between abstract interfaces and concrete implementations. The `ApachetaInterface` in `interface/abstract.py` defines the API contract, while specific backends like `DuckDBBackend` provide database storage. This adheres to the Dependency Inversion Principle.

2. **Epistemic Metadata and Provenance Tracking**

A major theme is the explicit tracking of epistemic metadata - truth values, uncertainty, and confidence metrics. Provenance metadata captures the origin and history of each tensor through `ProvenanceEnvelope` (in `models/provenance.py`) and `EpistemicMetadata` (in `models/epistemics.py`).

3. **Compositional Knowledge Graph Relationships**

Extensive support for tracking relationships between knowledge components through `CompositionEdge` with different relation types (`COMPOSES_WITH`, `CORRECTS`, etc.) in `models/composition.py`. This enables building complex knowledge graphs with explicit relationship semantics.

4. **Immutability and Versioning**

Tensors are treated as immutable objects, with `ImmutabilityError` raised when attempting to overwrite. Schema evolution is tracked through `SchemaEvolutionRecord` (in `models/composition.py`), ensuring controlled evolution of the knowledge base.

5. **Bootstrap Mechanism for Knowledge Initialization**

The `bootstrap` operator in `operators/bootstrap.py` provides controlled initialization of AI instances with specific knowledge bases, tracking what was included and omitted.

6. **Access Control Layer**

While the actual implementation is deferred (`Pukara`), the system defines access control through `check_access` in the interface and implements it as always returning `True` in the gateway client.

7. **Markdown as Knowledge Entry Format**

Knowledge entry primarily uses markdown documents parsed by `markdown_parser.py`, with flexible handling of different formatting conventions.

8. **Storage Obfuscation Protocol