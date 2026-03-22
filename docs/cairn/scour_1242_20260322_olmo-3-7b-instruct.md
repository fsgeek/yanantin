<!-- Chasqui Scour Tensor
     Run: 1242
     Model: allenai/olmo-3-7b-instruct (AllenAI: Olmo 3 7B Instruct)
     Target: src/yanantin/activity
     Scope: introspection
     Cost: prompt=$1e-07/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 8075, 'completion_tokens': 1938, 'total_tokens': 10013, 'cost': 0.0011951, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0011951, 'upstream_inference_prompt_cost': 0.0008075, 'upstream_inference_completions_cost': 0.0003876}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-22T19:44:38.993224+00:00
     GenerationID: gen-1774208649-IC0SGHdeVjS6Nxre55l1
-->


Below is a tensor-style report on the `src/yanantin/activity` target, based on a thorough but honest inspection as a chasqui (focused, honest messenger). I have organized the findings in the requested tensor structure with clear strands, losses, and closing remarks.

---

## Tensor Report: Scour of `src/yanantin/activity`

---

### Preamble

I was assigned to closely examine the `activity` module within the Yanantin project. This is the code responsible for the **activity stream logic**, specifically the storage and management of facts and memory anchors, serving as a foundational piece for the project's epistemic observability through composable tensor infrastructure. My first attention was drawn to the layered abstraction over storage backends, the separation of fact and anchor handling, and the careful enforcement of immutability — all core to maintaining a trustworthy, audit-ready stream.

---

### Strand 1: Storage Abstraction and Backend Flexibility

**What I saw:**  
The `ActivityStreamStore` abstract base class and its concrete backends (ArangoDB, InMemory, DuckDB) show a clear pattern of *decoupled storage* — the business logic for facts and anchors is agnostic to the underlying persistence mechanism. Each backend implements the same interface with its own storage details (indexes, queries, locking). This design enables rapid prototyping and future plug-in storage choices without refactoring the core logic.

I noticed the use of interface-driven contracts (e.g., `ImmutabilityError`, `NotFoundError`) and the strict enforcement of append-only, immutable record models. This is critical for the project's trust assumptions — once a fact or anchor is stored, it cannot be changed, supporting provenance and traceability.

**What this makes me think:**  
This abstraction is a good engineering choice for a high-throughput, audit-sensitive system. It also creates clear boundaries for testing (in-memory for unit tests, ArangoDB or DuckDB for deployment). However, the current code does not show explicit runtime selection of a backend at initialization — the default seems to be InMemory unless environment variables or configuration are used (not shown here). This could be a future point of fragility if deployment configurations aren't robust.

**Losses:**  
I did not inspect the configuration or initialization logic that selects which backend runs in production — I cannot comment on how dynamic backend switching is managed. Also, I did not deeply analyze the integration between the storage layer and the tensor store (e.g., how provenance and tensorization are coordinated).

---

### Strand 2: Model Design and Data Integrity

**What I saw:**  
The model definitions (e.g., `FactRecord`, `MemoryAnchor`) are strict, using Pydantic validation to enforce immutability and correct timestamp (UTC) usage. Facts are deep-copied to prevent mutation, and the storage layers raise errors on duplicate IDs/handles, upholding the immutability contract. Anchors include cursors per provider and are only written to storage under the two-flag (updated/referenced) policy in the anchor service.

I observed that all timestamps are normalized to UTC via a custom validator. This is important for cross-node and time-zone safety — a common failure point in event systems.

**What this makes me think:**  
The design strongly favors correctness and auditability at the cost of some complexity (deep copies, strict validation). The use of UUIDs for identifiers and timestamps for ordering is sound. However, the models lack metadata about the origin of the data (e.g., source identifiers beyond provider_id). This could be a gap if the system needs to trace provenance beyond just provider.

**Losses:**  
I did not deeply investigate how provenance information (e.g., data source beyond provider) is attached. Likewise, I did not examine how error handling in the storage layers propagates up to the activity service — only the core contract was visible.

---

### Strand 3: Anchor Service Logic and Write Gate

