<!-- Chasqui Scour Tensor
     Run: 856
     Model: xiaomi/mimo-v2-flash (Xiaomi: MiMo-V2-Flash)
     Target: src/yanantin/activity
     Scope: introspection
     Cost: prompt=$9e-08/M, completion=$2.9e-07/M
     Usage: {'prompt_tokens': 8103, 'completion_tokens': 3719, 'total_tokens': 11822, 'cost': 0.001926, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.001926, 'upstream_inference_prompt_cost': 0.0008103, 'upstream_inference_completions_cost': 0.0011157}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-15T11:23:48.097409+00:00
-->

# Scour Report: Activity Stream Layer

## Preamble

I was pointed at `src/yanantin/activity`, the temporal fact storage and memory anchor service for the Yanantin project. What drew my eye first was the write-gate pattern in `anchor.py` — the two-flag system (`updated` AND `referenced`) that controls when anchors persist. This is the bridge between high-volume fact streams and low-volume tensor storage.

The target structure is clean: models, store interface, anchor service, and three backends (memory, duckdb, arango). The architecture separates append-only facts from authored anchors, with late binding in `materialize()` to include providers registered after anchor creation.

## Strands

### 1. Write-Gate Pattern & Indaleko Heritage

The `MemoryAnchorService` implements a two-flag write gate (`_updated` and `_referenced`) that only persists when both are true. This is directly from Indaleko's `ActivityContextService` pattern.

**What I saw:**
- `anchor.py:48-61` — `update_cursor()` sets `_updated = True`
- `anchor.py:67-70` — `get_handle()` sets `_referenced = True`
- `anchor.py:72-90` — `flush()` only writes if `self._updated and self._referenced`

**What it made me think:**
This prevents noise. Anchors only get stored when:
1. A provider has new data (`update_cursor()` called)
2. Something actually asked for the current position (`get_handle()` called)

If a caller never requests a handle, no anchor is written even if data flows. If data never changes, no anchor is written even if handles are requested. This is efficient but introduces a coupling: the caller must call both methods, and `flush()` must be checked.

**Connection to project:**
This is the epistemic observability layer's clock. Anchors are Lamport ticks — they advance only on state change. The tensor layer (`freeze()`) consumes these ticks to pin provenance.

**Assumption check:**
The assumption is that callers will call `get_handle()` then `flush()` after `update_cursor()`. If a caller forgets `flush()`, data is lost. If a caller calls `get_handle()` multiple times without `update_cursor()`, it wastes handles.

**What would break:**
- Forgetting `flush()` after `update_cursor()` + `get_handle()` = silent data loss
- Race condition: two threads calling `update_cursor()` and `flush()` simultaneously — but `flush()` advances handle, so the second `flush()` would write a new anchor with potentially stale data

### 2. Late Binding in `materialize()`

**What I saw:**
- `anchor.py:103-122` — `materialize()` queries `list_providers()` at resolution time, not at anchor creation time
- It then calls `query_latest(provider_id, before=anchor.timestamp)` for *all* providers

**What it made me think:**
This is brilliant for dynamic systems. A provider registered *after* an anchor is created will still appear in the view if it has facts before the anchor's timestamp. The anchor captures a temporal "slice" but the view is resolved against the *current* universe of providers.

**Example:**
1. T0: Anchor A created with provider P1
2. T1: Provider P2 registers, adds facts at T0.5
3. T2: `materialize(A)` is called
4. Result: View includes P2's facts from T0.5, even though P2 didn't exist when A was created

**Assumption check:**
The assumption is that `query_latest(provider_id, before=anchor.timestamp)` is cheap. In DuckDB/ArangoDB it's O(log n) with indexes. In memory, it's O(log n) with bisect. This holds.

**What would break:**
If a provider's facts are deleted or timestamp is corrupted, `materialize()` could fail or return inconsistent views. But immutability is enforced, so deletion is impossible.

### 3. Immutability Enforcement

**What I saw:**
- `models.py:29-31` — `FactRecord` uses `frozen=True`
- `models.py:54-56` — `AnchorCursor` uses `frozen=True`
- `models.py:71-73` — `MemoryAnchor` uses `frozen=True`
- Backends raise `ImmutabilityError` on duplicate UUID/handle

**What it made me think:**
This is strict append-only semantics. No updates, no deletes. The `deep_copy()` pattern in backends ensures that even if you get a reference, you can't mutate the stored record.

**Connection to project:**
This is the foundation for epistemic observability. You can't change history. The tensor layer's provenance depends on this.

**Assumption check:**
The assumption is that Pydantic's `frozen=True` is enough. It prevents field assignment but doesn't prevent `object.__setattr__` (which is used in validators). However, validators only run on creation, so once stored, it's immutable.

**What would break:**
If someone bypasses Pydantic and mutates the internal dict, the backend's `deep_copy()` might not catch it. But the backends use `model_dump()` then `model_validate()` roundtrip, which would catch type violations.

