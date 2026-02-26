<!-- Chasqui Scour Tensor
     Run: 229
     Model: openai/gpt-oss-120b:exacto (OpenAI: gpt-oss-120b (exacto))
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$3.9e-08/M, completion=$1.9e-07/M
     Usage: {'prompt_tokens': 12197, 'completion_tokens': 2516, 'total_tokens': 14713, 'cost': 0.00099108, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00099108, 'upstream_inference_prompt_cost': 0.00048788, 'upstream_inference_completions_cost': 0.0005032}, 'completion_tokens_details': {'reasoning_tokens': 50, 'audio_tokens': 0}}
     Timestamp: 2026-02-26T17:22:35.357193+00:00
-->

**Tensor Report – `src/yanantin/apacheta` (introspection)**  

---

### Preamble  
The `apacheta` package is the core “tensor‑infrastructure” of the Yanantin project.  
It bundles:

* **Back‑ends** (`memory`, `duckdb`, `arango`) that implement the same abstract interface.  
* **Clients** for external gateways.  
* **Ingestion** utilities that turn markdown files into `TensorRecord`s.  
* **Models** (Pydantic v2) describing tensors, provenance, epistemics, composition edges, etc.  
* **Operators** that create higher‑level records (bootstrap, correct, dissent, evolve, …).  
* **Renderers** that turn records back into markdown for human consumption.  
* **Utility scripts** (`content_address.py`, `rummage.py`, `storage_obfuscator.py`) for deduplication and obfuscation.

The first file I opened was `models/__init__.py` because it defines the public surface of the data model – everything else builds on those classes.

---

### Strands  

| # | Theme | What I saw (file / line refs) | Thoughts / Implications |
|---|-------|------------------------------|--------------------------|
| 1 | **Unified abstract interface** | `interface/abstract.py` (not shown fully, but referenced throughout) defines `ApachetaInterface`. All back‑ends inherit from it and must implement the same CRUD + query methods. | Guarantees *backend‑agnostic* code: operators, renderers, and ingestion use only the interface. Changing method signatures would break every backend and all callers. |
| 2 | **Immutability contract** | In `memory.py`, `store_*` methods raise `ImmutabilityError` if the UUID already exists (lines ≈ 29‑71). Same pattern in `duckdb.py` (`_store` checks `_exists` before INSERT) and `arango.py` (`_store` checks `collection.has`). | Enforces provenance‑preserving “append‑only” semantics. If a caller tried to “update” a tensor they must create a new tensor and a composition edge. This is central to the epistemic model; breaking it would allow silent overwrites and destroy the audit trail. |
| 3 | **Access control stub** | Each backend implements `_enforce_access` that calls `self.check_access`. The concrete `check_access` lives in the abstract base (not shown). All calls pass `"system"` as caller for internal ops. | The current code never defines granular permissions – it’s a placeholder for future RBAC. If a real ACL were added, every backend would need to respect it; otherwise security expectations would be unmet. |
| 4 | **Content addressing / deduplication** | `content_address.py` implements `content_hash` (normalizes line endings, collapses blank lines, hashes with SHA‑256, truncates to 16 hex chars). `ContentIndex` builds a hash‑to‑paths map, `deduplicate_report` produces a human‑readable report, `_check_file` reports duplicates against a cairn directory. | Provides a *content‑based* identity distinct from the numeric “T‑number”. This protects against accidental re‑ingestion of identical markdown. The 16‑char prefix gives ~2⁶⁴ space – sufficient for the expected scale. If the hash length were reduced, collision risk would rise; if increased, reports become noisier. |
| 5 | **Tensor numbering ballot** | `ingest/tensor_ballot.py` scans `cairn_dir` for existing `T*.md` files, computes the highest numeric prefix, and atomically claims the next number using `os.O_CREAT|O_EXCL`. The candidate loop (lines ≈ 46‑71) guarantees uniqueness across concurrent processes. | Mirrors the “Lamport bakery” algorithm used for “scout” numbering elsewhere. This is the *global* namespace for tensors, separate from the UUID primary key used by back‑ends. If the file‑system semantics change (e.g., on a network FS without reliable `O_EXCL`), collisions could appear. |
| 6 | **Markdown ingestion tolerance** | `ingest/markdown_parser.py` contains heuristics for extracting preamble, strands, key claims, declared losses, etc. It tolerates many formatting variations (different header levels, bold, bullet/numbered lists). Functions like `_find_strand_boundaries` (regex on line ≈ 70‑80) and `_extract_key_claims` (regex on bold text) illustrate a “best‑effort” approach. | Makes the system robust to human‑written tensors from different LLMs. However, the parser is *lossy*: any structure not matched is silently dropped (the docstring warns). If a new author adopts a different markdown style, parsing may miss claims or losses, requiring parser updates. |
| 7 | **Composition edge semantics** | `operators/compose.py`, `correct.py`, `dissent.py`, `negate.py`, `evolve.py`, `bootstrap.py` each create a `CompositionEdge` linking two tensors with a `RelationType` (e.g., `CORRECTS`, `DISAGREES`). For example, `correct()` (lines ≈ 5‑30) stores a `CorrectionRecord` then optionally a `CompositionEdge`. | This graph‑based provenance is the heart of the “epistemic observability” goal: every transformation is recorded as a directed edge. Changing the edge model (e.g., adding timestamps) would require updates across all operator modules. |
| 8 | **Rendering pipeline** | `renderer/markdown.py` builds markdown from a `TensorRecord`. It optionally includes a metadata block (lines ≈ 15‑35) and can render a composition view (`render_composition_view`) that aggregates multiple tensors preserving attribution. | Provides the human‑readable output that mirrors the original markdown format, closing the round‑trip. If the schema of `TensorRecord` changes (new fields), the renderer must be extended or will silently ignore them. |
| 9 | **Storage obfuscation** | `backends/arango.py` imports `StorageObfuscator` and `TransparentObfuscator`. The backend maps semantic collection names to opaque storage names (`_map.collection_name`). | Allows swapping to an obfuscating layer (e.g., encrypting collection names) without touching business logic. The current default is transparent; if a real obfuscator is supplied, all back‑ends will automatically use it. |
|10| **Schema centralisation** | Each backend defines a constant mapping (`_TABLE_MODEL` in DuckDB, `_SEMANTIC_MODEL` in Arango) that links collection/table names to Pydantic model classes. | Guarantees that the same model class is used for serialization/deserialization across storage types. Adding a new record type (e.g., “Annotation”) would need to be added in all three mappings. |

