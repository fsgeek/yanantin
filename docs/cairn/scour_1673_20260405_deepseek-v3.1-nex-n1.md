<!-- Chasqui Scour Tensor
     Run: 1673
     Model: nex-agi/deepseek-v3.1-nex-n1 (Nex AGI: DeepSeek V3.1 Nex N1)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$1.35e-07/M, completion=$5e-07/M
     Usage: {'prompt_tokens': 9370, 'completion_tokens': 5039, 'total_tokens': 14409, 'cost': 0.00378445, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00378445, 'upstream_inference_prompt_cost': 0.00126495, 'upstream_inference_completions_cost': 0.0025195}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-05T20:57:41.123421+00:00
     GenerationID: gen-1775422504-YmMzOrTSB3I1aPNhDpzx
-->

### Preamble

I was pointed at `src/yanantin/apacheta` — the core “tensor storage” layer of the Yanantin project — and told to introspect it as a chasqui (message-scourer).  

The first thing that drew attention was the name itself: “Apacheta” evokes a physical stone cairn marking a path in the Andes, and the codebase consistently talks about “immutable” records, “lineage,” “provenance,” and “config-as-tensors.” This framing — configuration and knowledge as immutable, versioned tensors — is the central motif of the directory.

I then noticed the very explicit separation of concerns:
- `models/` — pure schema (Pydantic v2 models),
- `interface/` — abstract protocol + errors,
- `backends/` — implementations (memory, DuckDB, Arango),
- `clients/` — HTTP gateway to a fortress (“Pukara”),
- `ingest/` — markdown parsing into tensor records,
- `operators/` — named operations like `correct`, `dissent`, `evolve`, `project`.

There is also a `config.py` that uses the tensor storage itself to store configuration, and a `storage_obfuscator.py` that defines a contract for structural obfuscation at the storage boundary.

Below is a structured “tensor” of what I see.

---

### Strands

#### Strand 1: Immutable, provenance-aware tensors as the universal data spine

**What I see**

- `models/tensor.py` (not fully visible, but used heavily) defines `TensorRecord`, `KeyClaim`, `StrandRecord`. `KeyClaim` carries epistemic metadata (`truth`, `indeterminacy`).
- `models/provenance.py` defines `ProvenanceEnvelope` with fields like:
  - `source`
  - `timestamp`
  - `author_model_family`
  - `author_instance_id`
  - `context_budget_at_write`
  - `predecessors_in_scope`
  - `interface_version`
- The base class `ApachetaBaseModel` is used everywhere (`models/base.py`), implying an immutable-by-default stance.
- `config.py` treats configuration itself as a tensor:
  - `ConfigTensor` is stored as a `TensorRecord` with `lineage_tags = ("config", config_domain)`.
  - `previous_config_id` points to the predecessor config; `reasoning` explains why it changed.
- `interface/errors.py` includes `ImmutabilityError` with a message: “Tensors are immutable — compose, don't overwrite.”
- The `DuckDBBackend` enforces this:
  - `store_tensor()` calls `_store()`, which checks `_exists()` and raises `ImmutabilityError` if a UUID is already present.

**What this makes me think**

The project is designed around a single invariant: *knowledge is never mutated; it is only composed and revised*. Every piece of data — including configuration — is a versioned artifact with provenance. This is very close to content-addressable, versioned knowledge graphs (git-for-data meets epistemic graphs).

The `ProvenanceEnvelope` is particularly interesting: it records not just what model generated the tensor, but also context budget at write time. This is clearly aimed at epistemic observability — you want to later reason about why a model might have been overconfident or underconfident.

Configuration is not special-cased; it is just another domain of knowledge stored in the same tensor format. This is a strong design choice: it means config evolution is observable and auditable in the same way as other knowledge.

**Questions / risks**

- How does the system handle garbage collection? If everything is immutable and never deleted, storage grows indefinitely. This is not addressed in the snippets I see.
- There is tension between “everything is a tensor” and pragmatic performance. If config reads always require reconstructing `ConfigTensor` from `TensorRecord` by parsing key claims, that is more overhead than a simple key-value store.

