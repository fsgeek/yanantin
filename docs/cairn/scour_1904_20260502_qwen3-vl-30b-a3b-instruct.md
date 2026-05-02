<!-- Chasqui Scour Tensor
     Run: 1904
     Model: qwen/qwen3-vl-30b-a3b-instruct (Qwen: Qwen3 VL 30B A3B Instruct)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$1.3e-07/M, completion=$5.2e-07/M
     Usage: {'prompt_tokens': 8551, 'completion_tokens': 2775, 'total_tokens': 11326, 'cost': 0.0036527, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0036527, 'upstream_inference_prompt_cost': 0.0017102, 'upstream_inference_completions_cost': 0.0019425}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-02T00:49:04.733040+00:00
     GenerationID: gen-1777682891-WYlAAskPyTDZrvUZabCh
-->

# Scour Report — `apacheta/`

### Preamble  
I was directed to examine `src/yanantin/apacheta`, a core module of the Yanantin project that implements a tensor-based epistemic observability system. My attention was drawn first to the **epistemic metadata model** (`models/epistemics.py`) and the **abstract interface** (`interface/abstract.py`), as they define the foundational semantics of truth, indeterminacy, and falsity in the system. These files are not just technical artifacts — they are philosophical commitments encoded in code. The way `EpistemicMetadata` allows values outside [0, 1] and treats T/I/F as unconstrained floats signals a deliberate departure from classical logic, aiming for a neutrosophic framework. This immediately suggests that the system is designed not only to store information but to *observe* and *track* the epistemic status of claims — a key feature of the project’s broader goal of complementary human-AI cognition.

---

### Strands

#### 1. **Neutrosophic Epistemic Logic as Core Design Principle**
- **What I saw**: In `models/epistemics.py`, `EpistemicMetadata` defines `truth`, `indeterminacy`, and `falsity` as unconstrained floats, explicitly rejecting normalization to sum to 1.0. The docstring calls this "neutrosophic logic" and notes that values outside [0, 1] may represent uncalibrated raw scores.
- **What it made me think**: This is a bold architectural choice. Most systems using three-valued logic (e.g., Belief-Desire-Intention models) either normalize or treat the values as probabilities. Here, the lack of constraint suggests that the system expects external calibration — perhaps via downstream operators like `evolve.py` or `correct.py`. It also implies that the *meaning* of the values is not tied to probability but to *degree of epistemic confidence* in a non-probabilistic sense.
- **Connection to the project**: This aligns with the "complementary duality" between human and AI — humans may hold beliefs with high indeterminacy (e.g., "I don’t know if this is true, but it feels plausible"), while AI might output calibrated scores. The system allows both to coexist without forcing a single interpretation.
- **Assumptions**: It assumes that users (or agents) will interpret these floats as relative, not absolute, measures. It also assumes that normalization is a post-processing step, not a requirement of the model itself.
- **What would break if this changed**: If the values were constrained to sum to 1.0, the system would lose its ability to represent *uncalibrated* or *unnormalized* claims — a feature that may be essential for early-stage reasoning or speculative thinking.

#### 2. **Immutable, Versioned Configuration via `config.py`**
- **What I saw**: `config.py` defines `ConfigTensor`, which is a `ApachetaBaseModel` and thus immutable. It includes a `previous_config_id` field and a `reasoning` field, and the `store_config` function converts it into a `TensorRecord` with lineage tags. The `get_current_config` function queries for the latest config via `query_reading_order`, which returns tensors in chronological order.
- **What it made me think**: This is a sophisticated implementation of **configuration-as-tensor**, where changes to configuration are treated as first-class, traceable events. The use of `provenance` and `lineage_tags` ensures that configuration changes are auditable and can be linked back to their rationale. This is a powerful pattern for systems where configuration drift is a concern — such as in AI agents that need to reason about their own settings.
- **Connection to the project**: This ties into the broader theme of **epistemic observability**. Not only do we track the state of knowledge, but we also track how the *system itself* has evolved. The configuration becomes part of the narrative.
- **Assumptions**: It assumes that configuration changes are rare and intentional, and that the cost of storing them is acceptable. It also assumes that the `query_reading_order` function is reliable and returns tensors in correct temporal order.
- **What would break if this changed**: If `ConfigTensor` were mutable, the system would lose its ability to audit configuration history. If lineage tags were not used, it would be harder to distinguish configuration tensors from other types.

#### 3. **The Abstract Interface as a Contract for Storage**
- **What I saw**: `interface/abstract.py` defines `ApachetaInterface`, an abstract base class with methods for storing and querying tensors, composition edges, corrections, and more. It includes a `check_access` hook and enforces immutability. The interface is designed to be backend-agnostic, with all backends implementing this interface.
- **What it made me think**: This is a **clear separation of concerns**. The interface defines *what* can be done, while the backends define *how*. This is crucial for scalability and maintainability. The fact that `store_record` is generic (accepting any `ApachetaBaseModel`) suggests that the system is designed to be extensible — new record types can be added without breaking the interface.
- **Connection to the project**: This abstraction is essential for the project’s goal of **composable tensor infrastructure**. It allows different storage backends (e.g., ArangoDB, DuckDB, in-memory) to be swapped in and out without affecting the operators or clients.
- **Assumptions**: It assumes that all storage backends will be thread-safe and support the required operations. It also assumes that the `check_access` hook will be implemented correctly in all backends.
- **What would break if this changed**: If the interface were to change (e.g., adding a `delete` method), all backends would need to be updated, and the system would lose its immutability guarantee.

