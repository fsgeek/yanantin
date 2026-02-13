<!-- Chasqui Scour Tensor
     Run: 11
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 9082, 'completion_tokens': 2873, 'total_tokens': 11955, 'cost': 0.00093788, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00093788, 'upstream_inference_prompt_cost': 0.00036328, 'upstream_inference_completions_cost': 0.0005746}, 'completion_tokens_details': {'reasoning_tokens': 49, 'audio_tokens': 0}}
     Timestamp: 2026-02-13T10:04:38.234439+00:00
-->

**Preamble**  
I was pointed at the `src/yanantin/apacheta` package – the core of the “Apacheta” tensor database that underpins the Yanantin project’s dual‑human/AI epistemic stack.  
My first visual cue was the top‑level `__init__.py` docstring (“Apacheta: the tensor database. Each traveler adds a stone.”) which sets a poetic tone but gives no concrete API. Scrolling through the tree I noticed three logical layers that repeatedly appear:

1. **Interface / abstract contracts** (`interface/abstract.py`, `interface/errors.py`)  
2. **Data models** (`models/…`) built on top of a frozen Pydantic base (`models/base.py`)  
3. **Operators** that act on an `ApachetaInterface` implementation (`operators/…`)  

The surrounding helper modules (`clients/`, `ingest/`, `content_address.py`, `renderer/markdown.py`) glue the pieces together.  

---

### Strand 1 – **Model Foundations & Immutability**

*Files examined:* `models/base.py`, `models/tensor.py`, `models/provenance.py`, `models/epistemics.py` (imported indirectly).  

*Observations*  

| Line / File | Detail |
|-------------|--------|
| `models/base.py:9‑19` | Defines `ApachetaBaseModel` with `ConfigDict(frozen=True, extra="forbid")`. This makes every record immutable after creation, matching the “once‑written, never‑overwritten” philosophy described in `config.py`. |
| All model files inherit from this base, ensuring JSON‑serializable, deterministic dumps via `model_dump`. |
| The `ProvenanceEnvelope` (not shown fully) is used everywhere to capture authorship, timestamps, and a list of predecessor IDs (`predecessors_in_scope`). This is the only place where *mutable* relationships (the DAG of tensors) are expressed. |

*Implications*  

- **Safety:** Immutability prevents accidental overwrites, which is crucial for an audit‑trail database.  
- **Rigidity:** Any need to “edit” a tensor must be expressed as a new tensor with a predecessor link. The codebase already provides helpers (`store_config`, `evolve`) that follow this pattern.  
- **Potential breakage:** Changing `frozen=False` would silently allow mutation of in‑memory objects, but the storage layer (`store_tensor`) would still treat them as immutable, possibly leading to inconsistent provenance.  

*Missing / Questions*  

- No explicit `__hash__` override; relying on Pydantic’s default may be fine, but if tensors are used as dict keys, a stable hash is needed.  
- No unit tests in this directory to validate that immutability truly propagates through nested structures (e.g., `TensorRecord.strands`).

---

### Strand 2 – **Interface Contract & Versioning**

*Files examined:* `interface/abstract.py` (not fully displayed), `interface/errors.py`, `clients/gateway.py`.  

*Observations*  

- `ApachetaInterface` defines the public API (store, get, query). The client implementation (`ApachetaGatewayClient`) is a thin HTTP wrapper that translates each method to a FastAPI endpoint.  
- Versioning is enforced via a module‑level constant `INTERFACE_VERSION` (imported in the client). The client’s `get_interface_version` simply returns the local constant, while a comment notes that the remote version must be fetched via `/api/v1/version`.  
- Error handling is centralised in `_handle_error`, mapping HTTP status codes to custom exceptions (`ImmutabilityError`, `NotFoundError`, etc.).  

*Implications*  

- **Decoupling:** The interface abstracts away the storage backend (could be Arango, DuckDB, or in‑memory). This enables the “bootstrap problem” described in `config.py`.  
- **Version drift risk:** If the server upgrades its API but the client library isn’t rebuilt, the client will still report its own version, potentially leading to subtle incompatibilities. The code hints at this but provides no automatic negotiation.  

