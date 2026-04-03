<!-- Chasqui Scour Tensor
     Run: 1575
     Model: meituan/longcat-flash-chat (Meituan: LongCat Flash Chat)
     Target: src/yanantin/activity
     Scope: introspection
     Cost: prompt=$2e-07/M, completion=$8e-07/M
     Usage: {'prompt_tokens': 8314, 'completion_tokens': 2014, 'total_tokens': 10328, 'cost': 0.003274, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.003274, 'upstream_inference_prompt_cost': 0.0016628, 'upstream_inference_completions_cost': 0.0016112}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-03T10:16:32.794726+00:00
     GenerationID: gen-1775211371-KO5Sv3oSjia7bn4Quc5W
-->

### Preamble  
I was pointed at the `src/yanantin/activity` directory, specifically focusing on the **introspection** scope. This is the activity stream layer of the Yanantin project, which handles temporal fact storage and memory anchors. What drew my attention first was the **two-store duality**: *ActivityStreamStore* (facts) and *ApachetaInterface* (tensors), bridged by the *MemoryAnchorService*. The design appears to be a temporal/epistemic bridge between raw observations (facts) and authored knowledge (tensors). The prominent use of UUIDs, temporal indexing, and immutability patterns suggests a strong focus on **traceability and auditability** — core for epistemic observability.

---

### Strands  

#### 1. **Two-Store Architecture and the Write Gate**  
- **Where**: `__init__.py` docstring, `anchor.py` (MemoryAnchorService), `store.py` (interface)
- **What**: The system cleanly separates high-volume facts (`ActivityStreamStore`) from low-volume tensors (`ApachetaInterface`). The `MemoryAnchorService` acts as a gatekeeper: anchors (cursors) are only persisted when **both** flags (`_updated` and `_referenced`) are set — the "write gate". This implements Indaleko's pattern: persist only when there's a change *and* someone cares.
- **Thoughts**: This is a smart **anti-spam** mechanism. It avoids polluting the anchor store with meaningless cursor advances. The gate ensures that anchors are only written when they are *semantically meaningful* (someone asked for a handle). This directly supports the project's goal of **epistemic observability** — not just tracking what happened, but tracking what was *observed as meaningful*.
- **Risk**: If the gate logic is bypassed (e.g., via direct store access), anchors could be written without semantic significance. The service must be the **only** entry point for anchor creation.
- **Connection**: This mirrors broader project themes of **composable epistemic layers** — facts → anchors → tensors.

#### 2. **Temporal Indexing and Backend Diversity**  
- **Where**: `backends/arango.py`, `backends/memory.py`, `backends/duckdb.py`, `store.py`
- **What**: All backends implement the same abstract interface (`ActivityStreamStore`) but differ in indexing strategy:
  - **ArangoDB**: Uses persistent sorted indexes on `(provider_id, timestamp)` for O(log n) queries.
  - **Memory**: Uses `bisect` on sorted lists of `(timestamp, fact_id)`.
  - **DuckDB**: Uses indexed SQL queries with timestamps as ISO 8601 strings (to avoid pytz).
- **Thoughts**: The project **commits to temporal ordering** as a first-class citizen. The use of UTC-only timestamps (enforced via `_ensure_utc`) is critical — naive timestamps would break sort order and queries. DuckDB’s choice of `VARCHAR` for timestamps is pragmatic (ISO 8601 sorts correctly) and avoids timezone library dependencies.
- **Risk**: DuckDB and ArangoDB backends **omit obfuscation** (unlike Apacheta). This assumes local storage is trusted (Pukara boundary). If this assumption fails, data leakage could occur. The `backends/__init__.py` also **lazy-loads** DuckDB/ArangoDB, which is good for dependency hygiene but could confuse users who expect all backends to be importable.
- **Missing**: No backend supports **time-range queries across providers** (e.g., "all facts between T1 and T2"). This could be useful for global event analysis.

