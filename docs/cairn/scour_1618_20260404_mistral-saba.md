<!-- Chasqui Scour Tensor
     Run: 1618
     Model: mistralai/mistral-saba (Mistral: Saba)
     Target: src/yanantin/activity
     Scope: introspection
     Cost: prompt=$2e-07/M, completion=$6e-07/M
     Usage: {'prompt_tokens': 8344, 'completion_tokens': 2022, 'total_tokens': 10366, 'cost': 0.002882, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.002882, 'upstream_inference_prompt_cost': 0.0016688, 'upstream_inference_completions_cost': 0.0012132}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-04T07:50:30.165498+00:00
     GenerationID: gen-1775289009-FOsP085MBJmiWXrpG6k1
-->

### Preamble
You directed me to examine `src/yanantin/activity`, a directory implementing the **activity stream layer** for the Yanantin project. This layer handles temporal fact storage and memory anchors—two critical components for epistemic observability. My attention was first drawn to the **duality of immutability and dynamism**: facts are append-only, immutable records, while anchors are cursors that advance only when both "updated" and "referenced" flags are set. This tension between permanence and change feels central to the project's design.

---

### Strands

#### Strand 1: **The Dual Store Contract (models.py, store.py, anchor.py)**
- **Observed**:
  - `ActivityStreamStore` abstracts two append-only record types: `FactRecord` (raw observations) and `MemoryAnchor` (immutable snapshots of cursor state).
  - `MemoryAnchorService` bridges these stores by implementing a **two-flag write gate** (`updated` and `referenced`). An anchor is persisted only when both flags are set (see `flush()` in `anchor.py`).
  - `FactRecord` is schema-agnostic (`extra="allow"`), while `MemoryAnchor` is rigid (`extra="forbid"`). This reflects their roles: facts are raw data, anchors are structured metadata.
- **Connections**:
  - The store contract (`store.py`) is reused across backends (`arango.py`, `duckdb.py`, `memory.py`), all enforcing immutability (`ImmutabilityError` on duplicates).
  - `anchor.py`’s `materialize()` method performs **late binding**: it re-queries provider lists at resolution time, ensuring new providers are included even if registered after an anchor was created.
- **Questions**:
  - Why enforce `extra="allow"` for `FactRecord`? Could this lead to schema drift if downstream consumers assume a stable structure?
  - The write gate’s "updated AND referenced" logic mirrors **Indaleko’s ActivityContextService**. Is this pattern robust for distributed systems where messages might be lost?

#### Strand 2: **Temporal Query Optimization (backends/*)**
- **Observed**:
  - Backends optimize for temporal queries using:
    - **ArangoDB**: Persistent sorted indexes on `(provider_id, timestamp)` and `timestamp` (AQL pushdown).
    - **DuckDB**: Composite index on `(provider_id, timestamp)` with SQL query pushdown. Timestamps are stored as ISO 8601 strings for portability.
    - **Memory**: In-memory bisect on sorted lists of `(timestamp, fact_id)`.
  - All backends enforce **O(log n) temporal queries** (e.g., `query_latest`, `query_range`).
- **Thoughts**:
  - The **string-serialized timestamps** in DuckDB (`isoformat()`) are clever for avoiding pytz dependencies, but they risk subtle bugs if comparisons assume lexicographic order (though ISO 8601 is designed for this).
  - **Memory backend’s deep-copy strategy** (see `InMemoryActivityStreamStore._deep_copy`) mirrors Apacheta’s `InMemoryBackend`, suggesting a shared design philosophy. Is this a performance bottleneck for large datasets?
- **Breakage**:
  - Changing the timestamp format in DuckDB could silently break temporal queries.
  - Removing the composite index in ArangoDB would degrade performance to O(n).

#### Strand 3: **Authored Acts and Tensors (anchor.py:freeze())**
- **Observed**:
  - `MemoryAnchorService.freeze()` pins a temporal view into a permanent tensor via `ApachetaInterface.store_tensor()`.
  - The tensor includes:
    - **Strand 0**: Anchor summary (metadata).
    - **Strand 1**: Anchor data (cursor state + resolved facts).
  - The `preamble` and `lineage_tags` explicitly encode provenance (e.g., `"anchor", "frozen-view"`).
- **Connections**:
  - This is the **Yanantin project’s core goal**: composable tensor infrastructure for epistemic observability. The `freeze()` method is where temporal activity becomes an authored artifact.
  - The `content_hash` field in `FactRecord` hints at a future need for integrity verification (though it’s unused in `models.py`).