---

#### Strand 2: Explicit interface-first design with multiple backends and a remote gateway

**What I see**

- `interface/abstract.py` defines `ApachetaInterface` (protocol). Not all methods are visible here, but `DuckDBBackend` and `ApachetaGatewayClient` implement the same set:
  - `store_tensor`, `get_tensor`, `get_tensor_by_claim`, `query_reading_order`, ...
  - `store_composition_edge`, `store_correction`, `store_dissent`, `store_negation`, `store_bootstrap`, `store_evolution`, `store_entity`
  - `get_*` variants for each of these
  - `check_access` and `get_interface_version`
- `backends/memory.py` and `backends/duckdb.py` are local backends:
  - `DuckDBBackend` stores `(id, data JSON)` per table and uses Python-side logic for querying.
  - It explicitly notes: “DuckDB is local storage on a trusted device. No obfuscation needed.”
- `clients/gateway.py` implements `ApachetaInterface` over HTTP:
  - `ApachetaGatewayClient` maps each interface method to a `/api/v1/...` endpoint.
  - `_handle_error()` converts HTTP codes to `ImmutabilityError`, `NotFoundError`, `AccessDeniedError`, `InterfaceVersionError`, `ApachetaError`.
- `interface/errors.py` centralizes error classes used by both backends and client.

**What this makes me think**

The architecture is deliberately interface-first: core logic should depend only on `ApachetaInterface`, not on concrete storage. This enables:
- Local development/testing using memory or DuckDB,
- Production devices talking to a “fortress” (`Pukara`) over HTTP,
- Easy swapping of backends for testing or scaling.

The `ApachetaGatewayClient` is “thin”: it’s just a translation layer between Pydantic models and JSON-over-HTTP. The heavy lifting is on the server (`Pukara`).

Having both backends and the client implement the same interface is a strong design: if you accidentally leak backend-specific assumptions into higher-level code, the mismatch will show up quickly when you try to use the other backend or the client.

**Questions / risks**

- The DuckDB backend says “query logic in Python (same as in-memory) — push to SQL when scale demands.” If query volume grows, this becomes a bottleneck. The design is honest about this being a temporary choice.
- Error handling in the gateway client assumes `response.json()` exists and contains `{"detail": "..."}`. That is fine if the server is FastAPI/Pydantic, but it is a tight coupling to that style of API.

---

#### Strand 3: Composition, dissent, negation, and evolution as first-class concepts

**What I see**

- `models/composition.py` defines a rich set of composition models:
  - `CompositionEdge` with `from_tensor`, `to_tensor`, `relation_type` of `RelationType` enum:
    - `COMPOSES_WITH`, `CORRECTS`, `REFINES`, `BRIDGES`, `BRANCHES_FROM`, `DOES_NOT_COMPOSE_WITH`, `DISSENTS_FROM`, `CONFIRMS`, `DENIES`, `DEPENDS_ON`
  - `CorrectionRecord` for correcting a specific claim in a strand.
  - `DissentRecord` for formal disagreement with a tensor or claim, including an alternative framework.
  - `NegationRecord` to declare that two tensors do not compose.
  - `BootstrapRecord` to track what tensors an instance loaded at startup.
  - `SchemaEvolutionRecord` to track schema changes.
- The `ApachetaInterface` has explicit methods:
  - `store_composition_edge`, `store_correction`, `store_dissent`, `store_negation`, `store_bootstrap`, `store_evolution`.
- `operators/` has modules like:
  - `correct.py`, `dissent.py`, `negate.py`, `evolve.py`, `project.py`, `compose.py`, `bootstrap.py`.

**What this makes me think**

The project is not just storing “documents”; it is storing *reasoned relationships* between them. The system is explicitly designed to support disagreement, correction, and composition. This is epistemic infrastructure in a strong sense: it knows about “alternative frameworks,” “dissent,” and “negation.”

The `BootstrapRecord` is particularly interesting: it records what context an instance chose to load into its context window at startup, and what was omitted. This is meta-epistemic: it allows you later to reason about whether the system had the right prior context.

