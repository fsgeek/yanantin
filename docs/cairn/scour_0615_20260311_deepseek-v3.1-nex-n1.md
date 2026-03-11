<!-- Chasqui Scour Tensor
     Run: 615
     Model: nex-agi/deepseek-v3.1-nex-n1 (Nex AGI: DeepSeek V3.1 Nex N1)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$2.7e-07/M, completion=$1e-06/M
     Usage: {'prompt_tokens': 7411, 'completion_tokens': 6032, 'total_tokens': 13443, 'cost': 0.00803297, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00803297, 'upstream_inference_prompt_cost': 0.00200097, 'upstream_inference_completions_cost': 0.006032}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-11T03:10:23.018922+00:00
-->

### Preamble

I was pointed at `src/yanantin/apacheta` — the “tensor database” sub‑package of Yanantin. The first thing that drew my attention was the metaphor: *Apacheta* (“cairn”), where each traveler adds a stone. That motif is carried through multiple modules (`content_address.py`, `rummage.py`, `operators/`, `models/`) and suggests a system designed around accumulation, immutability, and content‑based identity rather than mutation.

Within that, three elements stood out immediately:

- The `StorageObfuscator` protocol in `storage_obfuscator.py` — a clear architectural boundary between “device” and “fortress (Pukara)”.
- The `ApachetaInterface` in `interface/abstract.py` (visible via imports and `InMemoryBackend`’s implementation) — the central abstraction for all tensor DB operations.
- The `InMemoryBackend` in `backends/memory.py`, which makes the interface semantics concrete and gives a clear picture of what kinds of records exist: tensors, composition edges, corrections, dissents, negations, bootstraps, schema evolutions, entities.

Because the assignment explicitly limits me to the `apacheta` subtree and I only see partial contents (many files are truncated), I’ll focus on what is visible and clearly inferable, and I’ll be explicit about where I’m extrapolating vs. reading directly.

---

## Strands

### Strand 1 — Immutable, content‑addressed knowledge cairn

**What I saw**

- `apacheta/__init__.py` exposes only:
  ```python
  __all__ = ["StorageObfuscator", "TransparentObfuscator"]
  ```
  This reinforces that `StorageObfuscator` is the main contract the outside world should care about at the package boundary.

- `content_address.py`:
  - Defines `content_hash(text: str) -> str`, a normalized SHA‑256 hash (prefix length 16) used as a content identity.
  - Normalization includes:
    - Line‑ending normalization (`\r\n`, `\r` → `\n`).
    - Stripping trailing whitespace per line.
    - Collapsing runs of blank lines into a single blank line.
    - Stripping leading/trailing blank lines.

  - Provides `ContentIndex`:
    - Maps content hashes to lists of paths and paths to hashes.
    - `from_directory()` scans a directory tree for `.md` files and registers them.
    - `duplicates()` returns only hashes that appear at more than one path.
    - `has_content()`, `lookup()`, `hash_for_path()` complete the query surface.

  - Offers `deduplicate_report()` and a `_check_file()` path for checking if a file’s content already exists in the cairn.

- `backends/memory.py`:
  - `InMemoryBackend.store_tensor()` explicitly checks:
    ```python
    if tensor.id in self._tensors:
        raise ImmutabilityError(
            f"Tensor {tensor.id} already exists. "
            "Tensors are immutable — compose, don't overwrite."
        )
    ```
  - Similar immutability checks exist for `CompositionEdge`, `CorrectionRecord`, `DissentRecord`, `NegationRecord`, `BootstrapRecord`, `SchemaEvolutionRecord`, `EntityResolution`.

**What it made me think**

This is clearly a write‑once, read‑many system. The central design idea is:

- Knowledge units (tensors, edges, corrections, etc.) are immutable once stored.
- If you want to “change” something, you don’t edit; you *add* a new record that references or contradicts the old one (composition, correction, dissent).
- Content addressing in `content_address.py` is about *documents* in a `docs/cairn/` directory, but the same philosophy (identity = content hash, duplicates are structural noise) mirrors the DB’s immutability.

