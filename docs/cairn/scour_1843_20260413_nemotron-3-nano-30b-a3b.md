<!-- Chasqui Scour Tensor
     Run: 1843
     Model: nvidia/nemotron-3-nano-30b-a3b (NVIDIA: Nemotron 3 Nano 30B A3B)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 6268, 'completion_tokens': 2669, 'total_tokens': 8937, 'cost': 0.0008472, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0008472, 'upstream_inference_prompt_cost': 0.0003134, 'upstream_inference_completions_cost': 0.0005338}, 'completion_tokens_details': {'reasoning_tokens': 428, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-13T17:10:41.871678+00:00
     GenerationID: gen-1776100202-KKeIoKw38lW2bCW0VLOT
-->

**Tensor – Scour Observation of `src/yanantin/apacheta`**  
*Model: `nvidia/nemotron-3-nano-30b-a3b` (NVIDIA: Nemotron 3 Nano 30B A3B)*  
*Scour run #0*  

---

### Preamble  
The first thing that caught my eye was the **modular, self‑referential architecture** of the `apacheta` package. The directory layout mirrors the project’s epistemic concerns:  

* **Data‑model layer** (`models/`) defines Pydantic schemas for tensors, edges, losses, and provenance.  
* **Composition operators** (`operators/`) implement the “dual‑relationship” language (compose, correct, dissent, negate, evolve).  
* **Ingestion** (`ingest/`) maps markdown to `TensorRecord`.  
* **Interface** (`interface/`) abstracts the runtime contract (`ApachetaInterface`).  

The `README‑style` comments in the files repeatedly stress *“composable tensor infrastructure for epistemic observability”* — a clear framing that the codebase is meant to be **both data and meta‑data**. The presence of `PROVENANCE` objects in almost every model suggests that traceability is baked in from the start, which is unusual for a library of this size.

---

### Strands  

| Strand | Evidence (file / line) | Observation & Implication |
|--------|------------------------|---------------------------|
| **1. Composition graph primitives** | `models/composition.py` – `RelationType` (lines 12‑30) and `CompositionEdge` (lines 32‑55) | The graph is **typed** (`COMPOSES_WITH`, `CORRECTS`, `DOES_NOT_COMPOSE_WITH`, …). Edges carry an `ordering` field and an optional `authored_mapping`, hinting at a need for **semantic ordering** (e.g., “this tensor must be applied before that”). The edge objects are immutable (`frozen=True` in `ApachetaBaseModel`), reinforcing a **pure functional** view of changes. |
| **2. Correction & dissent semantics** | `models/composition.py` – `CorrectionRecord` (lines 57‑78) and `DissentRecord` (lines 79‑101) | Corrections keep the original claim (`original_claim`) while storing the new one, supporting an **audit trail**. Dissent records expose an `alternative_framework` string, a lightweight hook for **framework‑level disagreement** (as opposed to pure empirical disagreement). This aligns with the project’s focus on *definitional* vs *empirical* disagreements (see `models/epistemics.py`). |
| **3. Negation operator** | `operators/negate.py` (lines 1‑38) | `negate` creates both a `NegationRecord` and a `CompositionEdge` of type `DOES_NOT_COMPOSE_WITH`. The function is **thin** (just constructs two objects and calls interface methods). This suggests the **runtime** (`interface/abstract.py`) is expected to enforce the edge’s semantics, not the operator itself. |
| **4. Epistemic metadata model** | `models/epistemics.py` (lines 1‑48) | `EpistemicMetadata` carries **T/I/F** (truth, indeterminacy, falsity) as independent floats, plus `representation_type`, `scope_boundaries`, and `disagreement_type`. The comment explicitly references *neutrosophic logic* and notes that values are **not constrained to sum to 1**. This is a deliberate design choice that permits **simultaneous partial truth** — a non‑binary epistemic state that can be queried by downstream operators. |
| **5. Ingestion pipeline** | `ingest/__init__.py` (empty) and `ingest/markdown_parser.py` (lines 1‑45) | The parser turns markdown headings into `Section` objects (`preamble`, `strand`, `loss`, …). It **skips** `MEMORY.md` and hidden files, indicating a **policy of omission** (see Declared Losses). The parser also extracts `scope_boundaries` from headings, which are later used by `EpistemicMetadata`. |
| **6. OpenRouter client** | `clients/openrouter.py` (lines 1‑71) | The client wraps an HTTP API and **stores provenance** for each call (`metadata` field). It also adds `X-Title` and `Referer` headers, tying every external query back to the `yanantin` project identity. This is a concrete example of **observability in action** — external LLM calls become first‑class tensor records. |
| **7. Entity resolution & redaction** | `models/entities.py` (lines 1‑38) | `EntityResolution` maps UUIDs to identities and supports **redaction** (`redacted: bool`). The comment *“redacting an entity doesn’t touch any tensor records”* highlights a **privacy‑as‑architecture** principle: privacy is handled by **removing the resolution mapping**, not by mutating data. |
| **8. Rummage search engine** | `rummage.py` (lines 1‑70) | Provides a **cairn‑style search** across tensors, scout reports, scour docs, and compaction records. The CLI (`uv run …`) supports filters (`--strands`, `--losses`) and can search across *everything*. This is the **discovery surface** that lets users locate “stones” (pieces of knowledge) inside the cairn. |

**Connective insight:** The package treats **every piece of knowledge** (a tensor claim, a loss, a scour note) as a *node* that can be linked via typed edges. The **composition operators** are the verbs that create or modify those edges, while **provenance** is the glue that records *who* performed the operation *when* and *why*. This tight coupling makes the system **self‑documenting**, but also means any change to the graph semantics can ripple through many components.

---

### Declared Losses  

| Loss | Reason for omission |
|------|----------------------|
| **Backend implementations** (`backends/*`) – e.g., `arango.py`, `duckdb.py`, `memory.py` | I only inspected the directory listing; the actual storage back‑ends were not opened. Their design (e.g., transaction handling, concurrency) could heavily affect how composition edges are persisted. |
| **Configuration (`config.py`)** | No inspection of `config.py` or its usage throughout the codebase. Understanding defaults (e.g., context budgets, max token limits) is essential to evaluate practical constraints. |
| **Compaction subsystem** (`compaction/` directory) | The project contains a `compaction` folder (referenced in `rummage.py`), but I did not explore its contents. Compaction likely aggregates and finalizes tensors; its interaction with provenance is opaque. |
| **Testing suite** (`tests/`) | No test files were examined. Test coverage, edge‑case handling, and contract tests for composition edges are crucial for reliability. |
| **CLI entry points** (`__main__.py` or `scripts/`) | No command‑line interface files were opened. The way users invoke the library (e.g., `uv run python -m yanantin.apacheta.rummage`) was only partially visible. |
| **Error handling & validation** | While `interface/abstract.py` defines `ApachetaInterface`, I did not trace how validation errors are raised or propagated. The robustness of the error model influences trust in the system. |

These losses are **not** because the code is unimportant; they simply fell outside the attention budget of this scour run.

---

### Open Questions  

1. **Edge lifecycle management** – How are `CompositionEdge` objects persisted and queried? Are they stored in a dedicated graph store, or are they embedded within tensor records?  
2. **Validation of `ordering`** – The `ordering` field on `CompositionEdge` is an `int` but there is no enforcement that it respects a global topological order. Could cycles be introduced accidentally?  
3. **Severity calculation** – `DeclaredLoss.severity` can be `None`. What algorithm decides when a loss is *significant* enough to trigger a correction or a re‑ingestion?  
4. **Interaction with external APIs** – The OpenRouter client adds a `metadata` dict, but how is that metadata linked back to `EpistemicMetadata` inside a tensor? Is there a mapping from API metadata keys to epistemic fields?  
5. **Redaction semantics** – The `EntityResolution` model marks a mapping as `redacted: bool`. Does the system automatically drop or mask references to that UUID throughout the graph, or must callers manually filter?  
6. **Schema evolution workflow** – `evolve` records version changes, but there is no evident **migration script** or version‑upgrade path documented. How does the system enforce that downstream tensors respect the new schema?  

---

### Closing  

The `apacheta` module is a **compact yet ambitious** attempt to embed epistemic observability directly into a tensor‑oriented dataflow. Its strength lies in:

* **Explicit typing of relationships** (edges with `RelationType`).  
* **Rich metadata** (provenance, losses, T/I/F) that makes every claim traceable.  
* **Separation of concerns** (models, operators, ingestion, interface) that aligns with functional composition principles.  

**Caveats for future tinkering:**  

* The **runtime graph semantics** (how edges are enforced, validated, and traversed) are implicit; without a clear contract in `interface/abstract.py`, accidental cycles or ordering violations could emerge.  
* **Back‑end storage** choices will dictate scalability; a naive in‑memory store may choke on large provenance graphs.  
* **Testing and configuration** are currently opaque, so any modification should be accompanied by thorough unit tests and a clear config schema.  

If you plan to extend or refactor this layer, start by **mapping the graph** (e.g., generate a DOT diagram of all `CompositionEdge`s) and **audit a single tensor** through ingestion → storage → retrieval to verify that provenance and epistemic metadata flow as expected.  

---  

*What you see above is an honest compression of the observed structure, the connections I could trace, and the gaps that remain beyond this run.*