`SchemaEvolutionRecord` shows that even schema changes are recorded as tensors, which is a powerful way to track and possibly migrate data over time.

**Questions / risks**

- I do not see how these records are used in querying or rendering. Are there higher-level operators that walk the graph of `CompositionEdge` or `DissentRecord`? The snippets show storage but not usage.
- The semantics of `relation_type` are rich but potentially ambiguous. For example, `CORRECTS` vs `REFINES` vs `BRANCHES_FROM`: the distinctions are subtle and might be interpreted differently by different agents.

---

#### Strand 4: Config-as-tensors and the bootstrap problem

**What I see**

- `config.py`:
  - `DEFAULT_CONFIGS` provides file-based defaults for domains like `"chasqui.pulse"` and `"pichay.policy"`.
  - `ConfigTensor`:
    - `config_domain: str`
    - `settings: dict[str, Any]`
    - `reasoning: str`
    - `previous_config_id: UUID | None`
    - `provenance: ProvenanceEnvelope`
    - `timestamp: datetime`
  - `store_config(interface, config)`:
    - converts `ConfigTensor` to `TensorRecord` with lineage tags `("config", domain)`,
    - stores each setting as a `KeyClaim` text `"key = value_repr"`,
    - stores `reasoning` as `narrative_body`.
  - `get_current_config(interface, domain)`:
    - queries tensors by `lineage_tags` and `topics`,
    - uses `query_reading_order` to get tensors sorted by timestamp,
    - returns `None` if no config exists so that the caller falls back to `DEFAULT_CONFIGS`.
- The docstring explicitly acknowledges the bootstrap problem:
  - You need file-based defaults to reach the database,
  - Database configs override file defaults,
  - `get_current_config` returns `None` when no database is available.

**What this makes me think**

This is a very elegant solution to the “configuration bootstrap” problem: config is stored in the same system it configures, but you always have a fallback path. The separation between `DEFAULT_CONFIGS` and `ConfigTensor` mirrors the separation between “factory defaults” and “user settings.”

By storing config as tensors with reasoning and predecessors, you can track the history of policy decisions: why `min_scout_interval` changed from 300 to 600, for example.

**Questions / risks**

- There is a circular dependency risk: if the system that *reads* config depends on the storage layer being configured correctly, and storage layer configuration is itself stored in that storage layer, you must be careful about initialization order.
- `_tensor_to_config` reconstructs settings by parsing `key = value_repr` strings using `ast.literal_eval`. This is fragile: if a value contains `" = "` or is not a valid Python literal, the parsing might fail silently or incorrectly.

---

#### Strand 5: Storage obfuscation and the “fortress” pattern

**What I see**

- `storage_obfuscator.py` defines a `StorageObfuscator` protocol:
  - `collection_name(semantic) -> str`
  - `field_name(semantic) -> str`
  - `reverse_field(opaque) -> str`
  - `obfuscate_document(doc) -> doc`
  - `deobfuscate_document(doc) -> doc`
  - `is_transparent` property.
- `TransparentObfuscator`:
  - identity mappings everywhere,
  - `is_transparent = True`.
- The docstring says:
  - “Backends accept this protocol. The fortress (Pukara) provides the real implementation.”
  - “Dependency inversion: yanantin defines the contract, Pukara implements it.”
- `DuckDBBackend` explicitly says:
  - “DuckDB is local storage on a trusted device. No obfuscation needed — obfuscating against yourself is theater.”

**What this makes me think**

The project is designed for a world where devices may not fully trust their local storage, or where local storage might be compromised. The “fortress” (`Pukara`) can apply structural obfuscation (renaming collections and fields) so that even if someone dumps the database, they cannot trivially understand the schema without the obfuscator.

The design is careful to avoid circular dependency: the backend does not import `SchemaMap` from the fortress; instead, it accepts a `StorageObfuscator` protocol. This is dependency inversion done correctly.

**Questions / risks**

