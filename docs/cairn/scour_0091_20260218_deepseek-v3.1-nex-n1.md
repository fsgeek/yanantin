<!-- Chasqui Scour Tensor
     Run: 91
     Model: nex-agi/deepseek-v3.1-nex-n1 (Nex AGI: DeepSeek V3.1 Nex N1)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$2.7e-07/M, completion=$1e-06/M
     Usage: {'prompt_tokens': 5530, 'completion_tokens': 5225, 'total_tokens': 10755, 'cost': 0.0067181, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0067181, 'upstream_inference_prompt_cost': 0.0014931, 'upstream_inference_completions_cost': 0.005225}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-18T18:29:53.828230+00:00
-->

### Preamble

I was pointed at `src/yanantin/apacheta`, a subpackage named after the Andean stone cairns used to mark trails. The first thing that drew my attention was the project’s explicit framing: “the tensor database. Each traveler adds a stone.” That metaphor is operationalized in the code as immutable, provenance‑carrying records (`TensorRecord`, `ConfigTensor`, etc.) that are never updated, only extended or corrected. This is clearly the core storage and composition layer for Yanantin’s epistemic observability system.

---

## Strands

### 1. Immutability and provenance as the spine of epistemic observability

Across `models/base.py`, `models/provenance.py` (imported), `models/tensor.py` (imported), `config.py`, and `operators/correct.py` and `dissent.py`, the same pattern repeats:

- All models inherit from `ApachetaBaseModel`, which is:
  - `frozen=True` (immutable after creation)
  - `extra="forbid"` (closed schema)
- `TensorRecord` and `ConfigTensor` carry a `ProvenanceEnvelope` with:
  - `source`, `author_model_family`, `author_instance_id`
  - `timestamp`
  - `context_budget_at_write`
  - `interface_version`
  - `predecessors_in_scope` (lineage)

Implications:

- **No mutation, only extension**: Corrections don’t overwrite; they create new records (e.g., `CorrectionRecord`, `CompositionEdge` with `relation_type=RelationType.CORRECTS` in `operators/correct.py`). This is essential for epistemic observability: you can always see what was believed when, and by whom.
- **Auditability by design**: The `renderer/markdown.py` functions (`render_tensor`, `render_correction_chain`, `render_composition_view`) depend on this immutability and provenance. They assume they can fetch any tensor by UUID and display its author, timestamp, lineage tags, and epistemic T/I/F values.
- **Assumption**: The underlying interfaces (`ApachetaInterface` in `interface/abstract.py`) must enforce that stored tensors and composition records are never updated. The `ImmutabilityError` in `interface/errors.py` suggests this is enforced at the interface/backend level, not just the model level.

What would break if this changed?

- If tensors became mutable, all of the correction, dissent, and composition operators would become misleading: they reference prior tensors as stable targets. Rendering “correction chains” would be meaningless if the original tensor can change underfoot.
- If provenance fields were optional or removed, the epistemic metadata and compositional rendering would lose their grounding.

---

### 2. Tensors as structured epistemic objects with neutrosophic logic

From `models/epistemics.py`, `models/tensor.py` (imported), `renderer/markdown.py`, and `models/__init__.py`:

- `TensorRecord` contains:
  - `strands: tuple[StrandRecord, ...]`
  - `key_claims` (inside strands)
  - `narrative_body`
  - `preamble`, `closing`, `instructions_for_next`
  - `lineage_tags`
  - `epistemic: EpistemicMetadata`
  - `declared_losses: tuple[DeclaredLoss, ...]`
  - `open_questions: tuple[str, ...]`

- `EpistemicMetadata` uses T/I/F (truth, indeterminacy, falsity) as independent floats, explicitly not constrained to sum to 1.0. The docstring calls this “neutrosophic logic” and allows values outside [0,1] for uncalibrated scores.

- `KeyClaim` also carries `epistemic` metadata (per claim), and `render_tensor` displays T/I/F for both strands and claims when `include_metadata=True`.

What this means:

- The system explicitly supports **partial truth, partial indeterminacy, partial falsity** simultaneously. This is not a simple probability or fuzzy logic; it’s a three‑axis epistemic state.
- Rendering and storage are coupled: `render_tensor` expects `tensor.epistemic` and `claim.epistemic` to be available; it prints them directly in metadata blocks.
- There is a `RepresentationType` enum (`SCALAR` vs `FUNCTIONAL`) and an optional `functional_spec` in `EpistemicMetadata`, but in the visible code it’s not used yet. This feels like forward‑looking infrastructure for more complex epistemic representations.

Assumptions:

- Authors (human or AI) will assign T/I/F values in a reasonably consistent way so that aggregations/comparisons across tensors make sense.
- The renderer assumes scalar representation for now (no functional rendering logic is visible in `renderer/markdown.py`).

If this changed:

- If `EpistemicMetadata` were removed or flattened to a single confidence score, the “neutrosophic” design and the explicit handling of indeterminacy would be lost. Composition and disagreement operators (like `dissent`) presumably rely on these values to structure debate.
- If T/I/F were forced to sum to 1.0, it would break the explicit neutrosophic intent.

---

### 3. Configuration as tensors: versioned, reasoned, and chainable

In `config.py`:

- `ConfigTensor` stores configuration as:
  - `config_domain: str`
  - `settings: dict[str, Any]`
  - `reasoning: str`
  - `previous_config_id: UUID | None`
  - `provenance: ProvenanceEnvelope`
  - `timestamp: datetime`

- `store_config` converts a `ConfigTensor` to a `TensorRecord`:
  - Each setting becomes a `KeyClaim` with text `f"{key} = {value!r}"`.
  - The reasoning becomes `narrative_body`.
  - The tensor gets `lineage_tags=("config", config_domain)`.
  - `predecessors_in_scope` is set from `previous_config_id`.

- `get_current_config` queries by domain and picks the most recent tensor (last in `query_reading_order`). If nothing is found, it returns `None`, and the caller is expected to fall back to `DEFAULT_CONFIGS`.

- There is a **bootstrap problem** acknowledged in the docstring: you need configuration to reach the database, but config lives in the database. The solution is file‑based defaults + override by DB when available.

Observations:

- Config is not special‑cased in the core tensor schema; it’s just a `TensorRecord` with specific lineage tags and claim formatting. This is elegant: the same storage, provenance, and query mechanisms work for both knowledge and configuration.
- The `reasoning` field is crucial: each config change is justified. This aligns with the epistemic observability goal: you can see not just what the config was, but why it was chosen.
- The `DEFAULT_CONFIGS` dict provides a fallback for when no config tensor exists, and the docstring explicitly guides callers to handle `None` from `get_current_config`.

Assumptions / risks:

- `query_reading_order(domain)` is assumed to return tensors ordered by timestamp ascending, so the “current” config is the last one. If that ordering contract changed, `get_current_config` could silently return an old config.
- The code uses `ast.literal_eval` to parse values from `KeyClaim.text`; this works for Python literals but would fail for complex objects that don’t have a literal representation. The code catches parsing errors and falls back to storing the raw string, which is safe but can lead to type inconsistency on reconstruction.

What would break if this changed:

- If config tensors stopped using the `"config"` lineage tag, `_tensor_to_config` would return `None` for all of them.
- If `previous_config_id` were removed, the correction chain for configuration would be lost (though the tensor lineage via `predecessors_in_scope` would still exist).

---

### 4. Composition, correction, dissent, and schema evolution as first‑class operators

Across `operators/__init__.py`, `correct.py`, `dissent.py`, `evolve.py`, and `models/composition.py` (imported), there is a family of operators that create explicit relationships between tensors:

- `correct`:
  - Creates a `CorrectionRecord` capturing:
    - `target_tensor`, optional `target_strand_index`, `target_claim_id`
    - `original_claim`, `corrected_claim`, `evidence`
  - Optionally creates a `CompositionEdge` with `RelationType.CORRECTS` from the `correcting_tensor` to the `target_tensor`.

- `dissent`:
  - Creates a `DissentRecord` with:
    - `target_tensor`, optional `target_claim_id`
    - `alternative_framework`, `reasoning`
  - Always creates a `CompositionEdge` with `RelationType.DISSENTS_FROM`.