This design strongly supports auditability and provenance: every piece of knowledge can be traced, and nothing disappears. It fits the Yanantin goal of “epistemic observability” — you can see not just what is believed now, but how it evolved.

**Assumptions and risks**

- **Assumption**: UUIDs for records are sufficiently unique and stable. If UUID generation were buggy or non‑deterministic, you could get accidental duplicates or, worse, accidental *non*-duplicates for logically identical content.
- **Assumption**: Immutability is enforced only at the backend layer (`InMemoryBackend`). If someone bypasses `ApachetaInterface` and writes directly to a backend’s internal structures, immutability is void.
- **Risk**: The content hash normalization in `content_hash()` is subtle. Changes to normalization (e.g., ignoring more whitespace, Unicode normalization) would change identity. That’s a schema evolution event and should be tracked explicitly.

**Connections**

- The cairn directory scanned by `ContentIndex` presumably holds the human‑readable artifacts (scout reports, scour documents, etc.) that the tensor DB models formally. The DB and the filesystem are dual representations of the same knowledge.
- `rummage.py` (not fully shown) likely uses this content addressing to search/filter documents in the cairn.

---

### Strand 2 — Operator‑centric workflow over an abstract interface

**What I saw**

- `interface/__init__.py` exports:
  ```python
  __all__ = [
      "AccessDeniedError",
      "ApachetaError",
      "ApachetaInterface",
      "ImmutabilityError",
      "InterfaceVersionError",
      "NotFoundError",
  ]
  ```
  This tells us the public API to the tensor DB is the abstract interface plus a small set of errors.

- Operators modules:
  - `operators/bootstrap.py`:
    - `bootstrap(interface: ApachetaInterface, instance_id: str, context_budget: float, ...)`
      → returns `(BootstrapRecord, list[TensorRecord])`.
    - Stores the bootstrap via `interface.store_bootstrap(record)`.
    - If `tensor_ids` is `None`, it selects all available tensors via `interface.list_tensors()`.

  - `operators/negate.py`:
    - `negate(interface: ApachetaInterface, tensor_a, tensor_b, reasoning, ...)`
      → returns `NegationRecord`.
    - Stores a `NegationRecord` and a `CompositionEdge` with `RelationType.DOES_NOT_COMPOSE_WITH`.

  - `operators/evolve.py`:
    - `evolve(interface: ApachetaInterface, from_version, to_version, fields_added, fields_removed, migration_notes, ...)`
      → returns `SchemaEvolutionRecord`.
    - Stores via `interface.store_evolution(record)`.

- `backends/memory.py`:
  - `InMemoryBackend` implements `ApachetaInterface` and provides concrete storage for:
    - `_tensors`, `_edges`, `_corrections`, `_dissents`, `_negations`, `_bootstraps`, `_evolutions`, `_entities`.
  - Read methods like `get_tensor`, `get_strand`, `list_tensors`, `query_tensors_for_budget`, `query_operational_principles`, `query_project_state`.

**What it made me think**

The architecture separates three concerns:

1. **Interface (contract)**: `ApachetaInterface` defines what you can do with the tensor DB.
2. **Backend (implementation)**: `InMemoryBackend` (and presumably `duckdb.py`, `arango.py`) implement storage and access control.
3. **Operators (workflows)**: `bootstrap`, `negate`, `evolve` (and likely `compose`, `correct`, `dissent`, `project`) encode standard operations that:
   - Take an `ApachetaInterface`,
   - Do some logic,
   - Store new records,
   - Return the records they created.

This is a clean pattern: new behaviors can be added as operators without touching the backend, as long as the interface supports the required reads/writes.

**Assumptions and risks**

- **Assumption**: All interesting workflows can be expressed as sequences of operator calls over the abstract interface. If a workflow needs a backend‑specific feature (e.g., a fancy ArangoDB graph query), it either:
  - Must be exposed generically in `ApachetaInterface`, or
  - Must be avoided in favor of more generic operators.