**What I saw:**  
The `MemoryAnchorService` is the orchestrator: it manages cursors per provider, tracks update/referenced flags, and only flushes (persists) anchors when both flags are set. The write gate is a deliberate design choice — it prevents accidental or premature persistence and ensures that both new data and demand (from consumers) are present before committing state. The materialize/freeze flow ensures that the tensor store receives the most current, late-bound view of the stream.

I noticed the use of a fresh handle and timestamp on each flush — this can create a chain of handles/timestamps that are not strictly monotonic if the system scales across nodes or threads, though in this codebase it appears single-threaded. Also, the anchor's cursors are stored as a mutable dict, but the anchor itself is immutable once persisted.

**What this makes me think:**  
This pattern is robust for local, single-process systems but may need enhancement (e.g., atomic increments, distributed consensus) for multi-node deployments. The separation of the "write gate" from raw storage is a good practice for safe, observable systems.

**Losses:**  
I did not examine the concurrency model (threading/multiprocessing) or how this would integrate with distributed systems. Also, I did not investigate the integration with the rest of the tensor infrastructure — how the anchor's materialized view is handed off for tensorization.

---

### Strand 4: Integration Points and Project Connections

**What I saw:**  
The `activity` package appears tightly coupled to the tensor infrastructure via interfaces (e.g., `ApachetaInterface`) and the calling conventions in `anchor.py` (passing tensors to `interface.store_tensor`). However, within the scope of this module, the tensor and provenance handling is deferred — the actual tensor creation and storage is not in this codebase, but in the services that call it.

There is a clear separation between the "stream" (facts/anchors as records) and the "tensor" (structured, provenanced output). This aligns with the project's stated goal of "composable tensor infrastructure" — the activity layer manages the raw stream, while the tensor layer adds structure and provenance.

**What this makes me think:**  
This is a healthy separation — the activity module's responsibility is data management, not interpretation. However, I did not see full evidence of how the various "strands" (as seen in `freeze()`) are composed into tensors with the rest of the system. There is a dependency on external code for the actual tensorization logic.

**Losses:**  
I did not analyze the tensor store code or the tensor models — I can only comment on the interface contracts.

---

### Strand 5: Assumptions and Risks

**What I see assumed:**  
- All storage backends support the required operations (insert, get, index, query) and enforce the immutability contract.
- Time is always UTC and normalized at the model level.
- The system is single-process (or concurrency risks are unknown).
- Provenance beyond provider is not currently tracked, though the interface could support it.
- The activity module is not responsible for tensorization — this is the role of the tensor layer.

**Risks:**  
If the storage backends have race conditions (e.g., concurrent writes in multi-process environments), immutability at the record level does not protect against duplicate or out-of-order records in the underlying storage. Also, the anchor service's write gate could be bypassed if both flags are manipulated externally.

---

### Declared Losses

I did not investigate:
- The initialization and dynamic switching of storage backends (how is ArangoDB/DuckDB chosen in production?).
- The full tensorization pipeline — how the materialized anchor view is transformed into a tensor with provenance.
- Concurrency control for multi-process or distributed deployments.
- How provenance metadata beyond provider is captured or used.
- The error handling path through the activity service to the upper layers.

I chose not to deeply explore these because the current scope is focused on the "activity stream" core — storage, models, and anchor management — and not the tensor layer or deployment mechanics.

---

### Open Questions

1. How does the system select and switch storage backends at runtime?
2. What is the concurrency model for the activity stream (single-threaded? multi-process? distributed)?
3. How is the tensor layer notified of new anchors/facts in real-time, and what is its interface?
4. How is provenance data (e.g., data source, collection ID) attached to facts/anchors?
5. What guarantees are there against storage collisions or out-of-order records if multiple processes access the stream?

---

### Closing

In summary, the `yanantin.activity` codebase presents a robust, model-driven approach to managing an append-only, immutable activity stream with clear separation of concerns between storage, data model, and tensorization/provenance. The architecture supports auditability, scalability (in theory), and easy backend plugging. However, it relies on external components for tensorization, provenance enrichment, and potentially for concurrency control in distributed settings. For robustness in larger deployments, these gaps should be addressed — but as a focused component for an observability pipeline, the design is sound and honest in its boundaries. If modifying this code, I would pay special attention to backend selection, concurrency safety, and integration with the tensor/provenance layers.