- `evolve`:
  - Creates a `SchemaEvolutionRecord` capturing:
    - `from_version`, `to_version`
    - `fields_added`, `fields_removed`
    - `migration_notes`

These operators all assume an `ApachetaInterface` that can:

- `store_correction`, `store_dissent`, `store_evolution`
- `store_composition_edge`
- `query_correction_chain` (used in `renderer/markdown.py`)

Observations:

- Composition is **explicit and typed**: edges are not just “related to”; they have a `RelationType` (e.g., `CORRECTS`, `DISSENTS_FROM`). This is the machinery that turns a pile of immutable stones (tensors) into a trail (a graph of epistemic moves).
- Correction preserves the original claim. This is crucial for epistemic honesty: you can see what was originally asserted and how it was revised.
- Dissent introduces a notion of **framework disagreement** (`alternative_framework`), not just factual correction. This aligns with the `DisagreementType` enum (`EMPIRICAL` vs `DEFINITIONAL`) in `epistemics.py`.

Assumptions:

- The interface implementation must index these records efficiently so that `query_correction_chain` and composition traversals are practical.
- There is an assumption that `CompositionEdge` and the various `*Record` types will be stored durably and atomically with tensor storage; otherwise, the graph could become inconsistent.

What is missing that might be expected:

- There is no visible `operators/compose.py` that defines how to traverse or aggregate along composition edges. `render_composition_view` takes an explicit list of `tensor_ids` rather than traversing edges. So composition is stored explicitly, but the automatic “compose a view by following edges” logic is not shown here.

---

### 5. Human readability as a separate layer, not a schema constraint

From `renderer/markdown.py`:

- `render_tensor`:
  - Turns `TensorRecord` into a structured markdown document with:
    - Preamble
    - Optional metadata block (ID, author, timestamp, context budget, lineage tags, T/I/F)
    - Strands as sections with topics and claims
    - Declared losses as a section
    - Open questions
    - Instructions for next instance
    - Closing
  - The output format is designed to match “T0‑T8 format conventions,” which suggests a pre‑existing template or convention outside this codebase.

- `render_composition_view`:
  - Renders multiple tensors with clear attribution: each tensor is shown under its own heading with author and ID.
  - The docstring emphasizes: “Composition preserves authorship — no collapsing into a flattened narrative.” This is consistent with the epistemic goal: don’t erase who said what.

- `render_correction_chain`:
  - Renders the history of corrections for a claim by querying `interface.query_correction_chain(claim_id)`.

Observations:

- The renderer is **tooling**, not schema. The schema holds structured, queryable data; the renderer turns it into human‑readable markdown. This separation is healthy: you can change rendering without changing storage.
- The renderer assumes that all the fields it references (`preamble`, `strands`, `declared_losses`, `open_questions`, `instructions_for_next`, `closing`, `lineage_tags`, `provenance`, `epistemic`) are present and have the expected types. There is no defensive handling for missing fields.

Assumptions:

- The calling code will typically call `render_tensor` with `include_metadata=True` when full epistemic context is desired.
- The “T0‑T8” format is a stable target; if that format changes, this renderer will need updating.

What would break if this changed:

- If `TensorRecord` were simplified (e.g., removing `instructions_for_next`), the renderer would still try to render it and might fail or produce empty sections.
- If `query_correction_chain` were removed from the interface, `render_correction_chain` would become unusable.

---

### 6. Epistemic honesty: declared losses, open questions, and disagreement typing

From `models/epistemics.py` and `renderer/markdown.py`:

- `DeclaredLoss` captures:
  - `what_was_lost`
  - `why`
  - `category: LossCategory` (`CONTEXT_PRESSURE`, `TRAVERSAL_BIAS`, `AUTHORIAL_CHOICE`, `PRACTICAL_CONSTRAINT`)
  - optional `severity` and `severity_rationale`

- `render_tensor` renders declared losses under “## Declared Losses” with the line: “The losses are mine.” This is a striking, first‑person acknowledgment of epistemic limitation.

