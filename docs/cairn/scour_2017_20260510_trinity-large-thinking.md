<!-- Chasqui Scour Tensor
     Run: 2017
     Model: arcee-ai/trinity-large-thinking (Arcee AI: Trinity Large Thinking)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$2.2e-07/M, completion=$8.5e-07/M
     Usage: {'prompt_tokens': 10092, 'completion_tokens': 4000, 'total_tokens': 14092, 'cost': 0.005723, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.005723, 'upstream_inference_prompt_cost': 0.002523, 'upstream_inference_completions_cost': 0.0032}, 'completion_tokens_details': {'reasoning_tokens': 2294, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-10T16:00:22.873971+00:00
     GenerationID: gen-1778428801-wn51YKOuiNmWfCr8G0AZ
-->


# Scour Report — Introspection

## Preamble

I've been directed to examine `src/yanantin/apacheta`, the foundational core of the Yanantin project. This is the project's own codebase — its tensor infrastructure, epistemic models, and interface contracts. What drew my attention first is the `interface/abstract.py` file, which defines the `ApacheraInterface` — the central contract that everything else implements or depends upon. This is the architectural keystone.

## Strands

### 1. **Interface as Contract** (`interface/abstract.py`)
The `ApachetaInterface` defines 30+ methods across version, access control, generic operations, write operations, and read operations. It's a comprehensive CRUD-like interface for tensor-based epistemic records. The design separates concerns: backends implement storage, clients implement transport, operators implement business logic. The `check_access` hook is intentionally permissive (returns `True` by default), delegating actual access control to implementations like the gateway. This creates a clean separation but assumes implementations will enforce security.

### 2. **Immutable Data Model** (`models/base.py`, `models/tensor.py`, etc.)
All models inherit from `ApachetaBaseModel` with `frozen=True` and `extra="allow"`. This enforces immutability — once created, records cannot be modified, only new ones composed. The `model_copy(deep=True)` pattern in `backends/memory.py` shows careful handling of nested models (like `ProvenanceEnvelope`) to avoid losing type information during copying. This immutability is central to the project's philosophy of "compose, don't overwrite."

### 3. **Neutrosophic Epistemics** (`models/epistemics.py`)
The `EpistemicMetadata` class implements neutrosophic logic with independent `truth`, `indeterminacy`, and `falsity` floats (not constrained to sum to 1). This is a key theoretical choice, allowing things to be simultaneously partly true, partly indeterminate, and partly false. The `DisagreementType` enum (`EMPIRICAL` vs `DEFINITIONAL`) reflects an archivist's observation about resolvable vs. unresolvable disagreements. This strand reveals the project's epistemic ambition.

### 4. **Composition Over CRUD** (`operators/`, `models/composition.py`)
The operators (`bootstrap`, `dissent`, `project`, etc.) don't just manipulate data — they create new records that reference old ones via UUIDs. The `CompositionEdge` model explicitly tracks relationships (`DISSENTS_FROM`, `CORRECTS`, etc.). This creates a directed acyclic graph of tensor evolution, where each new tensor is a composition that acknowledges its predecessors. The `bootstrap` operator even stores a record of its own selection process.

### 5. **Dual Implementation Paths** (`backends/`, `clients/`)
The codebase cleanly separates *storage* (backends: memory, ArangoDB, DuckDB) from *transport* (clients: gateway, OpenRouter). Both implement `ApachetaInterface`. This allows the same operator logic to run locally or remotely. The `InMemoryBackend` is a reference implementation that validates the interface contract. The `ApachetaGatewayClient` maps interface methods to HTTP endpoints, handling errors and JSON serialization.

### 6. **Human-Readable Rendering** (`renderer/markdown.py`)
The renderer converts structured `TensorRecord` data into markdown following T0-T8 conventions. It separates *schema* from *presentation* — the schema stores structured data, the renderer makes it human-readable. The `render_composition_view` preserves attribution by marking each tensor's contribution. This reflects the project's dual audience: machines (for composition) and humans (for reading).

### 7. **Configuration as Tensor** (`config.py`)
Configuration is stored as `ConfigTensor` — a tensor with lineage tags `("config", domain)`. Each setting becomes a `KeyClaim`. This treats configuration changes as first-class epistemic events, with reasoning and predecessor pointers. The `get_current_config` function uses `query_reading_order` to find the latest config, falling back to defaults when no database is available. This elegantly solves the bootstrap problem.

### 8. **Search and Discovery** (`rummage.py`)
`Rummage` searches across markdown documents (tensors, scours, scout reports) with awareness of structure (strands, losses, questions). It parses markdown into `Section` objects and can filter by section kind. This tool helps navigate the accumulating "cairn" of documents. The `KNOWN_SOURCES` dictionary hints at a distributed memory across multiple directories.

## Connections to the Rest of the Project

The `apacheta` module is the **núcleo** — everything else plugs into this interface. The `ingest` module (markdown_parser, tensor_ballot) likely creates tensors that get stored via this interface. The `renderer` consumes tensors from this interface. The `operators` are higher-order functions that use this interface. The `backends` and `clients` are interchangeable implementations. This modularity allows swapping local memory for remote gateway without changing operator logic.

## Assumptions and Validity

- **Immutability**: The system assumes records are never updated, only new ones created. This is enforced in backends but relies on caller discipline.
- **UUID as Identifier**: Every record has a UUID. This assumes UUID generation is collision-free and that UUIDs are the stable handle across composition.
- **Pydantic v2**: The models depend on Pydantic's v2 behavior (frozen models, `model_dump`/`model_validate`).
- **Neutrosophic Logic**: The epistemic model assumes users will provide T/I/F values in [0,1] (or raw scores). No validation enforces this — it's a convention.
- **Access Control Hook**: The `check_access` method is a no-op by default, assuming implementations will override it. The gateway client delegates entirely to the server.

## What Would Break If This Changed?

- Changing `ApachetaInterface` method signatures would break all implementations and callers.
- Altering `ApachetaBaseModel` (e.g., removing `frozen=True`) would break immutability guarantees and potentially cause subtle bugs in composition logic.
- Modifying the `EpistemicMetadata` structure (e.g., removing `indeterminacy`) would break the neutrosophic logic foundation.
- Changing the `CompositionEdge` relationship types would break the graph traversal and operator logic.
- The `ConfigTensor` format is tightly coupled to the `TensorRecord` structure — changing one would require changing the other.

## What Is Missing That Should Be Here?

- **Validation**: There's minimal validation of epistemic values (T/I/F ranges) or model consistency. This is likely by design (flexibility) but could lead to garbage-in, garbage-out.
- **Pagination/Streaming**: Methods like `list_tensors` return full lists. For large datasets, this could be problematic.
- **Transaction Support**: The interface doesn't define transactions. Composing multiple related records (e.g., a dissent with its edge) would need application-level handling.
- **Schema Evolution Guidance**: The `SchemaEvolutionRecord` exists but there's no helper to apply evolutions automatically.
- **Error Handling Granularity**: The `_handle_error` in the gateway client maps HTTP statuses to a few error types. Some nuances might be lost.

## Declared Losses

I chose not to examine:
- `ingest/markdown_parser.py` and `ingest/tensor_ballot.py` in depth — they're likely parsers/builders but not core to the interface contract.
- `backends/arango.py` and `backends/duckdb.py` — they follow the same pattern as `memory.py` but with database specifics.
- `clients/openrouter.py` — it's an HTTP client but for a different API.
- `content_address.py` and `storage_obfuscator.py` — utility modules that seem peripheral to the core data model.
- The full `rummage.py` implementation (beyond the first 200 lines) — it's a search tool, not a core interface.

I ran out of attention because the core is large and well-defined. The missing parts are important for production but don't change the foundational design.

## Open Questions

1. **How does `markdown_parser.py` handle the T0-T8 format?** Does it produce valid `TensorRecord` instances?
2. **What's the exact role of `content_address.py`?** Does it generate content-based addresses for tensors to enable deduplication?
3. **How does `storage_obfuscator.py` work?** Does it anonymize data before storage?
4. **How are `SchemaEvolutionRecord`s applied?** Is there a migration tool, or is it manual?
5. **What's the relationship between