### 4. Backend Diversity & Query Pushdown

**What I saw:**
- `memory.py` — bisect on sorted lists, O(log n)
- `duckdb.py` — SQL with composite index `(provider_id, timestamp)`, O(log n)
- `arango.py` — AQL with persistent sorted index, O(log n)

**What it made me think:**
All backends implement the same interface but optimize differently. DuckDB and ArangoDB push queries down to the storage engine. Memory backend does in-process binary search.

**DuckDB specifics:**
- `duckdb.py:28-30` — Timestamps stored as VARCHAR (ISO 8601). This is interesting. ISO 8601 strings sort lexicographically correctly if timezone is uniform (UTC). But it's not type-safe in SQL. However, it avoids pytz dependency and works across platforms.
- `duckdb.py:42-50` — Composite index on `(provider_id, timestamp)` enables the `query_latest()` optimization.

**ArangoDB specifics:**
- `arango.py:48-52` — Persistent sorted indexes
- `arango.py:70-82` — AQL queries with bind variables

**Assumption check:**
The assumption is that VARCHAR timestamps sort correctly. They do for UTC ISO 8601: `2024-01-01T00:00:00Z` < `2024-01-01T00:00:01Z`. But if someone inserts a non-UTC timestamp, sorting breaks. The validator in `models.py` enforces UTC, so this is safe.

**What would break:**
- DuckDB: If the index is missing, queries become O(n). But `_init_schema()` creates it.
- ArangoDB: If the AQL query has a syntax error, it would fail at runtime. But the queries are simple.

### 5. Missing Error Handling in `freeze()`

**What I saw:**
- `anchor.py:124-162` — `freeze()` calls `materialize()` then builds a tensor
- `interface.store_tensor(tensor)` is called without try/catch

**What it made me think:**
If `materialize()` fails (e.g., store is corrupted), `freeze()` propagates the exception. If `interface.store_tensor()` fails (e.g., Apacheta backend is down), the anchor is materialized but the tensor is lost. There's no rollback or retry.

**Connection to project:**
This is an "authored act" — freezing is intentional. But it's not atomic. The anchor exists, but the tensor might not.

**Assumption check:**
The assumption is that `interface.store_tensor()` is reliable. But Apacheta could fail (network, disk, etc.).

**What would break:**
If `freeze()` fails mid-way, you have a materialized view that never became a tensor. The caller would need to retry. But there's no idempotency guarantee — retrying might create a duplicate tensor.

### 6. No Cleanup or Compaction

**What I saw:**
- No `delete_fact()`, `delete_anchor()` methods
- No compaction strategy for old anchors or facts

**What it made me think:**
This is append-only forever. Storage will grow unbounded. For a production system, you need:
- TTL or retention policy for facts
- Anchor compaction (keep only latest N anchors, or anchors referenced by tensors)
- Vacuuming orphaned facts (facts not referenced by any anchor or tensor)

**Assumption check:**
The assumption is that storage is cheap and the system is ephemeral. But for long-running observability, this will bloat.

**What would break:**
No immediate break, but long-term: O(n) storage growth, slow queries, memory pressure in memory backend.

### 7. Thread Safety & Lock Granularity

**What I saw:**
- All backends use `threading.RLock()`
- Each method acquires the lock for its entire duration

**What it made me think:**
This is coarse-grained locking. For high-throughput scenarios, this could be a bottleneck. But for an observability layer, throughput is likely moderate.

**Assumption check:**
The assumption is that operations are fast enough that holding the lock for the whole method is fine. For DuckDB/ArangoDB, I/O is the bottleneck, not the lock. For memory backend, bisect is O(log n), so it's fast.

**What would break:**
If a caller does long-running work inside a method (e.g., `materialize()` calls `query_latest()` for many providers), it blocks other threads. But `materialize()` is O(m * log n) where m is number of providers, which is likely small.

### 8. Content Hash in FactRecord

**What I saw:**
- `models.py:27` — `content_hash: str = ""` in `FactRecord`
- `duckdb.py:70` — stored in DB
- `arango.py` — not used in queries, just stored

**What it made me think:**
The hash is present but unused in the activity layer. It's likely for the tensor layer to detect duplicate content or verify integrity. But it's optional and defaults to empty string.

**Assumption check:**
The assumption is that providers will populate this if needed. But there's no validation that it's a valid hash.

**What would break:**
Nothing in this layer. But the tensor layer might depend on it for deduplication.

### 9. Connection to Apacheta

**What I saw:**
- `anchor.py:10` — imports `ApachetaInterface`
- `freeze()` takes an `ApachetaInterface` parameter
- `freeze()` creates `TensorRecord` and calls `interface.store_tensor()`

**What it made me think:**
The activity layer is a *source* of tensors for Apacheta. It doesn't depend on Apacheta for storage — only for publishing frozen views. This is clean separation.

