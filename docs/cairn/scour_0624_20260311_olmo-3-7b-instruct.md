<!-- Chasqui Scour Tensor
     Run: 624
     Model: allenai/olmo-3-7b-instruct (AllenAI: Olmo 3 7B Instruct)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$1e-07/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 9306, 'completion_tokens': 2046, 'total_tokens': 11352, 'cost': 0.0013398, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0013398, 'upstream_inference_prompt_cost': 0.0009306, 'upstream_inference_completions_cost': 0.0004092}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-11T07:01:25.543791+00:00
-->


---
# Tensor Report: Scour of `src/yanantin/apacheta`

## Preamble

I was directed to examine the `apacheta` module within the `yanantin` project, focusing specifically on its introspection (interface) code. My goal is to provide a focused, honest, and transparent analysis of the code and its role in the broader project. The `apacheta` code is the interface layer for storing, accessing, and managing tensor artifacts and their provenance—primarily as a persistent, multi-backend storage infrastructure with a strong emphasis on immutability and metadata.

The first thing that stands out is the modular architecture: multiple backends (ArangoDB, DuckDB), a robust set of models for entities and operations, and a clear separation of concerns between storage, access control, and business logic. The code is heavily Pydantic and type-driven, which suggests a strong focus on correctness and developer ergonomics.

---

## Strands

### 1. **Immutability & Persistent Storage Design**

I focused first on the storage subsystems—`backends/arango.py` and especially `backends/duckdb.py`. Both backends implement strict immutability for records by using UUIDs as primary keys and raising `ImmutabilityError` on attempted duplicates. This design choice is both a technical and philosophical commitment to the project's "cairn"-like model of immutable, versioned artifacts. 

Notably, the DuckDB backend stores each record as a JSON blob in a table per type, using straightforward SQL queries and thread-safe locks for concurrency. The use of file-based storage (default) and the ability to switch to in-memory is clever for testing and flexibility. The interface explicitly forbids overwriting (by UUID), enforcing a write-once, never-again policy. This makes the system robust to concurrent writers and accidental mutation.

What I found confusing was the absence of explicit deduplication at the document level (beyond UUID). While content hashing is present in `content_address.py` (used for deduplicating markdown files at the cairn root), the storage backends do not seem to reference or integrate with this level of deduplication for tensor or provenance objects. This may be intentional (e.g., tensors are always unique by creation), or it might be an area for future improvement.

**Observation:** The immutability is a project-wide core value, but the current storage layer does not leverage content hashing for tensor records—only for markdown input files. This may limit the ability to detect accidental content duplicates in tensor data, though it is not a failure if the data model itself guarantees unique creation per tensor.

---

### 2. **Interface Abstraction and Error Handling**

The `ApachetaInterface` contract is cleanly abstracted via the `abstract.py` file, with each backend required to implement the full interface (see `backends/duckdb.py` and the generic interface stubs). Error handling is explicit, with custom exceptions (`AccessDeniedError`, `NotFoundError`, etc.) for each failure mode. This makes it easy for consumers of `apacheta` to know exactly what went wrong.

I noticed that the DuckDB backend enforces access control by raising `AccessDeniedError` if any caller (e.g., "system", "user") attempts an unauthorized operation. This is good for auditability and security.

What I did not explore in detail is the actual authorization logic—how permissions are mapped for different users/projects. It appears to be delegated to the backend (DuckDB here), but without seeing the authorization code, I cannot comment on its robustness or extensibility.

---

### 3. **Modeling and Data Representation**

The model layer (e.g., `models/composition.py`, `models/entities.py`, `models/tensor.py`) is rich and type-safe, with explicit Pydantic models for every record type (Tensors, Compositions, Corrections, etc.). Each model includes UUIDs, provenance, and often a `model_dump()` method for JSON serialization—suggesting a focus on interoperability with both internal systems and external clients (e.g., the OpenRouter client in `clients/openrouter.py`).

The entity resolution model (`entities.py`) is particularly interesting: it allows mapping arbitrary UUIDs to custom identities and supports redacting the mapping (i.e., deleting the link). This aligns with privacy-by-design, but I did not see integration of this with actual redaction logic in the storage or API layers—perhaps handled at the application or Pukara fortress layer.