- **Assumption**: Operators are stateless relative to the backend. They receive everything via the interface and function arguments. No hidden global state is assumed.
- **Risk**: `bootstrap`’s current logic is extremely simple (select all tensors if none specified). In a real system with budget constraints, this will need to become a real selection algorithm; the interface’s `query_tensors_for_budget(budget)` is clearly designed for that future.

**Connections**

- `operators/compose.py`, `correct.py`, `dissent.py`, `project.py` (not fully shown) likely follow the same pattern: accept `ApachetaInterface`, perform some reasoning over tensors, store new records.
- `clients/gateway.py` (not shown) probably exposes these operators over some transport (HTTP/gRPC) to remote clients.

---

### Strand 3 — Epistemic metadata and composition relations

**What I saw**

- `models/__init__.py` exports, among others:
  - `DeclaredLoss`, `DisagreementType`, `EpistemicMetadata`, `LossCategory`, `RepresentationType`
  - `KeyClaim`, `StrandRecord`, `TensorRecord`
  - `BootstrapRecord`, `CompositionEdge`, `CorrectionRecord`, `DissentRecord`, `NegationRecord`, `RelationType`, `SchemaEvolutionRecord`
  - `EntityResolution`

- `backends/memory.py`:
  - `get_strand(tensor_id, strand_index)` returns a `TensorRecord` that is a *projection* containing only the requested strand:
    ```python
    return TensorRecord(
        id=tensor.id,
        provenance=tensor.provenance,
        preamble=tensor.preamble,
        strands=matching,
        ...
    )
    ```
    The comment stresses:
    > The returned TensorRecord shares the source tensor's UUID — it is a view, not a new entity. … Storing the result would raise ImmutabilityError (duplicate UUID), which is the correct guard.

  - `query_operational_principles()` scans all tensors’ strands’ key claims and returns them as strings.

- `operators/negate.py`:
  - Creates both a `NegationRecord` and a `CompositionEdge` with `RelationType.DOES_NOT_COMPOSE_WITH`.

**What it made me think**

The data model is deeply epistemic:

- A `TensorRecord` is not just a bag of text; it has:
  - `provenance` (source, model, timestamps, etc. — from `ProvenanceEnvelope`),
  - `strands` (each with `key_claims`),
  - `epistemic` metadata (confidence, representation type, etc.),
  - `declared_losses` (what was omitted or abstracted away),
  - `open_questions`,
  - `lineage_tags`, `composition_equation`, etc.

- Relations like `CompositionEdge` and `NegationRecord` let the system express how tensors relate:
  - Some relations are positive (composes‑with, evolves‑from),
  - Others are negative (does‑not‑compose‑with).

- Returning a `TensorRecord` for a single strand but with the original UUID is a clever way to keep provenance while allowing fine‑grained access. The immutability check then prevents you from accidentally storing this projection as if it were a new tensor.

**Assumptions and risks**

- **Assumption**: Every tensor has a relatively small number of strands, and each strand has a manageable number of key claims. If a single tensor had thousands of strands, `get_strand` would still return a `TensorRecord` with the same UUID; that’s fine semantically but could be inefficient if callers aren’t careful.
- **Assumption**: `EpistemicMetadata`, `DeclaredLoss`, `open_questions` are populated honestly by the code creating tensors. The DB doesn’t enforce “epistemic honesty”; it only records what it’s told.
- **Risk**: `query_operational_principles()` returns raw claim strings without any context (which tensor, which strand, what epistemic metadata). In a real system, you’d want structured results that retain provenance.

**Connections**

- `ingest/markdown_parser.py` and `tensor_ballot.py` (not shown) likely turn markdown documents into `TensorRecord`s with structured strands and claims.
- `renderer/markdown.py` probably goes the other way: from `TensorRecord` to human‑readable markdown.
- `models/epistemics.py` and `models/provenance.py` (not shown) define the detailed structure behind `EpistemicMetadata`, `ProvenanceEnvelope`, etc.

---

### Strand 4 — Storage obfuscation and the fortress/device boundary