- The protocol is not yet used in the visible snippets of `DuckDBBackend` or `ApachetaGatewayClient`. The backends are currently written without passing an obfuscator instance. The design is prepared, but not yet fully wired.
- It is not clear how the obfuscator interacts with the HTTP gateway client. Does the client do obfuscation before sending, or does the fortress do it on the server side? The current `ApachetaGatewayClient` simply sends Pydantic models as JSON; there is no mention of obfuscation.

---

#### Strand 6: Ingestion from markdown — “cold start” for Apacheta

**What I see**

- `ingest/markdown_parser.py`:
  - `TENSOR_METADATA` maps filenames (e.g., `T0_20260207_bounded_verification.md`) to metadata:
    - `label`, `author_model_family`, `lineage_tags`, `date`.
  - The parser handles:
    - multiple strand formats (`## Strand N: Title`, `### Strand N: Title`, or plain `Strand N: Title`),
    - various ways of embedding key claims: bold text in lists, numbered lists, bullet points,
    - optional `Preamble`/`Closing` sections,
    - declared losses as a strand or section.
  - It constructs `TensorRecord` with:
    - `ProvenanceEnvelope` populated from the metadata and `author_model_family`,
    - `StrandRecord` for each strand,
    - `KeyClaim` objects with default epistemic metadata (`truth=0.5`, `indeterminacy=0.5`).
- The docstring emphasizes:
  - “The parser is deliberately tolerant. It captures what it can and declares what it drops.”

**What this makes me think**

This parser is the bridge from “human-authored conversation logs” to “machine-usable tensor records.” It is clearly built to handle historical artifacts from multiple models (Claude vs ChatGPT) and different conventions used in earlier experiments.

The tolerance is a good sign: instead of failing hard on malformed documents, it extracts what is possible and logs what is dropped. This aligns with the epistemic stance of the project: partial knowledge is better than none.

**Questions / risks**

- The default epistemic values (`truth=0.5`, `indeterminacy=0.5`) are placeholders. The parser does not attempt to infer confidence from the text. This is fine for cold start, but later tools might want to refine these values.
- There is no explicit schema versioning for the parsed tensors. If the parser evolves, it might produce tensors with different structure; downstream tools might need to handle multiple versions.

---

#### Strand 7: Epistemic metadata, entities, and the “observability” promise

**What I see**

- `models/__init__.py` re-exports:
  - `EpistemicMetadata`, `DeclaredLoss`, `DisagreementType`, `LossCategory`, `RepresentationType`.
- `models/epistemics.py` (not fully visible) defines these structures.
- `models/entities.py` defines `EntityResolution`.
- `TensorRecord` includes `epistemic_metadata` and `lineage_tags`.
- `KeyClaim` includes `epistemic` metadata.
- `ingest/markdown_parser.py` uses these epistemic types to annotate claims.

**What this makes me think**

The system is designed to track not just *what* is claimed but *how* confident the system is and what might be missing. `DeclaredLoss` and `LossCategory` suggest that the system can explicitly state “here is what I did not capture or understand.”

`EntityResolution` suggests that the system is aware of entities that might appear across multiple tensors and attempts to resolve them. This is important for building a coherent knowledge graph across many conversations and runs.

**Questions / risks**

- I do not see how `EntityResolution` is used in the snippets. The operators for entity resolution are not visible here. This might be an area that is designed but not yet implemented.

---

#### Strand 8: Operators and the `rummage` abstraction

**What I see**

- `operators/` includes:
  - `bootstrap.py`, `compose.py`, `correct.py`, `dissent.py`, `evolve.py`, `negate.py`, `project.py`.
- `rummage.py`:
  - The file is not fully visible, but the name suggests “searching through” the tensor store.
- `config.py` uses `query_reading_order` from the interface to retrieve tensors by tags and topics.

**What this makes me think**

The operators layer is likely where higher-level reasoning over tensors lives:
- `compose.py` probably builds new tensors from existing ones by following composition edges.
- `correct.py` and `dissent.py` likely create `CorrectionRecord` and `DissentRecord` and link them to the relevant tensors.
- `project.py` might implement “projections” of a tensor (summaries, views).
- `rummage.py` might provide higher-level querying, filtering, and traversal over the graph of tensors and edges.