*Potential breakage*  

- Adding a new endpoint (e.g., bulk tensor retrieval) without updating the abstract base will cause mypy/typing errors for any implementation that doesn’t implement it.  
- Changing the error‑code mapping (e.g., server now returns 422 for validation errors) would bypass the custom `InterfaceVersionError` and raise a generic `ApachetaError`.  

*Missing / Questions*  

- The abstract file isn’t shown; I could not confirm whether methods are annotated with `@abstractmethod` or if there are default implementations.  
- No retry logic for transient network failures; the client will raise on any non‑2xx status.

---

### Strand 3 – **Configuration as First‑Class Tensors**

*Files examined:* `config.py`, especially the `ConfigTensor` model and `_config_to_tensor` / `_tensor_to_config` helpers.  

*Observations*  

- Configurations are stored as immutable `TensorRecord`s with a special lineage tag `"config"` and a domain tag (e.g., `"chasqui.pulse"`).  
- Each setting becomes a `KeyClaim` (text `"key = value_repr"`). The parser uses `ast.literal_eval` to recover Python literals, falling back to raw strings on failure.  
- `store_config` logs the new tensor’s UUID and returns it, but does **not** enforce uniqueness of the domain – the caller must query `query_reading_order` and pick the latest.  

*Implications*  

- **Auditability:** Every change to a configuration is a new tensor with a provenance chain, making it possible to reconstruct the full evolution (via `query_reading_order`).  
- **Bootstrapping:** The docstring explains that when no DB is reachable, callers fall back to `DEFAULT_CONFIGS`. This dual‑source approach mitigates the chicken‑egg problem of needing a config to connect to the DB that stores configs.  

*Potential breakage*  

- If `query_reading_order` returns tensors out of order (e.g., due to clock skew), the “most recent” config could be stale. The code assumes timestamps are monotonic.  
- The conversion assumes every config tensor contains at least one strand with key claims; a malformed tensor would be silently ignored (`_tensor_to_config` returns `None`).  

*Missing / Questions*  

- No validation that the `settings` dict matches a schema for the domain – any key/value passes through.  
- No mechanism to garbage‑collect old config tensors; the DB could grow unboundedly over years of re‑configuration.  

---

### Strand 4 – **Markdown Ingestion & Content Addressing**

*Files examined:* `ingest/markdown_parser.py` (partial), `content_address.py`.  

*Observations*  

- The parser is deliberately tolerant: it matches strand headers with a regex that allows `##`, `###`, or plain “Strand N:”. It extracts key claims from bold text, numbered lists, and bullet points, assigning a default epistemic metadata of `(0.5, 0.5)`.  
- `TENSOR_METADATA` maps filenames to lineage tags, author families, and dates – a static lookup that supports both modern and legacy naming conventions.  
- `content_address.py` provides a stable SHA‑256 hash (first 16 hex chars) after normalizing line endings, collapsing blank lines, and trimming whitespace. This is used to detect duplicate markdown files (`deduplicate_report`).  

*Implications*  

- **Robustness:** The parser can ingest tensors produced by different LLMs (Claude vs. ChatGPT) without breaking.  
- **Deduplication:** Content addressing prevents re‑ingestion of identical tensors, which is essential for the “cairn” that accumulates many stones.  

*Potential breakage*  

- The parser’s heuristic for key claims may miss claims that are not bolded, leading to incomplete `TensorRecord.key_claims`. Downstream operators (e.g., `project`) that rely on these may produce incomplete views.  
- The hash prefix length (16 hex chars ≈ 64 bits) is safe for the expected scale, but if the cairn ever reaches billions of documents the collision probability becomes non‑trivial.  

*Missing / Questions*  

- No unit tests for the parser’s edge cases (e.g., nested lists, multiline claims).  
- No explicit handling of Unicode normalization (NFC/NFD); two visually identical files with different Unicode forms could get different hashes.

---

### Strand 5 – **Operator Suite & Composition**