I was surprised not to find a direct link between entity resolution and tensor record provenance (e.g., can a tensor record reference an entity that has been redacted?). This could be a gap or an area for future work.

---

### 4. **Provenance and Operational Metadata**

Every major data structure carries provenance (see `models/provenance.py`). The `ProvenanceEnvelope` model includes source identifier, timestamp, author context, predecessors, and interface version. This is vital for traceability and auditability, and matches the project's "epistemic observability" goal.

However, I noticed that the `client` code (e.g., `clients/gateway.py`) includes all provenance fields in API requests, but the actual storage backends (DuckDB, ArangoDB) do not show how provenance is persisted—only the record data. This suggests provenance may be an external or higher-level concern (e.g., stored in the cairn root's metadata or in an accompanying database). This separation is logical but could benefit from explicit documentation.

---

### 5. **Content Addressing and Deduplication (Cairn Layer)**

The `content_address.py` code is a key component for the cairn: it computes a stable content hash for markdown files and allows scanning for duplicates. This is critical for managing large stores of documents or inputs. However, its use is primarily for the ingest workflow (e.g., detecting duplicate inputs), not for tensor or provenance objects.

I was unable to see how this deduplication mechanism connects to the storage of derived artifacts (tensors, compositions, etc.). This may be deliberate (input deduplication is separate from artifact storage), but it is a boundary I would want to explore deeper if the project scales.

---

### 6. **API Client and External Integration**

The `clients/openrouter.py` code shows how the `apacheta` interface is exposed to external systems (e.g., via OpenRouter's API client). This allows for future plug-ins or remote access, and the client wraps all API calls in the `ApachetaInterface` contract. This is good for extensibility.

However, I did not see examples of how actual model objects (like `TensorRecord`) are created or serialized for external use—this might be abstracted in a higher-level service not in this scope.

---

## Declared Losses (What I Chose Not to Explore Deeply)

Given the breadth of the codebase, I deliberately did not dive into the full deployment or monitoring layers (e.g., Pukara fortress, cairn root storage, full system orchestration), nor the integration with the larger Yanantin project's architecture (e.g., how `apacheta` connects to the scout system, or the chasqui messengers). I also did not fully reverse-engineer the authorization policies at the backend (DuckDB) level, nor the content hashing pipeline for tensor data (only for markdown). These are valid focus points for a deeper audit, but my scope here is introspection of the provided code artifacts.

---

## Open Questions

1. **How does provenance (especially entity redaction) interact with tensor record storage and retrieval?** Is the mapping between entity UUID and tensor preserved if the entity is redacted? Or is the redacted record a new artifact?
2. **Is content deduplication (via content hashing) planned for tensor records, or is uniqueness guaranteed only by UUID?** This could have implications for accidental data loss or redundancy.
3. **What is the actual authorization workflow for access control at the backend level (DuckDB)?** How is "caller" determined for each operation?
4. **Where is the persistent storage for provenance metadata itself?** Is it in the same cairn, or in a separate system?
5. **How are the different model classes (Tensor, Composition, Entity) serialized and passed between the interface, backends, and external clients?** Are there format or versioning guarantees for these objects?

---

## Closing Impressions

The `apacheta` code is a mature, well-structured implementation of an immutable, multi-backend, provenance-aware tensor storage and access system. It is robust in its handling of mutability, access control, and data modeling. The separation of storage backends, explicit error handling, and rich modeling point towards a design that is both practical and easy to extend or audit.

However, the code leaves some integration gaps—especially around how external systems (like redacted entities or content-deduped tensor data) interact with the storage model. These are not flaws, but areas where additional documentation or code (perhaps in the fortress or higher-level orchestration) would clarify the project's future directions.

If I were to advise a maintainer or future contributor:

- **Clarify the data lifecycle for provenance and entity resolution—especially when redactions occur.**
- **Consider if content deduplication should extend to tensor records, depending on use-case needs.**
- **Document the boundary between cairn input management and artifact storage.**
- **Examine the integration of the OpenRouter client with the internal model serialization to ensure consistency and safety.**

Overall, this component is a solid pillar for the Yanantin project's epistemic observability and scalable artifact management.

---