**Questions / risks**

- Because the operator implementations are not visible, I cannot see how they use `CompositionEdge` or `DissentRecord`. This is the layer where bugs in logic would likely surface, but it is opaque from the snippets provided.

---

### Declared Losses

1. **Detailed operator implementations**  
   - I did not see the actual code in `operators/*.py` or `rummage.py`.  
   - As a result, I cannot say how composition edges are actually used to build new tensors, or how dissent is incorporated into reasoning.

2. **Full `models/tensor.py` and `models/epistemics.py`**  
   - I only saw fragments and usage sites of `TensorRecord`, `KeyClaim`, `EpistemicMetadata`, etc.  
   - I cannot comment on the full schema, such as whether there is a `confidence` field or how `RepresentationType` is used.

3. **Backend query logic in detail**  
   - While `DuckDBBackend` shows the structure, the actual query methods like `query_reading_order` are not fully visible.  
   - I cannot assess how efficiently queries are implemented or how indexing is handled.

4. **The `content_address.py` module**  
   - The name suggests content addressing or hashing, but I did not see its contents.  
   - This might be important for deduplication or integrity checks, but it is opaque to me.

5. **The `renderer/markdown.py`**  
   - The `renderer` directory exists, but I only saw `__init__.py` and the name `markdown.py`.  
   - I cannot see how tensors are rendered back into human-readable markdown, which is important for the user-facing side.

---

### Open Questions

1. **How is garbage collection or archival handled?**  
   - The design is fully immutable and never deletes records.  
   - Over time, this will lead to very large storage. How does the system decide what to keep online vs archive?

2. **What guarantees does `query_reading_order` provide?**  
   - The name suggests “reading order,” but the semantics are not fully visible.  
   - Does it always return tensors in chronological order? Is there a way to query by causal order (using `predecessors_in_scope`)?

3. **How is the `StorageObfuscator` actually injected into the backends?**  
   - The protocol is defined but not used in the visible snippets.  
   - Is there a factory or dependency injection mechanism that passes the obfuscator into the backend at initialization?

4. **How are `EntityResolution` records used to link tensors?**  
   - The schema exists, but I do not see how entities are discovered, resolved, and linked across tensors.

5. **What is the relationship between `Apacheta` and `Pukara` beyond the HTTP gateway?**  
   - The snippets mention Pukara as a fortress and gateway, but the actual responsibilities of Pukara vs Apacheta are not fully detailed here.

---

### Closing

Overall impression: `src/yanantin/apacheta` is a coherent, carefully designed core for an immutable, provenance-aware knowledge graph. The design is not just about storage; it is about *epistemic observability* — tracking who said what, when, under what context, and how claims relate to each other through composition, dissent, and correction.

Key strengths:
- Strong interface-first design with multiple backends and a remote gateway.
- First-class support for disagreement and evolution (`DissentRecord`, `CorrectionRecord`, `SchemaEvolutionRecord`).
- Configuration is treated as just another domain of knowledge, stored as tensors with reasoning and predecessors.
- Explicit separation of local storage (DuckDB, memory) from the “fortress” pattern (Pukara) with a storage obfuscation protocol.

Key things to watch:
- Parsing fragility in `_tensor_to_config` and markdown parsing.
- The lack of visible garbage collection or archival strategy.
- The obfuscation protocol is defined but not yet wired into the visible backends.

If someone were about to modify this codebase, I would tell them:
- Respect the immutability invariant everywhere — do not add “update” methods; instead, add new composition operators.
- Be careful when changing the schema of `TensorRecord` or `ProvenanceEnvelope` — use `SchemaEvolutionRecord` to track migrations.
- When adding new query needs, prefer extending the `ApachetaInterface` and then implementing in all backends and the client, rather than adding backend-specific methods.

I have not invented anything beyond the code snippets I was shown; where I could not see details (e.g., operator implementations, `content_address.py`, `rummage.py`), I explicitly declared that as a loss.