*Files examined:* `operators/project.py`, `operators/evolve.py`, `operators/compose.py` (not displayed), `operators/bootstrap.py`, `operators/correct.py`, `operators/dissent.py`, `operators/negate.py`.  

*Observations*  

- Operators are thin functional wrappers that accept an `ApachetaInterface` and perform a single logical action (e.g., `project` filters strands, `evolve` records schema evolution).  
- Each operator returns a Pydantic model (e.g., `SchemaEvolutionRecord`) after persisting it via the interface.  
- The design encourages composability: a higher‑level workflow can chain operators, store intermediate tensors, and later render them with `renderer/markdown.py`.  

*Implications*  

- **Extensibility:** Adding a new operator only requires implementing the function and a matching model. The interface already provides generic `store_*` methods.  
- **Consistency:** Because all operators rely on the same immutable models, provenance is automatically captured.  

*Potential breakage*  

- Operators assume the interface implementation validates input; e.g., `project` does not check that `strand_indices` are within range, silently returning an empty list if none match.  
- The `project` implementation merges results from two criteria but does not de‑duplicate if a strand matches both – it guards against duplicates only when adding via topics (`if strand not in results`). However, if a strand matches both a given index **and** a topic, it could be added twice (unlikely due to the `elif` logic, but the intent is unclear).  

*Missing / Questions*  

- No documentation of expected exception flow for each operator (e.g., what happens if `interface.get_tensor` raises `NotFoundError`).  
- No test coverage shown for edge cases (empty tensors, missing strands).  

---

### Declared Losses  

- **Deep inspection of `models/provenance.py`, `models/epistemics.py`, and `interface/abstract.py`** – these files define the core data structures and abstract methods but were omitted from the provided excerpt, limiting my ability to verify field names, default values, and method signatures.  
- **Full operator implementations (`compose.py`, `bootstrap.py`, `correct.py`, `dissent.py`, `negate.py`)** – only `project.py` and `evolve.py` were shown; the rest could contain subtle logic (e.g., conflict resolution, provenance merging) that I could not evaluate.  
- **Backend implementations (`backends/arango.py`, `duckdb.py`, `memory.py`)** – without seeing how tensors are persisted, I cannot assess transactional guarantees, performance characteristics, or how immutability is enforced at the storage layer.  

---

### Open Questions  

1. **How does `query_reading_order` order tensors?** Is it purely timestamp‑based, or does it also consider topology (predecessors)?  
2. **What is the exact schema of `TensorRecord`?** The rendering code accesses fields like `preamble`, `strands`, `declared_losses`, `open_questions`, `instructions_for_next`, `closing`, but the model definition is not present.  
3. **How are provenance timestamps generated across distributed writers?** Clock skew could affect ordering of config tensors.  
4. **Is there any schema migration strategy beyond recording `SchemaEvolutionRecord`s?** How are older tensors read by newer code?  
5. **What authentication/authorization model does the Pukara gateway enforce?** The client’s `check_access` is a no‑op, but the server may have policies; without seeing server code we can’t confirm security.  

---

**Closing**  
The `apacheta` package is a well‑structured, purpose‑driven core that treats every piece of knowledge as an immutable tensor with rich provenance. Its design leans heavily on Pydantic immutability, a clear interface abstraction, and a set of composable operators that together enable an auditable, versioned knowledge graph.  

For anyone planning to modify this codebase:  

- **Preserve immutability** – avoid making models mutable; instead, create new tensors with proper predecessor links.  
- **Respect the interface contract** – add or change methods only in `interface/abstract.py` and ensure every backend and client implements them.  
- **Mind provenance** – any new operation that creates a tensor must populate `ProvenanceEnvelope` (author, timestamp, predecessors).  
- **Add tests** – especially for edge cases in the markdown parser, content hashing, and operator error handling.  

Overall, the module exhibits a thoughtful balance between flexibility (tolerant parsers, multiple backends) and rigor (immutable models, explicit provenance). The missing pieces (backend implementations, full model definitions) are the next places to examine to ensure the entire stack behaves as the design intends.