- **Assumptions**:
  - The `ApachetaInterface` is assumed to be available and functional. If it fails, `freeze()` will raise an exception, but the anchor service itself remains consistent.
  - The tensor’s `source.identifier` uses the anchor’s `handle`, tying the authored act directly to the memory anchor.

#### Strand 4: **Thread Safety and Immutability Enforcement**
- **Observed**:
  - All backends use **threading.RLock** for thread safety (e.g., `store_fact`, `query_latest`).
  - Immutability is enforced at the **store level** (`ImmutabilityError` on duplicate UUIDs/handles) and **model level** (`frozen=True` in Pydantic models).
- **Thoughts**:
  - The **deep-copy strategy** in the memory backend ensures thread safety but may hide mutations (e.g., if `FactRecord.data` contains mutable objects, deep-copy might not be deep enough).
  - **ArangoDB’s obfuscator pattern** (`StorageObfuscator`) suggests a security-conscious design, but the `TransparentObfuscator` is the default. Is this sufficient for sensitive data?

#### Strand 5: **Schema Agility vs. Consistency**
- **Observed**:
  - `FactRecord` allows extra fields (`extra="allow"`), while `MemoryAnchor` forbids them (`extra="forbid"`).
  - Backends like DuckDB use JSON for `data` fields, enabling schema flexibility.
- **Tensions**:
  - Schema-agnostic facts enable adaptability but risk **inconsistent interpretations** downstream.
  - Anchors are rigid to ensure **reproducible resolution** during `materialize()`.
- **Missing**:
  - A **schema registry** or **validation layer** for `FactRecord.data` to prevent drift.

---

### Declared Losses
I chose not to examine:
1. **The full implementations of `ArangoDBActivityStreamStore` and `DuckDBActivityStreamStore`** (lines were truncated). I focused on their interfaces and design patterns rather than the low-level query optimizations.
2. **The `content_hash` field in `FactRecord`**: It’s unused in the provided code, so I couldn’t determine its purpose or integration.
3. **Error handling beyond `ImmutabilityError` and `NotFoundError`**: For example, how does the system recover from a failed `store_fact` in ArangoDB?
4. **The `StorageObfuscator` pattern**: I didn’t explore how obfuscation interacts with the activity stream’s immutability guarantees.

---

### Open Questions
1. **Distributed Coordination**: The write gate (`updated AND referenced`) assumes a single-threaded or atomic environment. How would this work in a distributed system where multiple services might call `update_cursor` or `get_handle` concurrently?
2. **Backpressure**: The `flush()` method in `MemoryAnchorService` doesn’t handle backpressure. What if the underlying store (e.g., ArangoDB) is slow or unavailable?
3. **Schema Evolution**: How are schema changes handled for `FactRecord`? For example, if a provider starts sending a new field, does it break downstream consumers?
4. **Provenance Depth**: The tensor created by `freeze()` includes provenance, but does it capture the **full lineage** of the facts it references (e.g., who wrote them, when, and why)?

---

### Closing
This part of the codebase is **a masterclass in balancing tension**:
- **Immutability vs. Change**: Facts are forever; anchors advance only when necessary.
- **Flexibility vs. Consistency**: Schema-agnostic facts enable adaptability; anchors enforce structure.
- **Performance vs. Simplicity**: Backends optimize for temporal queries, but the abstractions remain clean.

**Advice for Modifiers**:
1. **Preserve Immutability**: Any changes to `store.py` or the backends must maintain the append-only contract. Breaking this would corrupt the entire activity stream.
2. **Validate Timestamps**: Ensure all datetime handling uses UTC and rejects naive datetimes (see `_ensure_utc` in `models.py`). Naive datetimes will silently break temporal queries.
3. **Test Late Binding**: The `materialize()` method’s late binding is powerful but fragile. Add tests for scenarios where providers are added/removed between anchor creation and resolution.
4. **Monitor Write Gate**: The `flush()` logic is subtle. Add metrics to track how often the write gate opens/doesn’t open—this could reveal coordination issues in distributed setups.
5. **Schema Hygiene**: If `FactRecord.data` becomes a dumping ground, consider adding a lightweight validation layer (e.g., JSON Schema) to prevent silent drift.

**Final Impression**:
The `yanantin/activity` layer is **the backbone of the Yanantin project’s epistemic observability**. It turns raw, high-volume observations into structured, authored tensors—all while maintaining thread safety, immutability, and performance. The design is **elegant but not fragile**; it assumes correctness in its contracts and optimizes for the happy path. If you modify it, tread lightly.