**What I saw**

- `storage_obfuscator.py`:
  - Defines `StorageObfuscator(Protocol)`:
    - `collection_name(semantic: str) -> str`
    - `field_name(semantic: str) -> str`
    - `reverse_field(opaque: str) -> str`
    - `obfuscate_document(doc: dict) -> dict`
    - `deobfuscate_document(doc: dict) -> dict`
    - `is_transparent: bool` property.

  - Provides `TransparentObfuscator`, which:
    - Returns inputs unchanged for all methods.
    - `is_transparent = True`.

  - Comments emphasize:
    - “Backends accept this protocol. The fortress (Pukara) provides the real implementation. Devices use the transparent default.”
    - “Dependency inversion: yanantin defines the contract, Pukara implements it. The backend never imports SchemaMap — it accepts a StorageObfuscator.”

- `apacheta/__init__.py` only exports these obfuscation types, reinforcing that this is the main cross‑cutting concern exposed at this package’s top level.

**What it made me think**

This is a privacy/security abstraction:

- In a “device” environment (development, testing), `TransparentObfuscator` is used — no obfuscation, everything is stored as‑is.
- In a “fortress” environment (Pukara — presumably a hardened deployment), a real implementation of `StorageObfuscator`:
  - Maps semantic collection/field names to opaque names,
  - Obfuscates documents (e.g., encrypting or tokenizing sensitive fields),
  - Deobfuscates on reads.

The key architectural idea is **dependency inversion**: the backend depends only on the `StorageObfuscator` protocol, not on any specific Pukara schema or crypto implementation. Pukara injects its obfuscator into the backend.

**Assumptions and risks**

- **Assumption**: Obfuscation is stateless enough that `reverse_field(opaque)` and `deobfuscate_document` are pure functions of their inputs. If they require external state (e.g., a key server), the backend may need to be async or the obfuscator must hide latency carefully.
- **Assumption**: All backends (in‑memory, DuckDB, ArangoDB) uniformly use the injected obfuscator. If one backend bypasses it, the security model is broken.
- **Risk**: The protocol doesn’t specify error behavior. If obfuscation/deobfuscation fails (bad key, corrupted data), it’s unclear whether the backend should raise, log, or return a sentinel. This needs clear rules.

**Connections**

- `backends/duckdb.py` and `backends/arango.py` (not shown) almost certainly accept a `StorageObfuscator` in their constructors and use it when reading/writing collections and documents.
- The broader Yanantin project likely has a `pukara` package that implements a non‑transparent `StorageObfuscator` and handles key management.

---

### Strand 5 — External API clients as provenance sources

**What I saw**

- `clients/openrouter.py`:
  - `OpenRouterClient`:
    - Async httpx client for `https://openrouter.ai/api/v1`.
    - Requires `OPENROUTER_API_KEY` (env var or explicit arg).
    - `complete(model, messages, temperature, max_tokens, metadata)`:
      - Returns `OpenRouterResponse` with:
        - `id`, `model`, `content`, `usage`, `raw`, `timestamp`.
    - Also `list_models()` and async context manager support.

  - `complete(...)` helper for one‑shot completions:
    ```python
    async def complete(model, prompt, system=None, ...) -> str
    ```

- Comments note:
  - “Adds Apacheta‑specific provenance: every API call can be stored as a TensorRecord with full metadata about model, cost, and experiment context.”

**What it made me think**

This client is designed not just as a generic LLM caller, but as a *provenance source* for Apacheta:

- Each call to OpenRouter can be wrapped into a `TensorRecord` with:
  - `ProvenanceEnvelope` recording model, cost, timestamp, experiment metadata,
  - Strands/key claims derived from the response content,
  - Epistemic metadata reflecting that this is an external model’s output.

This fits the Yanantin goal of “epistemic observability”: the system can trace a conclusion back through the tensor DB to the exact API call and model that produced it.

**Assumptions and risks**

