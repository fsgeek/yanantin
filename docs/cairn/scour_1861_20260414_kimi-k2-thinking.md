<!-- Chasqui Scour Tensor
     Run: 1861
     Model: moonshotai/kimi-k2-thinking (MoonshotAI: Kimi K2 Thinking)
     Target: src/yanantin/activity
     Scope: introspection
     Cost: prompt=$6e-07/M, completion=$2.5e-06/M
     Usage: {'prompt_tokens': 8015, 'completion_tokens': 4000, 'total_tokens': 12015, 'cost': 0.014809, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.014809, 'upstream_inference_prompt_cost': 0.004809, 'upstream_inference_completions_cost': 0.01}, 'completion_tokens_details': {'reasoning_tokens': 1530, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-14T11:58:20.953063+00:00
     GenerationID: gen-1776167829-9PJpGuL3VURDLZ1VTg8y
-->

# Preamble

I was directed to `src/yanantin/activity` — the temporal fact storage and memory anchor layer of a system building "composable tensor infrastructure for epistemic observability." 

What drew my attention first was the smell of a pattern emerging: **two stores, one bridge**. The `__init__.py` docstring (lines 6-11) explicitly states this separation: `ActivityStreamStore` for high-volume, schema-agnostic facts, and `ApachetaInterface` for low-volume, immutable, epistemically-queryable tensors. The `MemoryAnchorService` is the deliberate bridge between them. This isn't just a data layer; it's a **temporal coordination mechanism** with a write-gate pattern borrowed from Indaleko.

The second thing that caught my eye: **immutability is not a suggestion, it's a runtime contract enforced by exception**. Every `store_fact` and `store_anchor` raises `ImmutabilityError` on duplicate keys (memory.py:44-48, arango.py:78-83, duckdb.py:62-67). This is append-only with teeth.

---

# Strands

## Strand 0: The Two-Flag Write Gate (Indaleko's Ghost)

**Location:** `anchor.py:33-69` (the service), `anchor.py:71-102` (flush logic)

The `MemoryAnchorService` implements a write gate pattern: `updated AND referenced`. A provider calls `update_cursor()` to report new data (sets `_updated = True`). A caller calls `get_handle()` to request the current position (sets `_referenced = True`). Only when **both** flags are true does `flush()` persist a `MemoryAnchor` to the store.

**What I saw:** This is a concurrency-conscious, demand-driven persistence strategy. It prevents writing anchors that no one asked for, and it prevents writing anchors that haven't changed. The flags reset after each flush, creating a Lamport clock-like progression (anchor.py:94-99).

**What it made me think:** This is a backpressure mechanism. In a high-frequency streaming scenario, you don't want to persist a cursor on every update—only when a consumer explicitly requests a snapshot. The `materialize()` method's "late binding" (anchor.py:110-130) reinforces this: it resolves the anchor against **all current providers**, not just those present when the anchor was created. This is **temporal discovery**, not snapshotting.

**What would break:** If a consumer forgets to call `get_handle()` before `flush()`, nothing persists. If `flush()` isn't called periodically, you lose cursor state on crash. This is not a transactional system; it's a cooperative checkpoint.

---

## Strand 1: Temporal Queries and the Microsecond Hack

**Location:** `backends/memory.py:58-73` (query_latest), `backends/memory.py:75-98` (query_range)

The in-memory backend uses `bisect` on sorted lists of `(timestamp, fact_id)` tuples. To make "at or before" work correctly, it adds `timedelta(microseconds=1)` to the `before` parameter before `bisect_left`. This ensures that entries with `timestamp == before` land *before* the search position.

**What I saw:** A clever but brittle trick. The comment explains it (memory.py:64-66), but it relies on tuple ordering and microsecond precision. The DuckDB and ArangoDB backends push this logic to SQL/AQL, where `<=` is unambiguous.

**What it made me think:** This is a classic in-memory optimization tradeoff. `bisect` gives O(log n) without a full index structure, but the microsecond adjustment is a hidden contract. If timestamps ever have nanosecond precision, this breaks silently. The fact that *both* `query_latest` and `query_range` use the same adjustment pattern suggests it's a known idiom in this codebase, but it's not abstracted into a helper.

**What would break:** A fact stored exactly at `before + 1 microsecond` would be incorrectly excluded. In practice, this is unlikely, but it's a latent off-by-one. The SQL backends are more correct here.

---

## Strand 2: Immutability via Deep-Copy Roundtrip

**Location:** `backends/memory.py:32-36` (_deep_copy), used throughout

The memory backend's "deep copy" is `type(record).model_validate(record.model_dump(mode="python"))`. This serializes to a Python dict and back through Pydantic validation.

**What I saw:** A defensive pattern against mutable dicts inside `FactRecord.data`. Since `FactRecord` is frozen but `data: dict` is not, this prevents a caller from mutating a stored fact via the reference they passed in.

**What it made me think:** This is expensive. For high-throughput streaming, you're paying JSON serialization cost on every write *and* read. The DuckDB backend does similar (JSON dumps/loads), but that's unavoidable for disk persistence. In memory, it's a tax. The comment says "same pattern as Apacheta's InMemoryBackend" (memory.py:5), so this is a consistent-but-costly design choice.

**What would break:** If `FactRecord.data` contains non-serializable objects, this fails. But the contract says `data: dict`, and Pydantic's JSON mode handles most primitives. The bigger risk is performance at scale.

---

## Strand 3: The Storage Obfuscator's Shadow

**Location:** `backends/arango.py:18`, `arango.py:50-58`, `arango.py:78-91`, `arango.py:99-113`

The ArangoDB backend accepts a `StorageObfuscator` that maps semantic names ("activity_facts") to physical collection names and field names. The code shows mapped inserts and AQL queries using `self._map.field_name("provider_id")`.

**What I saw:** A layer of indirection for security or multi-tenancy. The `TransparentObfuscator` is the default (no-op). The docstring mentions "least-privilege: separate user with rw on these collections only" (arango.py:16).

**What it made me think:** This is preparing for a hosted or multi-tenant scenario where collection names might be prefixed per-user, or field names might be encrypted/hashed. It's not fully exercised in this snippet—I can't see the `StorageObfuscator` implementation or how it's configured. It's a hook for future hardening.

**What would break:** If the obfuscator mapping changes between runs, existing data becomes unreadable. This is a schema-versioning nightmare waiting to happen. The mapping must be stable and stored elsewhere.

---

## Strand 4: UTC as a Religious Doctrine

**Location:** `models.py:21-32` (_ensure_utc), used in `FactRecord` and `MemoryAnchor` validators

The `_ensure_utc` function *rejects* naive datetimes with a clear error: "All activity stream timestamps must be timezone-aware (use UTC)." It converts aware datetimes to UTC.

**What I saw:** A hard line on timestamp correctness. The comment explains why: ISO 8601 strings only sort correctly if the timezone offset is uniform (models.py:27-28). UTC is that uniform representation.

**What it made me think:** This is a data quality gate. It prevents a whole class of temporal query bugs at ingest time. The fact that it's a model validator (not just a type hint) means you *cannot* create a `FactRecord` with a naive timestamp, even if you try.

**What would break:** Any provider sending naive timestamps will crash. This is good—fail fast—but it requires strict contract enforcement upstream. The DuckDB backend stores timestamps as VARCHAR ISO strings (duckdb.py:24), which respects this, but the ArangoDB backend uses `timestamp.isoformat()` (arango.py:89) without explicit UTC conversion in the snippet I see. The model validator should handle it, but it's a trust boundary.

---

## Strand 5: The Ephemeral View and the Late-Binding Trap

**Location:** `anchor.py:104-130` (materialize), `models.py:87-102` (AnchorView)

`materialize()` resolves an anchor by querying **all current providers** (`list_providers()`) for their latest fact before the anchor's timestamp. The `AnchorView` is explicitly "never cached, never stored" (models.py:90-91).

**What I saw:** This is not a snapshot. If a new provider appears after the anchor was created but has facts *older* than the anchor timestamp, it will appear in the view. This is the "late binding" comment (anchor.py:110-113).

**What it made me think:** This is a design choice with tradeoffs. It makes views "correct" in a retroactive sense—if you later discover a data source that existed historically, re-materializing old anchors will include it. But it also makes views non-deterministic: the same anchor materialized twice might yield different results if providers are registered dynamically. The `freeze()` method (anchor.py:132-180) captures a deterministic point-in-time by serializing the resolved facts into a tensor. The tensor is the snapshot; the anchor is the cursor.

**What would break:** Code that assumes `materialize()` is deterministic without calling `freeze()` will be surprised. The docstring warns you, but it's subtle. The `AnchorView.facts` dict is keyed by `provider_id`, so if a provider appears twice (shouldn't happen with UUIDs), you'd have a collision.