- `EpistemicMetadata` includes:
  - `scope_boundaries: tuple[str, ...]` — where the claim is meant to apply.
  - `disagreement_type: DisagreementType | None` — empirical vs definitional.

Observations:

- The system encodes not just what is claimed, but:
  - What was deliberately left out and why.
  - Where boundaries of applicability are.
  - Whether disagreements are about facts or frameworks.
- This is highly aligned with the Yanantin theme of complementary duality and epistemic observability: you see not only the content but also the limits and the disagreements.

Assumptions:

- Authors (human or AI) will actually populate these fields honestly. There is no enforcement beyond the schema requiring them to exist.
- The renderer assumes that `declared_losses` and `open_questions` are small enough to render comfortably; extremely long lists could make the output unwieldy.

What is missing:

- There is no visible logic for aggregating or comparing declared losses across tensors, or for using `disagreement_type` in composition or querying. These are stored but not yet operationalized in the visible code.

---

### 7. Interface abstraction and backend diversity

From `interface/abstract.py` (imported), `interface/errors.py`, and the presence of `backends/` and `clients/` directories:

- `ApachetaInterface` is the abstract interface used by:
  - `config.py` (`get_current_config`, `store_config`)
  - `operators/*.py` (`store_correction`, `store_dissent`, `store_evolution`, `store_composition_edge`, `query_correction_chain`)
  - `renderer/markdown.py` (`render_composition_view`, `render_correction_chain`)

- The interface defines methods like:
  - `store_tensor`
  - `get_tensor`
  - `query_reading_order`
  - `store_correction`, `store_dissent`, `store_evolution`
  - `store_composition_edge`
  - `query_correction_chain`

- `interface/errors.py` defines:
  - `ImmutabilityError`
  - `AccessDeniedError`
  - `NotFoundError`
  - `InterfaceVersionError`

- `backends/` contains:
  - `arango.py`, `duckdb.py`, `memory.py` — suggesting multiple storage backends.
- `clients/` contains:
  - `gateway.py`, `openrouter.py` — suggesting external service integrations.

Observations:

- The core logic in `config.py`, `operators/*.py`, and `renderer/markdown.py` is backend‑agnostic; it depends only on the abstract interface. This is a strong architectural choice: you can swap storage or client implementations without changing the higher‑level logic.
- The presence of `InterfaceVersionError` suggests that the interface may evolve, and there is a versioning scheme to detect incompatibilities.

Assumptions:

- All backends must implement the full interface faithfully, including composition and correction storage.
- The interface is assumed to be durable and transactional enough that storing a tensor and its composition edges is safe.

What I did not see (and thus can’t confirm):

- The concrete implementations of `ApachetaInterface` in `backends/arango.py`, `duckdb.py`, `memory.py`. Without reading those, I don’t know how well they uphold immutability or how they index for queries like `query_reading_order` and `query_correction_chain`.

---

### 8. Ingest and content addressing: not fully visible

From the directory structure:

- `ingest/`:
  - `markdown_parser.py`
  - `tensor_ballot.py`
- `content_address.py`
- `rummage.py`

None of these files’ contents were provided. Based on names only:

- `markdown_parser.py` likely parses external markdown (e.g., scout reports) into `TensorRecord` structures.
- `tensor_ballot.py` suggests some form of voting or aggregation over tensors (perhaps for consensus or epistemic aggregation).
- `content_address.py` may implement content‑addressable storage for tensors (e.g., hashing tensor content to derive an ID or to detect duplicates).
- `rummage.py` might provide search or browsing functionality over stored tensors.

Because I cannot see the code, I can’t say how they interact with the rest of Apacheta. They are clearly important for the full picture, but they are outside the scope of what I was able to examine in detail.

---

## Declared Losses

1. **Backend implementations** — I did not examine `backends/arango.py`, `backends/duckdb.py`, `backends/memory.py`. These are central to how the system actually stores and indexes tensors, corrections, and composition edges. Without them, my understanding of performance, durability, and consistency guarantees is incomplete. I chose not to invent details about them.