- **Assumption**: The caller of `OpenRouterClient` is responsible for turning responses into `TensorRecord`s. The client itself doesn’t depend on Apacheta models, which is good layering.
- **Assumption**: `metadata` passed to `complete()` is used for cost allocation and experiment tracking on the OpenRouter side, and also available to include in provenance.
- **Risk**: Error handling is basic: `httpx.HTTPStatusError` and `httpx.RequestError` are raised, but there’s no retry logic or backoff. For a robust system, callers will likely need to wrap this in a retry/fallback layer.

**Connections**

- `clients/gateway.py` (not shown) may expose OpenRouter (and other providers) behind a unified gateway that automatically records tensors for each call.
- The `ProvenanceEnvelope` type (from `models/provenance`) likely has fields for `author_model_family`, `cost`, `experiment_id`, etc., which `OpenRouterClient` helps populate.

---

### Strand 6 — In‑memory backend as specification and test fixture

**What I saw**

- `backends/memory.py`:
  - Implements `ApachetaInterface` with dicts and `threading.RLock`.
  - `_enforce_access(caller, operation, target)` and `check_access` (the latter not fully shown) indicate the interface has an access control hook.
  - Immutability checks on every `store_*` method.
  - `_deep_copy` via `model_dump(mode="python")` + `model_validate` ensures stored records are independent of caller‑held objects.

- Read methods:
  - `get_tensor`, `get_strand`, `get_entity`, `list_tensors`.
  - `query_tensors_for_budget(budget)` currently returns all tensors (no budget logic yet).
  - `query_operational_principles()` extracts claim strings from all tensors.
  - `query_project_state()` aggregates counts and lineage tags and model families.

**What it made me think**

The in‑memory backend is serving multiple roles:

1. **Executable specification** of `ApachetaInterface` semantics:
   - Shows what “immutability” means in practice.
   - Shows how strands are projected.
   - Shows what query operations are expected to do, even if the current implementation is naive.

2. **Test fixture**:
   - Unit tests for operators can spin up an `InMemoryBackend` without needing DuckDB/ArangoDB.
   - The deep‑copy behavior ensures tests are isolated.

3. **Reference for future backends**:
   - Any new backend (e.g., PostgreSQL, SQLite) must match this behavior, at least for the subset of operations it supports.

**Assumptions and risks**

- **Assumption**: The in‑memory backend is *not* used in production for anything that requires persistence. The comments are clear about this (“Not for production persistence — that's the persistent backend's job”).
- **Assumption**: All backends will implement full `ApachetaInterface`. If some backends only support a subset, operators must be written defensively or there must be a way to query backend capabilities.
- **Risk**: The naive implementations of `query_tensors_for_budget` and `query_operational_principles` set a baseline, but if production relies on them being performant or sophisticated, they’ll need significant work.

---

## Declared Losses

I chose not to examine several parts in detail because they were truncated or only indirectly visible, and I can’t infer their internals reliably:

1. **DuckDB and ArangoDB backends (`backends/duckdb.py`, `backends/arango.py`)**
   - I only see their existence in the directory listing.
   - I did not analyze how they use `StorageObfuscator`, handle transactions, or map Pydantic models to tables/collections.
   - Why: the assignment provides no content for these files, and guessing their implementation would be fabrication.

2. **Full `ApachetaInterface` abstract definition (`interface/abstract.py`)**
   - I inferred its methods from `InMemoryBackend` and operator signatures, but I did not see the actual abstract base class or method signatures.
   - I also did not see `interface/errors.py` beyond the names of the exceptions.
   - Why: these files are not included in the provided snippets. I prefer not to invent the exact method list or error hierarchy.

3. **Detailed epistemic and provenance models (`models/epistemics.py`, `models/provenance.py`, `models/base.py`, `models/composition.py`, `models/entities.py`, `models/tensor.py`)**
   - I only see the types they export via `models/__init__.py`.
   - I did not examine field‑level details (e.g., what exactly is inside `EpistemicMetadata`, how `ProvenanceEnvelope` tracks costs, or how `EntityResolution` represents entities).
   - Why: the content is truncated, and enumerating hypothetical fields would be speculation.