#### 4. **Bootstrap as a Mechanism for Context Budgeting**
- **What I saw**: `operators/bootstrap.py` defines a `bootstrap` function that selects tensors for a new instance’s context budget. It takes a `context_budget` parameter and returns a `BootstrapRecord` and a list of selected `TensorRecord`s. The `BootstrapRecord` includes information about what was omitted and the provenance.
- **What it made me think**: This is a **critical control point** for managing computational resources. The context budget is likely a proxy for token limits or processing time. The fact that the `what_was_omitted` field is included suggests that the system is designed to be transparent about its limitations — a form of **epistemic honesty**.
- **Connection to the project**: This ties into the complementary duality — the AI must reason about its own constraints and communicate them to the human. The `BootstrapRecord` becomes a record of the system’s decision-making process.
- **Assumptions**: It assumes that the `context_budget` is a meaningful metric and that the `list_tensors` method returns tensors in a useful order (e.g., by relevance or recency).
- **What would break if this changed**: If the `context_budget` were ignored or if the selection logic were changed without updating the `what_was_omitted` field, the system would lose its ability to track omissions.

#### 5. **Composition as a Bridge Between Tensors**
- **What I saw**: `operators/compose.py` defines a `compose` function that creates a `CompositionEdge` between two tensors. The `authored_mapping` field allows for a human-authored description of the relationship between the tensors.
- **What it made me think**: This is a **key mechanism for knowledge integration**. The `CompositionEdge` is not just a link — it’s a **bridge** that can carry a narrative about how two pieces of knowledge relate. The `authored_mapping` field is particularly interesting — it suggests that the system values human interpretation of relationships.
- **Connection to the project**: This supports the complementary duality — humans can author mappings between AI-generated tensors, creating a feedback loop where human insight shapes AI reasoning.
- **Assumptions**: It assumes that the `authored_mapping` is a string that can be parsed or interpreted by humans. It also assumes that the `CompositionEdge` is stored in a way that preserves the directionality of the relationship.
- **What would break if this changed**: If the `authored_mapping` were removed, the system would lose its ability to capture human-authored relationships. If the `relation_type` were not properly enforced, the graph could become inconsistent.

---

### Declared Losses

- **What I chose not to examine**: The `backends/` directory. I did not examine `arango.py`, `duckdb.py`, or `memory.py` because they are not defined in the target files. I also did not examine `ingest/markdown_parser.py` or `ingest/tensor_ballot.py` because they are not directly related to the core epistemic infrastructure.
- **Why**: The assignment was focused on introspection — examining the target as part of the project’s own codebase. The `backends` are likely implementation details, and the ingest modules are more peripheral to the core epistemic observability system. I also ran out of attention — the `interface/abstract.py` and `models/epistemics.py` were dense enough to require deep focus.
- **What I ran out of attention for**: The `clients/gateway.py` and `clients/openrouter.py` were complex, but I prioritized the core infrastructure. I also did not examine the `renderer/markdown.py` module, which is likely responsible for rendering tensors as Markdown, but it’s not central to the epistemic logic.

---

### Open Questions

1. **How is the `context_budget` in `bootstrap.py` calculated?**  
   The `context_budget` is passed as a parameter to `bootstrap`, but it’s not clear how it’s derived. Is it a fixed value, or does it depend on the instance’s configuration? How is it related to token limits or processing time?

2. **What is the role of `lineage_tags` in `TensorRecord`?**  
   The `lineage_tags` field is used to tag tensors (e.g., `("config", "chasqui.pulse")`), but it’s not clear how these tags are used in queries. Are they only used for filtering, or do they have semantic meaning?

3. **How are `KeyClaim` and `StrandRecord` related to `EpistemicMetadata`?**  
   `KeyClaim` has an `epistemic` field, and `StrandRecord` has an `epistemic` field, but `TensorRecord` also has an `epistemic` field. Is the `epistemic` field at the tensor level a summary of the strand-level fields? How is it computed?

4. **What is the purpose of `preservation_target` in `TensorRecord`?**  
   The `preservation_target` field is present but not used in any of the code I examined. What does it represent? Is it used for archival or retention purposes?

5. **How is `query_reading_order` implemented in the backends?**  
   The `query_reading_order` method is defined in `interface/abstract.py`, but the implementation is not provided. How is the reading order determined? Is it based on timestamp, provenance, or some other criterion?

---

### Closing

This part of the codebase is **thoughtful, intentional, and deeply rooted in epistemic philosophy**. The use of neutrosophic logic, immutable configuration, and a well-defined interface demonstrates a commitment to **epistemic observability** — not just storing data, but tracking the *status* of knowledge.

The system is **designed to be extensible and modular**, with clear separation between the interface, models, and operators. The use of `ApachetaBaseModel` and `ProvenanceEnvelope` ensures that all records are traceable and auditable.

However, the system is also **complex**, with many interdependent components. The `interface/abstract.py` alone defines over 30 methods, and the `config.py` module introduces a new concept (configuration as tensor) that must be understood in the context of the broader system.

If I were to modify this codebase, I would:
- **Be cautious about changing the epistemic model** — the `EpistemicMetadata` class is central to the system’s philosophy.
- **Ensure that all backends implement the interface correctly** — the system’s reliability depends on this.
- **Document the meaning of `lineage_tags` and `composition_equation`** — these fields are underused and could benefit from clearer semantics.
- **Consider adding a `query_by_tag` method** to the interface — this would make it easier to filter tensors by lineage tags.

Overall, this is a **powerful and sophisticated system** that reflects a deep understanding of the challenges of human-AI collaboration. It is not just a database — it is a **knowledge observatory**.