2. **Client integrations** — I did not examine `clients/gateway.py` or `clients/openrouter.py`. These likely connect to external LLM gateways or routing services. They may be where `author_model_family` and `author_instance_id` are populated. Lacking them, I cannot say how provenance is captured at call time.

3. **Ingest pipeline** — `ingest/markdown_parser.py` and `ingest/tensor_ballot.py` are opaque. I don’t know how external documents become tensors, how key claims are extracted, or how “ballots” are structured. This is a major part of the epistemic pipeline that I had to leave aside.

4. **Content addressing and search** — `content_address.py` and `rummage.py` were not shown. I don’t know if tensors are content‑addressed, how deduplication works, or how users search/browse the tensor space.

5. **Unseen operator modules** — `operators/bootstrap.py`, `operators/compose.py`, `operators/negate.py`, `operators/project.py` were not provided. These likely implement important composition operations (e.g., bootstrapping a new knowledge base, projecting a subspace of tensors, negating claims). I did not speculate on their behavior.

6. **Entity resolution** — `models/entities.py` defines `EntityResolution`, but its content was not shown. I don’t know how entities are resolved across tensors or how that interacts with composition.

7. **Full `config.py`** — The file was truncated after `get_current_config` began. I saw the query and part of its structure, but not the complete implementation or any additional helper functions that might exist later in the file.

---

## Open Questions

1. **Composition traversal** — Is there a standard operator (e.g., in `operators/compose.py`) that traverses `CompositionEdge` relations to automatically build a reading order or a dependency graph? Or is composition purely manual (explicit lists of IDs)?

2. **Functional epistemic representation** — `EpistemicMetadata` includes `representation_type` and `functional_spec`, but no code I saw uses them. How is functional representation intended to be used? Will there be operators that evaluate these functions over inputs?

3. **Aggregation of epistemic values** — Are there operators that aggregate T/I/F across multiple tensors or claims (e.g., for consensus, disagreement, or epistemic risk assessment)? If so, where are they?

4. **Indexing and query performance** — How do the backends index tensors for `query_reading_order`, `query_correction_chain`, and composition edge lookups? Are there performance traps or scalability limits that the higher‑level code should be aware of?

5. **Schema evolution in practice** — `operators/evolve.py` records schema changes, but I didn’t see how these records are used. Is there migration tooling that applies these evolutions, or are they purely documentary?

6. **Content addressing and deduplication** — Does `content_address.py` enable deduplication of tensors? If two identical tensors are stored, do they get the same ID? How does this interact with provenance (same content, different authors)?

7. **Default config lifecycle** — When a config domain moves from `DEFAULT_CONFIGS` to having its first `ConfigTensor`, is there a bootstrapping operator that creates that initial config tensor with reasoning explaining the transition?

8. **Error handling in operators** — The visible operator functions (`correct`, `dissent`, `evolve`) don’t show explicit error handling for interface failures (e.g., if `store_correction` raises). Is there a standard pattern for retries, logging, or rollback in the calling code?

---

## Closing

Overall, `yanantin/apacheta` is a thoughtfully designed tensor database layer that embodies epistemic honesty and immutability. It treats configuration, knowledge claims, corrections, dissent, and schema evolution uniformly as tensors with provenance. The design is strongly influenced by neutrosophic logic (T/I/F), explicit disagreement typing, and declared losses, which together support a rich, auditable record of how knowledge evolves.

If I were about to modify this codebase, I would keep three things in mind:

1. **Immutability is non‑negotiable** — Do not introduce update‑in‑place for tensors, corrections, or composition edges. If you need to change something, add a new record and link it via predecessors or edges.

2. **Provenance and epistemic metadata are first‑class** — Any new tensor type or operator should carry and preserve provenance and epistemic annotations. If you add a new field, consider whether it needs to be reflected in `render_tensor` and in any future aggregation logic.

3. **Respect the interface abstraction** — Core logic should depend only on `ApachetaInterface`, not on backend‑specific details. If you need new query or storage capabilities, extend the interface and then implement it in all backends.

What I know comes from the files shown; what I don’t know lies in the backends, clients, ingest logic, content addressing, and several operator modules that were not included in the target. I have not invented details about those unseen parts; where I speculated, I labeled it as such.