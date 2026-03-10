<!-- Chasqui Scour Tensor
     Run: 589
     Model: nvidia/nemotron-3-nano-30b-a3b (NVIDIA: Nemotron 3 Nano 30B A3B)
     Target: src/yanantin/activity
     Scope: introspection
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 8361, 'completion_tokens': 2387, 'total_tokens': 10748, 'cost': 0.00089545, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00089545, 'upstream_inference_prompt_cost': 0.00041805, 'upstream_inference_completions_cost': 0.0004774}, 'completion_tokens_details': {'reasoning_tokens': 193, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-10T12:40:20.317519+00:00
-->

**Tensor — Scoured Observation of `src/yanantin/activity`**  

---

### Preamble  
I was directed to the **activity** package of the Yanantin project. This package implements the low‑level temporal store that backs the project’s “introspection” layer:  
* **Facts** – raw, schema‑agnostic observations from data providers.  
* **Anchors** – immutable cursors that mark a provider’s position in the stream.  
* **Views** – ephemeral resolutions of an anchor against the current set of providers.  
* **Back‑ends** – three concrete implementations (`InMemory`, `DuckDB`, `ArangoDB`) that share a common `ActivityStreamStore` abstract interface.  

The first thing that caught my eye was the **strict immutability contract** enforced throughout the codebase (e.g., `store_fact` raises `ImmutabilityError` on duplicate UUIDs, anchors are frozen, views are never cached). This contract is the backbone of the project’s epistemic observability guarantees and is the source of many design‑level assumptions that ripple into the rest of Yanantin.

---

### Strands  

| # | Theme (Strand) | Evidence (file / line / snippet) | Immediate Insight / Question |
|---|----------------|----------------------------------|------------------------------|
| 1 | **Immutability & UUID‑based identity** | `models.py` – `FactRecord` (`frozen=True`), `AnchorCursor` (`frozen=True`), `MemoryAnchor` (`frozen=True`), `store_fact` / `store_anchor` implementations in each backend raise `ImmutabilityError` on duplicate keys. | Guarantees that once a fact or anchor is persisted it cannot be overwritten. This is essential for auditability but forces the system to allocate new UUIDs for every update, which may affect scalability and storage cost. |
| 2 | **Temporal indexing strategy** | `InMemoryActivityStreamStore` uses `bisect` on `(timestamp, fact_id)` lists (lines 45‑63). `DuckDB` stores timestamps as ISO‑8601 VARCHAR and creates a composite index on `(provider_id, timestamp)` (lines 31‑33). `ArangoDB` adds a persistent sorted index on `(provider_id, timestamp)` via `add_index` (lines 73‑78). | All back‑ends rely on a **sorted temporal index** to answer `query_latest` and `query_range` in O(log n). The choice of string timestamps is portable but brittle if timezone handling drifts. |
| 3 | **Late‑binding provider discovery** | `MemoryAnchorService.materialize` queries `list_providers()` each time an `AnchorView` is built (line 140‑150). The comment notes “late‑bound: includes providers registered after the anchor was created.” | This enables **dynamic provider addition** without recreating anchors, but it means every materialization incurs a full provider enumeration and a round‑trip to the store for each provider’s latest fact. Performance impact depends on provider count. |
| 4 | **Write‑gate logic (updated ∧ referenced)** | `MemoryAnchorService.flush` returns `False` unless both `_updated` and `_referenced` are true (lines 84‑108). After a successful flush it creates a new handle/UUID and resets flags. | This two‑flag pattern decouples *provider updates* from *consumer interest*. If a consumer never calls `get_handle`, no anchor is ever persisted, which can be useful for “dry‑run” analyses but also means any missing `get_handle` call silently drops the anchor. |
| 5 | **Separation of concerns between store and tensor layer** | `activity/__init__.py` re‑exports `ActivityStreamStore`, models, and `MemoryAnchorService`. The comment explains that `ActivityStreamStore` is “temporal fact storage” while “ApachetaInterface” handles “authored tensor storage.” | The layering is clear, but the **concrete `ApachetaInterface` implementation** is not present in this package; it lives elsewhere. Any change to the store API must be reflected consistently in the tensor layer, otherwise the `freeze` method would break. |
| 6 | **Backend modularity & optional dependencies** | `activity/__init__.py` deliberately does **not** import `arango` or `duckdb` at package level; they are imported only when needed (comment block). | This keeps the core package lightweight for users who only need the in‑memory backend. However, the documentation does not warn about missing optional dependencies when a backend is requested, which could cause obscure import errors at runtime. |
| 7 | **Error handling & exception hierarchy** | All back‑ends raise `ImmutabilityError` and `NotFoundError` from `yanantin.apacheta.interface.errors`. These are defined in `apacheta/interface/errors.py` (not shown). | The exceptions are shared across the whole project, ensuring callers can catch a single base error type. It would be useful to see the base class definition to understand the full hierarchy. |

---

### Declared Losses  

| Loss | Why it was not examined |
|------|--------------------------|
| **Full source of `store.py`** | The snippet ends with `... (56 more lines truncated)`. I did not read those lines, so I cannot comment on additional abstract methods or hidden invariants. |
| **Implementation details of `DuckDB`/`ArangoDB` query_range** | Only the opening portion of `backends/duckdb.py` and a large chunk of `backends/arango.py` were truncated in the provided listing. I observed the schema and index creation, but the rest of the query logic (e.g., handling of edge‑cases, pagination, error handling) is unknown. |
| **`apacheta/apacheta/models.py` and `apacheta/apacheta/interface.py`** | Those files contain `TensorRecord`, `ProvenanceEnvelope`, etc., used by `MemoryAnchorService.freeze`. I have not inspected them, so I cannot verify the exact shape of the tensor payload or the provenance schema. |
| **`apacheta/apacheta.storage_obfuscator`** | Used in `ArangoDBActivityStreamStore` to map collection/field names. The opaque `StorageObfuscator` implementation was not inspected, so I cannot assess its impact on queryability or debugging. |
| **Thread‑safety edge cases** | While each backend uses an `RLock`, I did not examine concurrent‑access tests or the interaction with Python’s GIL in async contexts. |

---

### Open Questions  

1. **What guarantees does the system provide when a provider’s cursor reference changes but the same logical position is reused?**  
   The `update_cursor` method returns `False` if the reference is unchanged, but the semantics of “reference” (e.g., is it a monotonically increasing counter?) are unclear.  

2. **How does the system behave under clock skew?**  
   All timestamps are forced into UTC, but the code raises an error for naïve datetimes. If a collector inadvertently sends a naive datetime, it fails fast. However, what happens if two providers generate facts with the *same* UTC timestamp? The bisect ordering on `(timestamp, fact_id)` uses the tuple comparison; the `fact_id` (UUID) provides a deterministic tie‑breaker, but this is not documented.  

3. **What is the intended lifecycle of the `MemoryAnchorService` instance?**  
   The service holds a single persistent `handle` and `timestamp`. When `flush` succeeds it creates a *new* handle. Does the old handle remain usable for `materialize` after a flush? If so, could stale handles be materialized against a different anchor state?  

4. **Are there any constraints on the size of `data` fields in `FactRecord`?**  
   `data` is stored as a raw `dict` (JSON‑serialized in DuckDB/Arango). Large payloads could bloat the store and affect query performance. No size limits or compression are evident.  

5. **How does the project plan to handle schema evolution for `data` fields?**  
   Since `FactRecord` is frozen and `data` can contain any keys (`extra="allow"`), downstream consumers must evolve their interpretation of `data` independently. There is no migration strategy visible in the code.  

6. **What is the expected scaling behavior of the ArangoDB backend at “28.5M facts”?**  
   The comment mentions that loading all records then filtering is not viable at that scale. The index on `(provider_id, timestamp)` should make range queries O(log n), but I have not seen any benchmark or pagination logic that would bound memory usage for very large result sets.  

---

### Closing  

The **activity** module is a well‑engineered, tightly‑coupled set of components that together provide a robust, append‑only temporal store with strong immutability guarantees. Its design intentionally separates **observation** (facts) from **authoring** (tensor freeze), enabling flexible downstream analysis while preserving provenance.

If you intend to modify this codebase, keep the following in mind:

* **Preserve the immutability contract** – any operation that mutates a stored fact or anchor will raise `ImmutabilityError` and break the project’s audit trail.  
* **Maintain the temporal index semantics** – changing the representation of timestamps or the ordering key will invalidate the O(log n) query guarantees and may break `query_latest`/`query_range`.  
* **Mind the optional backend dependencies** – importing `arango` or `duckdb` at package import time could unintentionally pull heavyweight libraries into environments that only need the in‑memory store.  
* **Watch the write‑gate** – forgetting to call `get_handle` before `flush` will silently drop anchors; ensure every anchor you intend to persist is referenced.  

Overall, the package is **sound but fragile** in the sense that its correctness hinges on many small, explicit invariants (UUID uniqueness, UTC timestamps, sorted index integrity). Modifications should be accompanied by unit tests that verify those invariants remain intact across all back‑ends.