---

### Declared Losses  

| What was omitted | Why / Impact |
|------------------|--------------|
| **Full `interface/abstract.py`** – only referenced, not shown. Without seeing the abstract method signatures, I cannot verify that every backend implements *exactly* the same API (e.g., optional query methods). |
| **`storage_obfuscator.py` implementation** – only imported. Its behavior (e.g., encryption, name mangling) is unknown, so I cannot assess security implications. |
| **Error‑type hierarchy** – only `AccessDeniedError`, `ImmutabilityError`, `NotFoundError` are used, but the definitions are hidden. Understanding what fields they carry could affect how callers handle them. |
| **`rummage.py` and `config.py`** – not examined. These likely contain CLI utilities and configuration handling that affect runtime paths (e.g., where `cairn_dir` lives). |
| **`operators/bootstrap.py`, `evolve.py`, `dissent.py`, `negate.py`** – only `correct.py` was inspected. Other operators may have subtle differences (e.g., additional validation) that I have not verified. |
| **Testing suite** – not present in the tree. Without tests, it is hard to gauge coverage of edge cases (concurrent ballot, duplicate detection, backend failures). |
| **Documentation/comments** – many modules have docstrings but lack inline comments for complex logic (e.g., the regexes in the markdown parser). This makes future maintenance more error‑prone. |

---

### Open Questions  

1. **Access control semantics** – What concrete policies does `check_access` enforce? Is it ever overridden by a client or configuration?  
2. **Failure modes of the ballot** – On a network‑mounted filesystem where `O_EXCL` may not be atomic, could two processes claim the same number? Is there a fallback?  
3. **Content‑hash collision handling** – If two distinct documents happen to share the same 16‑char prefix, does `deduplicate_report` treat them as duplicates? Is there a secondary check?  
4. **Schema evolution** – `SchemaEvolutionRecord` exists, but I did not see any migration logic. How are schema changes applied to existing stored JSON blobs?  
5. **Obfuscator contract** – What methods must a `StorageObfuscator` implement? Does it also encrypt document fields or only collection names?  
6. **Performance of the in‑memory index** – `ContentIndex.from_directory` loads all `.md` files into memory. For a large cairn (thousands of tensors), could this become a bottleneck?  
7. **Thread safety across back‑ends** – The RLock protects each backend instance, but if the same backend object is shared across threads, is the lock sufficient for the underlying DB drivers (DuckDB, Arango)?  

---

### Closing  

`src/yanantin/apacheta` is a well‑structured, deliberately **backend‑agnostic** core that enforces an **append‑only, graph‑based provenance model**. The code makes clear design choices:

* **Immutability** and **access enforcement** are baked into every storage path.  
* **Content addressing** provides a secondary, content‑based identity to avoid duplicate ingestion.  
* **Lamport‑style ballot** ensures global numeric ordering of tensors without a central coordinator.  
* **Operators** encode epistemic actions as records plus composition edges, forming a navigable knowledge graph.  
* **Renderers** close the loop, turning structured records back into the human‑readable markdown format that originally fed the system.

The system’s **extensibility** hinges on the abstract interface and the mapping tables; adding a new storage backend or a new record type is straightforward but requires updates in three places (semantic collection/table list, model map, and the backend’s CRUD methods).

Potential pain points are the **lack of explicit tests**, the **opaque access‑control implementation**, and the **fragility of the markdown parser** when faced with novel authoring styles. Future contributors should:

1. **Add unit/integration tests** for the ballot, content hashing, and each backend’s CRUD operations.  
2. **Document the `check_access` contract** and consider a simple default policy.  
3. **Provide a more robust parser** or a pluggable parsing strategy to handle evolving markdown conventions.  
4. **Expose migration utilities** for `SchemaEvolutionRecord` so stored JSON can be upgraded safely.

Overall, the package presents a solid foundation for a “tensor‑based epistemic observability” system, with clear separation of concerns and a consistent data model. Modifications should respect the immutability contract and the graph‑oriented provenance design to preserve the project's core guarantees.