**Assumption check:**
The assumption is that `ApachetaInterface` is always available when `freeze()` is called. If not, `freeze()` fails.

**What would break:**
If Apacheta is down, you can't freeze anchors. But you can still update cursors and flush anchors. The system degrades gracefully.

### 10. Provider ID Semantics

**What I saw:**
- `models.py:19` — `FactRecord.provider_id: UUID`
- `anchor.py:48` — `update_cursor(provider: UUID, reference: UUID, ...)`
- `store.py:28` — `query_latest(provider_id: UUID, ...)`

**What it made me think:**
Provider IDs are UUIDs, but there's no registry of providers. You can call `update_cursor()` with any UUID, and it just works. This is flexible but could lead to orphaned cursors if a provider UUID is never used again.

**Assumption check:**
The assumption is that providers are well-known and stable. But there's no validation that a provider exists before using its ID.

**What would break:**
If you use a random UUID as provider, you'll create a cursor for it, but it will never have facts unless you also store facts for that provider. This is fine but could confuse `materialize()`.

## Declared Losses

I did not examine:
- **Apacheta models** (`ProvenanceEnvelope`, `TensorRecord`, etc.) — I saw they're imported and used, but didn't inspect their structure. I assumed they work as intended.
- **Full AQL query in arango.py** — The code snippet was truncated at line 109, so I didn't see the complete `query_range()` implementation. I inferred it from context.
- **Exact bisect logic in memory.py** — I didn't trace the tuple comparison edge cases for `before + timedelta(microseconds=1)`. I trust it's correct but didn't verify with examples.
- **StorageObfuscator** — Used in ArangoDB but not defined. I assumed it's a name-mapping layer and doesn't affect logic.
- **External Apacheta interface errors** — Imported but not inspected.

I ran out of attention for the exact SQL query construction in `duckdb.py`'s `query_range()` and the full AQL in `arango.py`. The pattern is clear, but the exact string formatting could have subtle bugs.

## Open Questions

1. **Idempotency of `freeze()`**: If `freeze()` fails after materializing but before storing the tensor, can it be safely retried? Should there be a `frozen` flag on anchors?

2. **Anchor retention policy**: How long should anchors be kept? Is there a cleanup process? The system is append-only, but production needs TTL.

3. **Content hash usage**: What algorithm is expected for `content_hash`? Is it used for deduplication in Apacheta?

4. **Provider lifecycle**: What happens if a provider is decommissioned? Its cursors remain in anchors, but `materialize()` will still query it. Should there be a `list_active_providers()`?

5. **Clock skew**: Anchors use `datetime.now(timezone.utc)`. If the system clock jumps (NTP sync, VM resume), anchors could have non-monotonic timestamps. Is this a concern?

6. **Handle collision**: `uuid4()` is used for handles. The probability is astronomically low, but if it happens, `store_anchor()` raises `ImmutabilityError`. Should there be a retry loop?

7. **Deep copy cost**: `deep_copy()` does a full model roundtrip. For large `FactRecord.data`, this could be expensive. Is this acceptable for the memory backend?

## Closing

This is a well-designed, clean separation of concerns. The write-gate pattern is elegant and prevents unnecessary writes. Late binding in `materialize()` is a powerful feature for dynamic systems. The backend abstraction is solid, with query pushdown for performance.

**What I'd tell someone about to modify it:**

1. **Don't break the write-gate**: If you add new write paths, ensure both flags are set. If you remove flags, you'll lose the "only write when needed" optimization.

2. **Respect immutability**: Never mutate stored records. The `deep_copy()` pattern is your friend. If you add new fields, ensure they're frozen.

3. **Test with real timestamps**: The VARCHAR timestamp sorting works, but test with edge cases (leap seconds, DST transitions — though UTC avoids DST).

4. **Handle `freeze()` failures**: Consider adding a retry mechanism or a `frozen` flag on anchors to prevent duplicate tensors.

5. **Plan for compaction**: You'll need a way to clean up old facts and anchors. Design it early, before storage is 100GB.

6. **Provider registry**: Consider adding a provider metadata table to track active providers and prevent orphaned cursors.

7. **Lock granularity**: If you see lock contention, consider splitting the lock (one for facts, one for anchors) or using finer-grained locks.

**What I know:**
- The architecture is sound
- The patterns are consistent with Indaleko
- The backends are optimized for their storage engines
- The write-gate prevents noise

**What I don't know:**
- Exact query performance at scale (millions of facts)
- How Apacheta handles tensor storage and retrieval
- The full lifecycle of providers and consumers

**What I made up:**
- I assumed `StorageObfuscator` is a name-mapping layer
- I assumed `ApachetaInterface` is reliable and always available
- I assumed the system is for moderate throughput, not high-frequency trading

Overall, this is a solid foundation for epistemic observability. The main risks are long-term storage growth and `freeze()` failure handling.