<!-- Chasqui Scour Tensor
     Run: 1821
     Model: mistralai/mistral-small-2603 (Mistral: Mistral Small 4)
     Target: src/yanantin/activity
     Scope: introspection
     Cost: prompt=$1.5e-07/M, completion=$6e-07/M
     Usage: {'prompt_tokens': 8351, 'completion_tokens': 1930, 'total_tokens': 10281, 'cost': 0.00241065, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00241065, 'upstream_inference_prompt_cost': 0.00125265, 'upstream_inference_completions_cost': 0.001158}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-12T15:11:17.393642+00:00
     GenerationID: gen-1776006663-DOHEIEvMkXqZRhlWjkem
-->

```markdown
### Preamble
Examining `src/yanantin/activity` with a focus on **introspection** within the Yanantin project. The activity layer is a critical bridge between raw provider facts and authored tensors, implementing temporal storage and memory anchors. Within the target, `memory.py`, `arango.py`, `duckdb.py`, `store.py`, `models.py`, and `anchor.py` form a cohesive subsystem. The first draw was the **duality of immutability vs. temporal mutability** — facts and anchors are immutable, but their *collections* (streams, cursors) evolve over time. The use of `RLock` across all backends signals a shared design goal: thread safety under high-volume append operations.

---

### Strands

#### 1. **Immutability as a Contract**
- **Observed**:
  - Facts (`FactRecord`) and anchors (`MemoryAnchor`) are `frozen=True` Pydantic models.
  - `store_fact()` and `store_anchor()` raise `ImmutabilityError` on duplicate UUID/handle.
  - Deep-copy behavior in `InMemoryActivityStreamStore` ensures caller isolation.
- **Connections**:
  - Tied to the Apacheta pattern of immutable data boundaries (imported from `yanantin.apacheta.interface.errors`).
  - Anchors act as Lamport clock ticks — their `handle` advances only when state changes.
- **Assumptions**:
  - Providers never correct past facts — only append. This is a valid assumption for an *observation stream*, not a mutable dataset.
  - Breaking immutability here would corrupt temporal queries (e.g., `query_latest()` would return inconsistent results).
- **Breaking Change**:
  - Removing `frozen=True` or deep-copy would allow mutations, breaking thread safety and temporal correctness.

#### 2. **Temporal Query Patterns**
- **Observed**:
  - All backends implement `query_latest()` and `query_range()` with O(log n) performance:
    - `memory.py`: Uses `bisect` on sorted lists of `(timestamp, UUID)`.
    - `arango.py`: Relies on persistent sorted indexes with AQL pushdown.
    - `duckdb.py`: Uses composite index `(provider_id, timestamp)` with SQL `ORDER BY`.
  - `AnchorView.materialize()` performs **late binding** — it queries `list_providers()` at resolution time, not anchor creation.
- **Connections**:
  - The activity layer is designed for **epistemic observability** — queries must reflect the *current state of the world*, not a stale snapshot.
  - Late binding ensures new providers are included even if registered after an anchor was created.
- **Assumptions**:
  - Timestamps are stored as timezone-aware UTC datetimes (enforced in `models.py` via `_ensure_utc`).
  - Breaking this would corrupt sort order and query correctness.
- **Breaking Change**:
  - Switching to naive datetimes would silently corrupt temporal queries.

#### 3. **The Write Gate Pattern**
- **Observed**:
  - `MemoryAnchorService` implements a **two-flag write gate**:
    - `updated`: Set when a provider’s cursor advances (`update_cursor()`).
    - `referenced`: Set when a caller requests a handle (`get_handle()`).
  - `flush()` persists the anchor only if both flags are set.
  - This mirrors Indaleko’s `ActivityContextService` pattern.
- **Connections**:
  - The gate ensures anchors are **not stored unnecessarily** — a provider may update its cursor without an anchor being materialized.
  - Bridges the activity stream (temporal, append-only) with tensors (authored, immutable).
- **Assumptions**:
  - Providers are trusted to report accurate cursor positions.
  - Callers will request handles when they need to freeze state.
- **Breaking Change**:
  - Removing the gate would bloat the store with redundant anchors.

#### 4. **Backend Abstraction and Dependency Management**
- **Observed**:
  - Backends are **not imported at package level** (`backends/__init__.py` only exposes `InMemoryActivityStreamStore`).
  - Users must import directly (e.g., `from yanantin.activity.backends.arango import ArangoDBActivityStreamStore`).
  - `arango.py` and `duckdb.py` are **conditionally heavy**:
    - `python-arango` and `duckdb` are not required for all users.
    - ArangoDB requires a pre-provisioned database.
- **Connections**:
  - The project avoids dependency bloat for users who only need in-memory testing.
  - ArangoDB’s error handling in `_connect_database()` is **fail-stop** — it requires an admin to provision the database first.
- **Assumptions**:
  - Production users will handle dependency installation and database setup.
  - Test users will use `InMemoryActivityStreamStore`.
- **Breaking Change**:
  - Forcing all dependencies at package level would increase installation friction.

#### 5. **Obfuscation and Trust Boundaries**
- **Observed**:
  - Only `arango.py` uses `StorageObfuscator` (via `TransparentObfuscator` by default).
  - `duckdb.py` and `memory.py` skip obfuscation entirely.
  - ArangoDB’s design mentions a **least-privilege user** with restricted access.
- **Connections**:
  - The Yanantin project runs on **Pukara** (trusted device boundary).
  - ArangoDB is the only backend that might cross a network boundary (hence obfuscation).
- **Assumptions**:
  - Local storage (DuckDB, memory) does not require obfuscation.
  - Networked storage (ArangoDB) may need it, but the default is transparent.
- **Breaking Change**:
  - Removing obfuscation from ArangoDB would expose raw field names unless an external obfuscator is used.

---

### Declared Losses
- **Did not examine**:
  - The truncated portion of `arango.py` (lines beyond the first 109) — likely contains `query_range()` implementation.
  - The truncated portion of `duckdb.py` (lines beyond the first 56) — likely contains `Discovery` methods and cleanup.
  - Tests or benchmarks for the activity layer — would reveal performance characteristics under load.
  - Integration with the rest of the Yanantin project (e.g., how providers or tensors interact with this layer).
- **Why**:
  - The observed code is sufficient to understand the **design intent** and **contract** of the activity layer.
  - Truncated sections are likely boilerplate (e.g., SQL queries, cleanup methods) that do not alter the core patterns.

---

### Open Questions
1. **How are `content_hash` fields populated in `FactRecord`?**
   - The code defines the field but does not show its usage. Is it computed by providers or the store?
2. **What is the performance impact of `deep_copy` in `InMemoryActivityStreamStore`?**
   - At scale, deep-copying every fact/anchor read/write may become a bottleneck.
3. **How does the project handle timezone-naive datetimes in practice?**
   - The validator rejects them, but what if providers accidentally send them?
4. **Is the late-binding behavior in `AnchorView.materialize()` intentional?**
   - It ensures freshness but may return different results for the same anchor over time.
5. **Why does `AnchorView` include both `facts` and `providers`?**
   - The `providers` tuple seems redundant with the keys of `facts`, unless some providers have no facts at the anchor’s timestamp.

---
### Closing
The `yanantin.activity` layer is a **well-engineered temporal substrate** for epistemic observability. Its design centers on:
- **Immutability as correctness** (facts, anchors).
- **Temporal precision** (O(log n) queries, UTC enforcement).
- **Minimalist write gates** (only persist when necessary).
- **Pluggable backends** (memory for tests, DuckDB/ArangoDB for production).

**Advice for modifications**:
1. **Do not break immutability** — it is the foundation of temporal correctness.
2. **Preserve UTC enforcement** — naive datetimes will silently corrupt queries.
3. **Keep late-binding behavior** — it ensures anchors reflect the current state of the world.
4. **Avoid adding dependencies** — the backend separation is intentional for usability.
5. **Test performance at scale** — especially for `deep_copy` in `InMemoryActivityStreamStore` and AQL/SQL query pushdown in other backends.

This layer is **mature and intentional** — changes should be additive, not subtractive. If you’re adding a new backend, follow the same patterns: thread safety, immutability enforcement, temporal indexing, and late binding.
```