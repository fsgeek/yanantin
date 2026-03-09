<!-- Chasqui Scour Tensor
     Run: 500
     Model: deepseek/deepseek-v3.1-terminus (DeepSeek: DeepSeek V3.1 Terminus)
     Target: src/yanantin/activity
     Scope: introspection
     Cost: prompt=$2.1e-07/M, completion=$7.9e-07/M
     Usage: {'prompt_tokens': 8466, 'completion_tokens': 1390, 'total_tokens': 9856, 'cost': 0.00367582, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00367582, 'upstream_inference_prompt_cost': 0.00228582, 'upstream_inference_completions_cost': 0.00139}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-09T00:36:24.567252+00:00
-->

### Preamble

I was pointed at `src/yanantin/activity` — the activity stream layer for temporal fact storage and memory anchors. What drew my attention first was the elegant separation of concerns: two stores (activity stream for high-volume facts, apacheta for authored tensors) bridged by a service that implements Indaleko's two-flag write gate pattern. The memory anchor service's "updated AND referenced" logic immediately stood out as a sophisticated coordination mechanism.

### Strands

**Strand 1: Immutability as Architectural Foundation**
- **Observation**: Every component enforces strict immutability. `store.py` declares "append-only, no update, no delete" as contract. `memory.py` raises `ImmutabilityError` on duplicate UUIDs. `models.py` uses `frozen=True` Pydantic config. Even the anchor service advances handles rather than modifying existing anchors.
- **Connections**: This mirrors Apacheta's tensor storage philosophy — both layers treat records as immutable events in an audit trail.
- **Assumptions**: That append-only semantics are sufficient for epistemic observability. Valid for audit trails but might complicate data correction scenarios.
- **Breakage**: Any attempt to implement update/delete would require fundamental contract changes across all backends.

**Strand 2: Temporal Query Optimization Patterns**
- **Observation**: All three backends implement identical temporal query semantics using different optimization strategies. `memory.py` uses `bisect` on sorted lists (lines 35-36), `duckdb.py` uses SQL indexes (lines 28-29), `arango.py` uses AQL with persistent sorted indexes (lines 40-58). All handle timestamp boundaries consistently with the "+1 microsecond" pattern for inclusive/exclusive ranges.
- **Connections**: This demonstrates the abstract interface's effectiveness — same contract, different performance characteristics.
- **Assumptions**: That temporal queries will primarily be "latest before timestamp" and "range queries." The composite index patterns suggest provider_id + timestamp is the primary access pattern.
- **Missing**: Query patterns for cross-provider temporal correlations aren't directly supported — you'd need to query each provider separately.

**Strand 3: Late Binding in Anchor Resolution**
- **Observation**: `anchor.py`'s `materialize()` method (lines 96-114) discovers ALL current providers at resolution time, not just those in the anchor's original cursor list. This means new providers registered after anchor creation can contribute facts to the view if they have historical data.
- **Connections**: This enables progressive enrichment of historical contexts — a powerful feature for evolving systems.
- **Assumptions**: That providers might be added after system initialization and should be able to contribute to historical analysis.
- **Breakage**: If late binding is undesirable (for reproducibility), this would need to be configurable.

**Strand 4: Storage Abstraction with Progressive Complexity**
- **Observation**: The backends form a progression: `memory.py` (simple dicts, tests) → `duckdb.py` (SQL, local persistence) → `arango.py` (document DB, production). Each handles the same interface with increasing sophistication (obfuscation, connection pooling, etc.).
- **Connections**: Follows Yanantin's composable infrastructure philosophy — start simple, scale as needed.
- **Assumptions**: That most users will start with in-memory/duckdb and graduate to ArangoDB. The dependency isolation in `backends/__init__.py` supports this.
- **Missing**: Migration paths between backends aren't addressed — data portability between storage engines.

**Strand 5: Timezone Enforcement as Data Integrity Measure**
- **Observation**: `models.py` contains strict timezone validation (lines 24-35) — naive datetimes are rejected because "ambiguous timestamps corrupt sort order in every backend." All timestamps are normalized to UTC.
- **Connections**: This is crucial for the temporal query correctness that the entire activity layer depends on.
- **Assumptions**: That UTC is the correct universal time representation. Valid assumption for technical systems.
- **Breakage**: Any relaxation of timezone requirements would break all temporal queries across all backends.

### Declared Losses

I chose not to deeply examine:
- The exact AQL query construction in `arango.py` beyond the pattern — the truncated lines (109+) contain additional query logic that follows the established patterns.
- The duckdb connection management and transaction semantics — while I noted the context manager pattern, I didn't analyze transaction boundaries or error recovery.
- The content hashing mechanism in `FactRecord` — it's present but not implemented in the storage backends beyond field storage.
- The `apacheta.interface` integration in the `freeze()` method — I noted the pattern but didn't trace through the tensor creation pipeline.

I ran out of attention for the exact obfuscation implementation in `arango.py` — while I noted its presence and purpose, the mapping mechanics deserve deeper analysis.

### Open Questions

1. **Data Evolution**: How does this system handle schema evolution of `FactRecord.data`? The store is schema-agnostic, but consumers must interpret the JSON. Is there versioning or content-type metadata?
2. **Anchor Pruning**: Is there a mechanism for pruning old anchors or facts, or is everything kept forever? The immutability suggests perpetual retention, but that has scaling implications.
3. **Concurrency Limits**: The RLock-based thread safety works for single-process scenarios. How does this extend to distributed scenarios? The ArangoDB backend suggests multi-process use, but the service itself isn't distributed.
4. **Error Recovery**: What happens if `flush()` fails after updating the internal state? The handle advances on successful persistence, but error handling isn't shown.

### Closing

This is exceptionally well-architected code. The separation of concerns is clear, the abstractions are leak-resistant, and the implementation shows thoughtful attention to both correctness and performance. The two-flag write gate pattern is particularly elegant for coordinating independent actors.

**To someone modifying this**: Respect the immutability contract — it's foundational. The temporal query patterns are carefully optimized across backends; changes to timestamp handling require cross-backend validation. The late-binding anchor resolution is a powerful feature but also a subtle behavior — document whether you're relying on or disabling it. Test across all three backends — the interface may be identical, but the performance characteristics are not.

I'm confident in my understanding of the core patterns but recognize the storage backends (particularly ArangoDB) have depth I didn't fully explore. The timezone enforcement and immutability constraints are non-negotiable architectural decisions.