#### 3. **Immutability and Deep Copying**  
- **Where**: All backends, `models.py` (frozen Pydantic models)
- **What**: Facts and anchors are **immutable** — duplicate IDs/handles raise `ImmutabilityError`. Backends use **deep-copy on read/write** (e.g., `_deep_copy` in memory.py, `model_dump`/`model_validate` in ArangoDB).
- **Thoughts**: Immutability is **enforced at the store level**, not just the model level. This prevents accidental state corruption. Deep copying ensures that callers can’t mutate internal state via references — a critical thread-safety measure.
- **Risk**: Deep copying could be expensive for large `FactRecord.data` (schema-agnostic dicts). The project assumes facts are **small-ish** (author’s comment: "raw observations"). If facts grow large, performance could suffer.
- **Connection**: This aligns with the Apacheta interface’s immutability contract, ensuring consistency across the tensor stack.

#### 4. **Late-Binding in Anchor Resolution**  
- **Where**: `anchor.py` (materialize method)
- **What**: When resolving an anchor (`materialize`), the service **queries `list_providers()` at resolution time**, not just the providers in the anchor’s cursor list. This means a provider added after the anchor was created will appear in the view if it has facts before the anchor’s timestamp.
- **Thoughts**: This is a powerful **late-binding** pattern. It ensures that the view is always **fresh and complete** — no need to re-issue anchors when new providers join. However, it also means that the same anchor handle can resolve to different fact sets over time (if new providers are added). This could surprise users who expect anchors to be **fixed snapshots**.
- **Risk**: If providers are added and facts are backfilled (before the anchor’s timestamp), the view will change. This might break expectations in audit scenarios. The project likely accepts this trade-off for **completeness**.

#### 5. **Tensor Freezing and Authorship**  
- **Where**: `anchor.py` (freeze method)
- **What**: The `freeze` method pins a temporal view into a permanent tensor via `ApachetaInterface`. It creates two strands: a human-readable summary and a JSON-serialized dump of the anchor/facts.
- **Thoughts**: This is where **authorship** happens — the system doesn’t just store data; it **makes a claim**. The tensor is marked with `provenance` and `lineage_tags`, linking it back to the anchor handle. This is the project’s "frozen view" mechanism.
- **Missing**: No support for **selective freezing** (e.g., "only freeze facts from provider X"). The current design freezes the entire view. This might be too coarse for some use cases.

---

### Declared Losses  
- **Omitted Examine**:  
  1. **Error handling in DuckDB/ArangoDB backends** — I didn’t scrutinize the SQL/AQL injection risks (though the code uses parameterized queries, I didn’t verify all cases).  
  2. **Thread-safety edge cases** — The `RLock` usage looks correct, but I didn’t stress-test for deadlocks or race conditions.  
  3. **Performance benchmarks** — I didn’t analyze the scalability limits of each backend (e.g., DuckDB at 100M facts).  
  4. **Integration with ApachetaInterface** — I assumed the interface works as documented but didn’t check its implementation.  
- **Why**: My focus was on **design patterns and guarantees**, not low-level implementation details. These losses are acceptable for a first-pass introspection.

---

### Open Questions  
1. **How are `AnchorCursor.reference` values generated?** The code treats them as opaque UUIDs, but where do they come from? Are they fact IDs? Something else?  
2. **What is the trust model for `StorageObfuscator`?** It’s referenced in ArangoDB but not used in DuckDB (which assumes local trust). Is this a deliberate choice?  
3. **How is garbage collection handled?** Facts and anchors are immutable and never deleted — does the system have a pruning policy?  
4. **What happens if a provider is removed?** If a provider is deregistered, will `list_providers()` still return its UUID? How are dangling cursors handled?  
5. **Is `content_hash` used?** It’s in `FactRecord` but never referenced in the code. Is it a placeholder?  

---

### Closing  
This is a **well-designed, cohesive layer** that cleanly separates concerns while enforcing critical invariants (immutability, temporal ordering, write gates). The code is **defensive** (UTC timestamps, deep copying, immutability errors) and **pragmatic** (DuckDB/ArangoDB trade-offs).  

**Advice for modifiers**:  
- **Don’t break the write gate** — it’s core to the project’s semantics.  
- **Respect the immutability contract** — bypassing it will corrupt trust.  
- **Consider the late-binding behavior** — anchors are "living" until frozen.  
- **Watch performance** — deep copying and fact resolution could be bottlenecks.  
- **Follow the UTC mandate** — naive timestamps will break everything.  

The module feels like a **solid foundation** for epistemic observability. The biggest risk is **undocumented assumptions** (e.g., cursor semantics, garbage collection), but the code itself is clear and well-documented.