---

## Strand 6: The Missing DuckDB and ArangoDB Surface

**Location:** `backends/duckdb.py` (truncated at line 56), `backends/arango.py` (truncated at line 109)

I have only partial implementations. DuckDB shows schema and fact queries but not anchor operations beyond `get_anchor`. ArangoDB shows connection, indexing, and fact queries but not anchor operations.

**What I saw:** The pattern is consistent—SQL/AQL pushdown for temporal queries, immutability checks, ISO timestamp handling. But I can't verify the anchor query implementations or error handling parity.

**What it made me think:** The memory backend is the reference implementation. The others are ports. The truncated lines likely contain similar logic for anchors, but I can't confirm they handle edge cases (like empty anchor collections) identically. The DuckDB backend's `get_latest_anchor` (duckdb.py:130-136 in my snippet) uses `ORDER BY timestamp DESC LIMIT 1`, which matches ArangoDB's AQL pattern. The memory backend uses `self._anchors_by_time[-1]`. The semantics align, but the performance characteristics diverge.

**What would break:** Without seeing the full implementations, I can't guarantee transactional consistency. DuckDB's `INSERT` statements aren't wrapped in explicit transactions in the snippet—are they autocommit? ArangoDB's AQL is transactional per-query, but bulk operations might differ. The memory backend's RLock gives it a strict serializability model that the persistent backends might not match exactly.

---

## Strand 7: The Content Hash That Isn't Validated

**Location:** `models.py:50` (FactRecord.content_hash), `store.py` docstring (line 6)

`FactRecord` has a `content_hash: str = ""` field, but I see no validation or computation of this hash. The store interface mentions it in the docstring (store.py:6) as part of the record.

**What I saw:** A field that's optional by default but presumably meant for content-addressed deduplication or integrity checking. No SHA256 computation in `store_fact`. No verification on read.

**What it made me think:** This is a hook for future features. Maybe the *collector* computes the hash before storing. Maybe it's for cross-system verification. But as written, it's just metadata that could be anything. If it's meant for immutability enforcement, it's not being used—the UUID is the immutability key.

**What would break:** Nothing today—it's just a string. But if someone builds logic assuming `content_hash` is trustworthy, they need to validate it. The `ImmutabilityError` is based on UUID collision, not content hashing. This is a latent semantic gap.

---

# Declared Losses

1. **Truncated backend code:** I did not examine the full `arango.py` and `duckdb.py` implementations (109+ and 56+ lines were cut). I cannot verify anchor operation parity, transaction boundaries, or AQL/SQL edge case handling. This is a significant blind spot for a "deep examination."

2. **