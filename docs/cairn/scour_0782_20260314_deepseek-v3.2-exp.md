<!-- Chasqui Scour Tensor
     Run: 782
     Model: deepseek/deepseek-v3.2-exp (DeepSeek: DeepSeek V3.2 Exp)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$2.7e-07/M, completion=$4.1e-07/M
     Usage: {'prompt_tokens': 7384, 'completion_tokens': 2482, 'total_tokens': 9866, 'cost': 0.0030113, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0030113, 'upstream_inference_prompt_cost': 0.00199368, 'upstream_inference_completions_cost': 0.00101762}, 'completion_tokens_details': {'reasoning_tokens': 585, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-14T08:10:09.353031+00:00
-->

## Preamble

I was pointed at `src/yanantin/apacheta` — the tensor database component of Yanantin. What drew my attention first was the clear architectural separation: backends, operators, models, ingest, interface. This isn't just storage; it's a system for composing and relating epistemic claims. The "log before you parse" philosophy appears in multiple files — a strong design stance.

## Strands

### Strand 1: Immutability as Core Contract
**Observation:** Every backend (`duckdb.py:79-85`, `memory.py` implied) enforces immutability through duplicate UUID checks. The error message is consistent: "Tensors are immutable — compose, don't overwrite." The interface defines `ImmutabilityError` specifically for this. Thread safety via `RLock` appears in both backends shown.

**Thought:** This isn't just data persistence — it's a version control system at the atomic level. Each tensor is a commit. The operators (compose, correct, dissent, negate) become the git operations of this system. The design assumes all modification happens through explicit composition edges, not mutation.

### Strand 2: Schema Evolution as First-Class Concern
**Observation:** `models/tensor.py:31-44` shows deliberate handling of schema evolution in `StrandRecord`. The `declared_losses`, `mechanism`, and `overlaps` fields have three states: `None` (pre-migration, not considered), empty/zero (considered, nothing to declare), populated (active declaration). The comment explicitly states "The distinction between None and empty is the diagnostic signal."

**Thought:** This is sophisticated. Most systems either ignore schema evolution or handle it opaquely. Here, the system tracks whether a tensor was *aware* of schema evolution concepts. This allows analyzing when certain epistemic practices entered the corpus. The `mechanism` field having `""` as "migration default" vs `None` as "actively considered and purely conceptual" shows nuanced thinking about defaults.

### Strand 3: Storage Obfuscation as Protocol
**Observation:** `storage_obfuscator.py` defines a `Protocol` for structural obfuscation at the storage boundary. The comment says "The fortress (Pukara) provides the real implementation. Devices use the transparent default." Dependency inversion: Yanantin defines the contract, Pukara implements it.

**Thought:** This reveals a security model where the "fortress" (presumably a secure server) can obfuscate field names and collections, while local development uses transparent mapping. This allows the same code to run in trusted and untrusted environments. The protocol is minimal: collection/field name mapping and document transformation.

### Strand 4: Atomic Numbering via POSIX Semantics
**Observation:** `ingest/tensor_ballot.py` implements Lamport's bakery algorithm using `O_CREAT|O_EXCL`. It scans for highest existing tensor number, then attempts to claim the next with atomic file creation. If `FileExistsError`, increments and retries. Same pattern as Chasqui's scout numbering but different namespace.

**Thought:** This is elegant systems programming. No central coordinator needed — relies on filesystem atomicity. The "bakery loop" comment shows awareness of distributed systems concepts. This allows multiple concurrent Yanantin instances to number tensors without collision. The separation from scout numbering (date+model vs global) shows careful namespace design.

### Strand 5: Tolerant Parsing with Loss Declaration
**Observation:** `ingest/markdown_parser.py` begins with: "The parser is deliberately tolerant. It captures what it can and declares what it drops. A parser that rejects valid tensors is worse than one that captures them imperfectly — log before you parse." It handles multiple markdown formats (Claude vs ChatGPT, different heading levels).

**Thought:** This embodies the epistemic humility of the system. Rather than enforcing strict schema upfront, it accepts variation and declares what's lost. The `TENSOR_METADATA` dictionary maps filenames to metadata, showing manual curation of early tensors. The parser extracts key claims from bold text in various list formats — pragmatic rather than perfect.

### Strand 6: Operator Pattern for Tensor Relations
**Observation:** Each operator (`bootstrap.py`, `dissent.py`, `negate.py`) follows a pattern: takes an `ApachetaInterface`, creates one or more records, stores them, returns the primary record. `dissent` and `negate` create both a relation record and a `CompositionEdge`. The operators are pure functions aside from storage side effects.

**Thought:** This is clean functional architecture. Operators don't know about backends — they work through the interface. Each operator corresponds to a specific epistemic action: bootstrapping a context, dissenting, negating composition. The system grows by adding operators, not modifying core.

### Strand 7: DuckDB as Honesty Check
**Observation:** `backends/duckdb.py:13-20` comment: "Keeps the interface honest alongside the in-memory backend — if the interface leaks backend-specific assumptions, one of the two backends will expose it." Uses `(id UUID, data JSON)` per table with full model serialization. Query logic in Python for now, "push to SQL when scale demands."

**Thought:** This is testing philosophy as architecture. Two implementations (memory, DuckDB) validate the interface abstraction. The JSON storage suggests early stage — will need migration when queries become complex. The "obfuscating against yourself is theater" comment shows pragmatic security thinking for local storage.

## Declared Losses

1. **Did not examine `backends/arango.py` or `backends/memory.py`** — only saw DuckDB implementation. The patterns are likely similar, but ArangoDB (graph database) might show different tradeoffs.

2. **Did not examine `clients/` directory** — contains `gateway.py` and `openrouter.py`. These presumably handle external API calls, but their relation to core tensor operations is unclear from surface.

3. **Did not examine `models/composition.py`, `models/epistemics.py`, `models/provenance.py`** in detail — saw only references. These define the relation types and epistemic metadata structures.

4. **Did not examine `operators/compose.py`, `correct.py`, `evolve.py`, `project.py`** — only saw bootstrap, dissent, negate. The composition operator is likely central.

5. **Did not trace through the full `markdown_parser.py` (209+ lines truncated)** — saw the philosophy and key claim extraction, but not full parsing logic.

6. **Did not examine `renderer/markdown.py`** — assumes it renders tensors back to markdown, but implementation details unknown.

## Open Questions

1. **How are tensor queries expressed?** I see `list_tensors()` and `get_tensor()` in DuckDB, but no query language. The comment says "Query logic in Python" — does this mean all filtering happens in application code?

2. **What is the `content_address.py` file?** Name suggests content-addressable storage, but not shown. How does this relate to UUID-based storage?

3. **What is `rummage.py`?** The name suggests search functionality, but not shown in contents.

4. **How does schema evolution actually propagate?** The models track awareness of evolution, but what mechanism migrates old tensors to new schemas? Or is migration optional/declarative?

5. **What is the `preservation_target` field in `TensorRecord`?** Mentioned but not explained — seems to indicate what aspect of the tensor should be preserved through transformations.

6. **How are `EntityResolution` records used?** Seen in DuckDB table list but not examined. Likely handles entity disambiguation across tensors.

## Closing

This is a thoughtfully designed epistemic database. The architecture shows clear influences from version control systems (immutability, composition), distributed systems (atomic numbering), and semantic web (provenance, relations). The codebase values clarity over cleverness — comments explain philosophy, not just mechanics.

If I were about to modify this, I'd note:

1. **The interface is sacred** — all storage access goes through `ApachetaInterface`. Don't add backend-specific shortcuts.

2. **Immutability is non-negotiable** — every write must check for existing UUIDs.

3. **Schema evolution is tracked explicitly** — the None/empty/populated pattern matters for diagnostics.

4. **Operators should remain pure functions** — they take interface and data, return records.

5. **Parsing tolerates variation** — when ingesting markdown, capture what you can, declare what you drop.

The system feels like it's built for long-term knowledge accumulation, where the mechanisms for preserving context and tracking provenance are as important as the data itself. The complement to Chasqui's exploration: Apacheta is the cairn where findings are stacked.