4. **Ingestion pipeline (`ingest/markdown_parser.py`, `ingest/tensor_ballot.py`)**
   - I know they exist and are labeled “markdown to TensorRecord,” but I did not analyze parsing logic, error handling, or how “tensor ballot” works.
   - Why: they are outside the scope of the provided text.

5. **Renderer and rummage (`renderer/markdown.py`, `rummage.py`, `config.py`)**
   - I did not look at how tensors are rendered back to markdown, how `rummage` searches the cairn, or how `config.py` structures Apacheta configuration.
   - Why: again, content not provided.

6. **Other operators (`operators/compose.py`, `correct.py`, `dissent.py`, `project.py`)**
   - I saw their names but not their implementations.
   - Why: not included in the snippets.

These losses mean my view of Apacheta is centered on:
- The in‑memory backend,
- A few representative operators,
- The storage obfuscation contract,
- The OpenRouter client,
- And the content addressing layer.

---

## Open Questions

1. **Interface completeness**
   - What is the full signature of `ApachetaInterface`? In particular, are there methods for:
     - Querying edges or negations?
     - Versioning or schema introspection?
     - Bulk operations or transactions?
   - Without the abstract definition, I can only infer from `InMemoryBackend`.

2. **Backend persistence semantics**
   - How do `duckdb.py` and `arango.py` handle durability, atomicity, and concurrency?
   - Do they support async operations? The interface from operators appears synchronous, but `OpenRouterClient` is async — how are these composed?

3. **Access control model**
   - `InMemoryBackend._enforce_access` and `check_access` suggest an access control hook, but I don’t see how it’s configured or what policies exist.
   - Is it purely internal (“system” only) or can external callers have identities?

4. **Epistemic metadata semantics**
   - What do `RepresentationType`, `LossCategory`, `DisagreementType` enumerate?
   - How is `DeclaredLoss` used in practice to track what information was omitted?

5. **Content addressing vs. tensor UUIDs**
   - How are content hashes from `content_address.py` related to tensor UUIDs?
   - Are markdown files in `docs/cairn/` mirrored as `TensorRecord`s with the same identity?

6. **Evolution and compatibility**
   - How is `SchemaEvolutionRecord` used? Is there a mechanism to replay or migrate data when the schema changes?
   - Does the system enforce that all records conform to the current schema, or can old records live with outdated fields?

7. **Operational principles extraction**
   - `query_operational_principles()` returns raw strings. Is there a plan to:
     - Deduplicate them?
     - Cluster or categorize them?
     - Preserve provenance (which tensor/strand/claim each came from)?

I can’t resolve these from the provided code alone; they require looking at the actual definitions and usage sites.

---

## Closing

My overall impression of `yanantin/apacheta` is that it’s a thoughtfully designed, metaphor‑driven tensor database layer with a strong emphasis on:

- **Immutability and composition**: You don’t edit knowledge; you add new layers (corrections, dissents, compositions).
- **Provenance and epistemic metadata**: Every tensor knows where it came from (model, time, experiment) and how confident or lossy it is.
- **Clear boundaries**:
  - Interface vs. backends,
  - Device vs. fortress via `StorageObfuscator`,
  - Operators vs. storage logic.

The architecture is ready for expansion: new backends, new operators, and richer epistemic annotations can be added without breaking the core model.

**If you’re about to modify this codebase, I’d emphasize:**

- Respect immutability: never modify stored records in place. If something is wrong, add a correction or a new version.
- Keep operators stateless and dependent only on `ApachetaInterface`. Avoid backend‑specific logic in operators.
- When changing hashing, schema, or obfuscation, think in terms of explicit evolution records and migration notes.
- Be cautious with `content_hash` normalization changes — they change identity.
- Remember that `InMemoryBackend` is a spec/test double, not a production store; don’t rely on its performance or persistence.

I’ve reported what I could clearly see and reason about. Where I lacked information (truncated files, unseen abstractions), I’ve flagged guesses as speculative and losses as declared rather than filling in the blanks.