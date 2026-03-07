<!-- Chasqui Scour Tensor
     Run: 421
     Model: prime-intellect/intellect-3 (Prime Intellect: INTELLECT-3)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$2e-07/M, completion=$1.1e-06/M
     Usage: {'prompt_tokens': 8081, 'completion_tokens': 2122, 'total_tokens': 10203, 'cost': 0.0039504, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0039504, 'upstream_inference_prompt_cost': 0.0016162, 'upstream_inference_completions_cost': 0.0023342}, 'completion_tokens_details': {'reasoning_tokens': 1360, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-07T00:43:21.910767+00:00
-->

### Preamble
I was directed to examine `src/yanantin/apacheta`, the tensor database core of the Yanantin project. My attention was immediately drawn to the tension between **external API integration** (OpenRouter client) and **internal state management** (TensorRecords, composition operators). The system appears designed to capture every API interaction as a first-class tensor record while maintaining strict immutability guarantees at the storage layer.

---

### Strands

#### 1. **API Provenance Capture**  
In `clients/openrouter.py`, every API call returns a `TensorRecord` with full metadata (model, cost, experiment context). This creates a **provenance chain** from external LLM interactions to internal state. The design assumes:  
- The OpenRouter API is stable (line 32: `BASE_URL = "https://openrouter.ai/api/v1"`)  
- API responses contain structured `usage` data (line 162: `usage=raw.get("usage", {})`)  
**What breaks**: If OpenRouter changes their API or pricing model, the cost-tracking logic would need updates. The client also hardcodes `OPENROUTER_API_KEY` (line 38), which may conflict in multi-tenant deployments.  

#### 2. **Storage Immutability**  
`backends/arango.py` enforces immutability via `ImmutabilityError` (line 263) and locks with `threading.RLock`. This ensures a reliable version history but assumes:  
- UUID collisions are impossible (uses `uuid4`)  
- ArangoDB transactions are ACID-compliant (line 382: `self._db.has(key)`)  
**What breaks**: If UUID collisions occur (statistically unlikely but possible) or ArangoDB loses transaction guarantees, data integrity could degrade.  

#### 3. **Epistemic Metadata Propagation**  
`models/epistemics.py` defines neutrosophic logic (T/I/F values) for claims. The `EpistemicMetadata` class propagates uncertainty through the system. However:  
- Values are "unconstrained" (line 38: `truth: float = 0.0`), allowing negative values or values >1.0  
- The `functional_spec` field is unused in provided code  
**Missing**: Calibration logic to normalize raw scores into [0,1] ranges.  

#### 4. **Operator Composition**  
Operators like `dissent.py` and `negate.py` create **dual records**: both a semantic record (e.g., `DissentRecord`) and a graph edge (`CompositionEdge`). This creates redundancy but enables:  
- Graph traversal for "disagreement networks"  
- Programmatic filtering by relation type  
**Assumption**: Consumers will query edges and records separately (e.g., `store_dissent()` vs `store_composition_edge()`).  

#### 5. **Search Infrastructure**  
`rummage.py` provides a grep-like tool for tensors. Its parser:  
- Classifies sections via regex (`_classify_section()`)  
- Skips `MEMORY.md` and hidden files (line 94)  
**Potential gap**: No stemming/lemmatization for search queries (e.g., "memory" vs "memories").  

---

### Declared Losses  
I chose **not** to examine:  
- `ingest/markdown_parser.py` and `tensor_ballot.py`: Critical for input processing but not provided.  
- `interface/abstract.py`: Defines the backend interface contract but requires inference from implementations.  
- `backends/duckdb.py` and `memory.py`: Alternative storage engines not included in target scope.  

---

### Open Questions  
1. How are `epistemic` values from `OpenRouterResponse` (clients/openrouter.py) mapped to TensorRecords? The client stores raw usage but doesn't link to tensor creation.  
2. What triggers schema evolution? The `evolve.py` operator exists, but no migration logic is visible in provided models.  
3. How do backends handle concurrency? ArangoDB uses `RLock`, but other backends might have different guarantees.  

---

### Closing  
The apacheta module is a **well-architected core** that prioritizes immutability, provenance, and epistemic rigor. Its design explicitly separates concerns:  
- **API layer** (`clients`) for external interactions  
- **Data layer** (`models`, `backends`) for storage and retrieval  
- **Operators** for safe state mutations  

**Caution for modifiers**:  
- Never bypass the operators (e.g., directly calling `backend.store_tensor()`)—this breaks provenance tracking.  
- UUIDs are sacred; never regenerate them.  
- If adding new relation types in `CompositionEdge`, update both `RelationType` enum and operator logic.  

The codebase feels like a **fortress**: built for resilience, but complex to extend. Prioritize backward compatibility—schema changes require `evolve()` calls, not direct model alterations.