<!-- Chasqui Scour Tensor
     Run: 1459
     Model: mistralai/mistral-small-creative (Mistral: Mistral Small Creative)
     Target: src/yanantin/apacheta
     Scope: introspection
     Cost: prompt=$1e-07/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 8084, 'completion_tokens': 5400, 'total_tokens': 13484, 'cost': 0.0024284, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0024284, 'upstream_inference_prompt_cost': 0.0008084, 'upstream_inference_completions_cost': 0.00162}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-30T22:21:37.795079+00:00
     GenerationID: gen-1774909266-yRtj1aS79ENxsZqFH4LD
-->

### **Tensor: Scour Report on `yanantin.apacheta` (Introspection Focus)**

---

### **Preamble**
**Target:** The `apacheta` submodule of Yanantin, a composable tensor infrastructure for epistemic observability. The focus was on **introspection**—how the system examines itself, tracks provenance, and manages compositional relationships.

**First Impressions:**
1. **Three Backends, One Interface:** The system enforces a strict separation between backends (`arango.py`, `duckdb.py`, `memory.py`) and the abstract `ApachetaInterface`. This is a classic "three backends" pattern (dict, SQL, graph) to ensure the interface remains honest to its contract.
2. **Immutability as a Core Principle:** Tensors and records are immutable once stored. Overwrites raise `ImmutabilityError`, forcing compositional operations (e.g., `correct`, `dissent`) instead.
3. **Epistemic Metadata as First-Class Citizens:** The `EpistemicMetadata` model (in `models/epistemics.py`) explicitly tracks truth/indeterminacy/falsity (T/I/F) and disagreement types, treating uncertainty as a structured part of the data.
4. **Provenance Everywhere:** Every record (`TensorRecord`, `CorrectionRecord`, etc.) includes a `ProvenanceEnvelope`, embedding who/what/when/why for all operations.

**What Drew Attention:**
- The **composition operators** (`operators/correct.py`, `operators/dissent.py`, etc.) felt like the "glue" of the system—how tensors relate to each other.
- The **epistemic models** (`models/epistemics.py`, `models/entities.py`) stood out as the "theory" layer, defining how the system reasons about truth and identity.
- The **rummage.py** tool, which searches across tensors and scour reports, felt like a "debugging lens" for the system’s own output.

---

### **Strands**

#### **1. The Three Backends: Thread-Safe, Immutable, and Honest**
**Files:** `backends/arango.py`, `backends/duckdb.py`, `backends/memory.py`
**Key Observations:**
- **Thread Safety:** All backends use `threading.RLock` to ensure thread safety during writes. The ArangoDB backend even locks at the database level (line 30 in `arango.py`).
- **Immutability Enforcement:** The `_store` method in both `arango.py` (line 120) and `memory.py` (line 40) checks for duplicate UUIDs and raises `ImmutabilityError` if violated. This is *not* just a database constraint—it’s a fundamental design choice.
- **Obfuscation Layer:** The `StorageObfuscator` (used in `arango.py` line 25) abstracts away storage-specific details (e.g., ArangoDB’s `_key` vs. DuckDB’s primary keys). This is a clever way to decouple the interface from backend quirks.
- **Graph vs. Document vs. Dict:** The comment in `arango.py` (line 10–12) hints at a future where ArangoDB’s graph features (e.g., traversing composition edges) are fully utilized. Currently, it’s just storing documents, but the infrastructure is there.

**Connections to Broader Project:**
- The **three backends** suggest this is designed for flexibility—you can swap persistence layers without changing the interface. This is critical for a system meant to scale (e.g., from in-memory prototyping to ArangoDB for production).
- The **obfuscation layer** implies the project anticipates needing to hide or transform data (e.g., for privacy or compliance). This aligns with the `EntityResolution` model’s redaction support.

**Assumptions:**
- **UUIDs are globally unique.** If two backends generate colliding UUIDs, immutability breaks. The code assumes `uuid4()` is sufficient (line 20 in `entities.py`).
- **Thread safety is enough for concurrency.** No distributed locks or transactions are modeled. This is fine for a single-process system but could be a bottleneck if Apacheta is later distributed.

**What Would Break If Changed:**
- If immutability were relaxed (e.g., allowing tensor updates), the composition operators (`correct`, `dissent`) would need redesign. They rely on preserving original claims.
- If the obfuscation layer were removed, backends would need to handle schema mappings manually, increasing coupling.

**What’s Missing:**
- **Conflict Resolution:** If two processes try to insert the same tensor simultaneously, one will fail. There’s no retry or merge logic.
- **Backup/Restore:** The `memory.py` backend has no persistence. The project seems to assume users will handle this externally (e.g., via ArangoDB).

---

#### **2. Epistemic Metadata: Truth as a Spectrum**
**File:** `models/epistemics.py`
**Key Observations:**
- **T/I/F Model:** The `EpistemicMetadata` class tracks truth, indeterminacy, and falsity as independent floats (lines 25–30). This is **neutrosophic logic**—values don’t sum to 1, and they can be outside [0, 1]. This is unusual in ML (where probabilities sum to 1) but aligns with the project’s goal of modeling uncertainty explicitly.
- **Disagreement Types:** The `DisagreementType` enum (line 15–18) distinguishes between empirical (resolvable with evidence) and definitional (framework-level) disagreements. This is a **theoretical choice**—it assumes all disagreements can be categorized this way.
- **Functional Representations:** The `functional_spec` field (line 28) suggests some epistemic values might be functions (e.g., "truth = f(context)") rather than scalars. This is forward-looking but not yet implemented.

**Connections to Broader Project:**
- The **epistemic models** feed into the **composition operators**. For example, a `correct` operation (in `operators/correct.py`) might use epistemic metadata to decide how to relate two tensors.
- The **declared losses** (`DeclaredLoss` class) are tied to epistemic metadata. When a tensor is composed, its losses are preserved (see `TensorRecord` in `models/tensor.py`), creating a "ledger of uncertainty."

**Assumptions:**
- **Epistemic values are meaningful.** The system assumes that T/I/F scores are useful for composition, but there’s no validation that they’re calibrated or consistent across tensors.
- **Disagreements are binary.** The `DisagreementType` enum treats disagreements as either empirical or definitional, but real-world disagreements might be gradated.

**What Would Break If Changed:**
- If the T/I/F model were replaced (e.g., with Bayesian probabilities), the composition operators would need to reinterpret how tensors relate. For example, `correct` might no longer assume that a correction implies higher truth.
- If `functional_spec` were implemented, the serialization/deserialization logic (e.g., in `arango.py` line 60) would need to handle arbitrary functions.

**What’s Missing:**
- **Normalization:** The comment in `epistemics.py` (line 22) notes that T/I/F values are "uncalibrated" and "may represent raw scores." There’s no mechanism to normalize or compare them across tensors.
- **Visualization:** The epistemic metadata is stored but not rendered. The `renderer/markdown.py` (not shown) might need extensions to display T/I/F scores.

---

#### **3. Composition Operators: The "Glue" of the System**
**Files:** `operators/correct.py`, `operators/dissent.py`, `operators/compose.py`, `models/composition.py`
**Key Observations:**
- **Operators as Functions:** Each operator (e.g., `correct`, `dissent`) is a pure function that takes an `ApachetaInterface` and returns a new record. This is a **functional programming** approach—no side effects, just transformations.
- **Dual Record Creation:** Most operators create **two things**:
  1. A **record** (e.g., `CorrectionRecord`, `DissentRecord`) describing the operation.
  2. A **composition edge** (`CompositionEdge`) linking the tensors.
  For example, `correct` (line 20 in `operators/correct.py`) stores both a `CorrectionRecord` and a `CompositionEdge` of type `RelationType.CORRECTS`.
- **Provenance Chaining:** Every operation embeds a `ProvenanceEnvelope`, which includes the author, timestamp, and context. This creates a **chain of custody** for how tensors relate.
- **Relation Types:** The `RelationType` enum (line 5 in `composition.py`) defines 10+ ways tensors can relate (e.g., `COMPOSES_WITH`, `DISSENTS_FROM`, `DOES_NOT_COMPOSE_WITH`). This is a **taxonomy of composition**, but it’s not clear how these types are used beyond storage.

**Connections to Broader Project:**
- The **composition edges** are stored in the same backends as tensors, enabling queries like "find all tensors that correct X" or "find the lineage of tensor Y."
- The **operators** are the "verbs" of the system, while the **epistemic models** are the "adjectives" (describing *how* tensors relate). Together, they form a **compositional language**.

**Assumptions:**
- **Composition is acyclic.** The `CompositionEdge` model doesn’t prevent cycles (e.g., A corrects B, B corrects A). This could lead to infinite loops in queries.
- **Relation types are exhaustive.** The `RelationType` enum assumes all possible tensor relationships are covered. In practice, new types might be needed (e.g., `SUPPORTS`, `CONTRADICTS`).

**What Would Break If Changed:**
- If the **dual-record pattern** (record + edge) were removed, the system would lose its ability to query relationships. For example, `rummage.py` relies on composition edges to traverse the graph.
- If **provenance were optional**, the system would lose its audit trail. This would break tools like `rummage.py` that filter by author or timestamp.

**What’s Missing:**
- **Operator Composition:** There’s no way to chain operators (e.g., "first correct, then refine"). Operators are atomic.
- **Edge Weights:** Composition edges are binary (they exist or don’t). There’s no way to weight or prioritize relationships (e.g., "this correction is more important than that one").

---

#### **4. Rummage: The System’s Debugging Lens**
**File:** `rummage.py`
**Key Observations:**
- **Full-Text Search:** `rummage.py` scans tensors, scour reports, and scout documents for arbitrary text patterns. It’s a **swiss army knife** for introspection.
- **Section-Aware Search:** It parses markdown into sections (preamble, strands, losses, etc.) and can search within specific sections (e.g., `--strands "fabrication"`).
- **Contextual Matches:** Results include surrounding lines (`context_before`, `context_after`), making it easy to see how a term is used.
- **Source Agnosticism:** It can search across multiple "sources" (e.g., `cairn`, `ai-honesty`), treating them as a unified corpus.

**Connections to Broader Project:**
- `rummage.py` is the **user-facing introspection tool**. It lets humans query the system’s own output, which is critical for a project about epistemic observability.
- It **complements the backends** by providing a way to explore data without writing custom queries.

**Assumptions:**
- **Markdown is the canonical format.** The parser assumes tensors are stored as markdown. If the format changes (e.g., to JSON), `rummage.py` would break.
- **Search is linear.** For large corpora, this could be slow. There’s no indexing or full-text search engine (e.g., Elasticsearch).

**What Would Break If Changed:**
- If the **markdown structure** changed (e.g., section headers were renamed), the `_classify_section` function (line 100) would need updates.
- If **new document types** were added (e.g., JSON logs), the parser would need extensions.

**What’s Missing:**
- **Advanced Querying:** No support for regex, boolean queries, or fuzzy matching. The `search` function (line 150) is basic.
- **Visualization:** Results are text-based. No way to generate graphs (e.g., of composition edges) or summaries.

---

#### **5. Entity Resolution: Privacy as Architecture**
**File:** `models/entities.py`
**Key Observations:**
- **Redaction as Deletion:** The `EntityResolution` model maps UUIDs to identities but supports **redaction** (setting `redacted=True`). This is a **privacy-by-design** feature—removing an entity doesn’t delete tensors, just the ability to resolve who they refer to.
- **Identity Types:** The `identity_type` field (line 15) is a string (e.g., "person", "organization"), but there’s no enum to validate it. This is flexible but risky.
- **Provenance for Redactions:** Even redactions are tracked via `ProvenanceEnvelope`. This creates an audit trail for privacy decisions.

**Connections to Broader Project:**
- This ties into the **obfuscation layer** in the backends. If an entity is redacted, the obfuscator could hide its UUIDs in queries.
- It’s part of the **epistemic observability** goal—tracking who/what is known and why.

**Assumptions:**
- **UUIDs are stable.** If an entity’s UUID changes after redaction, the mapping breaks.
- **Redaction is irreversible.** Once an entity is redacted, there’s no way to "un-redact" it. This is intentional but could be problematic for compliance.

**What Would Break If Changed:**
- If **redaction were made reversible**, the system would need to track "un-redaction" provenance, complicating the audit trail.
- If **identity types were enumerated**, the model would become less flexible but more type-safe.

**What’s Missing:**
- **Fine-Grained Redaction:** You can redact an entire entity, but not specific attributes (e.g., "hide the person’s name but keep their organization").
- **Access Control:** Redaction is all-or-nothing. There’s no way to say "only users with role X can see this entity."

---

### **Declared Losses**
*(What I chose not to examine and why.)*

1. **The `tensor.py` Model**
   - **Why:** The `TensorRecord` class (in `models/tensor.py`) is likely the "atom" of the system, but it was omitted from the scour. I assumed its structure would emerge from how it’s used in other files (e.g., `memory.py`, `operators/correct.py`).
   - **Loss:** I didn’t deeply analyze how strands, claims, or declared losses are structured within a tensor.

2. **The `renderer` Module**
   - **Why:** The `renderer/markdown.py` file was truncated. I assumed it handled markdown output but didn’t examine how epistemic metadata or composition edges are rendered.
   - **Loss:** I don’t know how the system visualizes its own data for humans.

3. **The `operators` Module (Full Scope)**
   - **Why:** I focused on `correct.py` and `dissent.py` but didn’t examine `compose.py`, `evolve.py`, or `negate.py`. These likely define other ways tensors relate.
   - **Loss:** I don’t know the full "vocabulary" of composition operations.

4. **The `ingest` Module**
   - **Why:** The `ingest/` directory (e.g., `markdown_parser.py`, `tensor_ballot.py`) seems to handle importing data into the system. I assumed this was out of scope for introspection.
   - **Loss:** I don’t know how tensors are created or validated on ingestion.

5. **The `storage_obfuscator.py`**
   - **Why:** This file defines how data is transformed for storage. I glossed over it, assuming it was a utility.
   - **Loss:** I don’t know the full obfuscation strategies (e.g., encryption, hashing) or how they interact with redaction.

6. **Error Handling and Edge Cases**
   - **Why:** I didn’t dig into how the system handles malformed data, concurrency conflicts, or corrupt backends.
   - **Loss:** I don’t know the resilience of the system under stress.

7. **Performance Considerations**
   - **Why:** I didn’t analyze query performance (e.g., `rummage.py` on large corpora) or backend bottlenecks (e.g., ArangoDB graph traversals).
   - **Loss:** I don’t know if the system scales to thousands of tensors.

8. **The `config.py` File**
   - **Why:** This likely contains default settings (e.g., backend URLs, obfuscation rules). I assumed it was boilerplate.
   - **Loss:** I don’t know if there are "magic numbers" or hardcoded paths.

---

### **Open Questions**
*(Things I can’t resolve from observation alone.)*

1. **How Are Tensors Composed?**
   - The `compose.py` operator is missing from the scour. How does the system combine tensors into new ones? Does it merge strands, average epistemic scores, or something else?

2. **What’s the "Budget" System?**
   - The `query_tensors_for_budget` method (line 200 in `memory.py`) suggests tensors have a "budget" (a float). What does this represent? Context? Computational cost? Epistemic weight?

3. **How Are Composition Edges Queried?**
   - The backends store `CompositionEdge` records, but I didn’t see how they’re queried (e.g., "find all tensors that correct tensor X"). Is this done via the backends or a higher-level layer?

4. **What’s the "Lineage" Mechanism?**
   - The `lineage_tags` field in `TensorRecord` (referenced in `memory.py` line 210) suggests tensors can be tagged for lineage. How are these tags used? For filtering? For visualization?

5. **How Does the System Handle Schema Evolution?**
   - The `SchemaEvolutionRecord` (in `composition.py`) tracks schema changes, but I didn’t see how migrations are applied. Is this manual, or is there an automated process?

6. **What’s the "Functional Spec" for Epistemic Values?**
   - The `functional_spec` field in `EpistemicMetadata` (line 28 in `epistemics.py`) is noted as "future work." Is this ever used, or is it a placeholder?

7. **How Are Disagreements Resolved?**
   - The `DissentRecord` (in `composition.py`) captures disagreements, but I didn’t see how they’re later addressed or reconciled. Is this a manual process?

8. **What’s the "Project State" Query For?**
   - The `query_project_state` method (line 220 in `memory.py`) returns high-level stats (e.g., tensor count, lineage tags). Who uses this, and for what?

9. **How Does the System Handle Conflicting Provenance?**
   - If two tensors claim to correct the same original claim but with different evidence, how does the system reconcile this?

10. **What’s the "Archivist’s Observation"?**
    - The comment in `epistemics.py` (line 18) references "the Archivist’s observation" about empirical vs. definitional disagreements. Who or what is the Archivist, and where is this documented?

---

### **Closing**
**Overall Impression:**
The `apacheta` submodule is a **rigorous, theory-driven system** for modeling compositional knowledge with explicit handling of uncertainty, provenance, and identity. It’s designed for **introspection**—not just storing data, but making it queryable, auditable, and composable. The three backends, immutability enforcement, and epistemic metadata are all signs of a system built for **long-term observability**.

**Strengths:**
1. **Theory Meets Practice:** The epistemic models (T/I/F, disagreement types) are grounded in real composition operations (correct, dissent, compose). This is rare in ML systems, which often treat uncertainty as an afterthought.
2. **Honest Abstractions:** The three backends and strict interface ensure the system doesn’t hide its quirks. This makes it easier to reason about.
3. **Provenance Everywhere:** The `ProvenanceEnvelope` is a masterstroke—it turns every operation into a traceable event, which is critical for a system about observability.
4. **Tooling for Introspection:** `rummage.py` is a brilliant way to let humans "debug" the system’s own output. It’s a microcosm of the project’s goals.

**Weaknesses:**
1. **Missing Operator Composition:** There’s no way to chain operations (e.g., "correct, then refine"). This limits how tensors can be transformed.
2. **No Edge Weights:** Composition edges are binary. Adding weights (e.g., "this correction is stronger than that one") would make the graph more expressive.
3. **Linear Search in Rummage:** For large corpora, `rummage.py` will be slow. Indexing or a proper search backend would help.
4. **Assumptions About UUIDs:** The system assumes UUIDs are unique and stable. In practice, collisions or changes could break things.
5. **No Visualization:** The epistemic metadata and composition graph are stored but not visualized. Adding a way to render these (e.g., as graphs or heatmaps) would make the system more usable.

**What I’d Tell a Modifier:**
- **Start with the Interface:** The `ApachetaInterface` is the contract. If you’re adding a feature, ask: *Does it fit within this contract, or do we need to extend it?*
- **Immutability is Sacred:** Overriding immutability will break composition operators. If you need mutability, design a new pattern (e.g., "versions" of tensors).
- **Provenance is Your Friend:** Every change should include a `ProvenanceEnvelope`. This is what makes the system auditable.
- **Epistemic Values Are Raw:** The T/I/F scores are uncalibrated. If you use them for composition, normalize or validate them first.
- **Rummage is Your Debugger:** If you’re unsure how something works, use `rummage.py` to search for examples in the wild.

**What I Know:**
- The system is designed for **compositional knowledge**—building new tensors from old ones while preserving provenance and uncertainty.
- It treats **identity and privacy** as first-class concerns (e.g., redaction, obfuscation).
- It’s **thread-safe** and **immutable by default**, which makes it predictable but rigid.

**What I Don’t Know:**
- How tensors are **composed** in practice (beyond the `compose.py` operator, which I didn’t see).
- How the **budget system** works (e.g., `query_tensors_for_budget`).
- How **schema evolution** is handled in production.
- How the system **scales** with thousands of tensors and edges.

**What I Made Up:**
- I assumed the `functional_spec` in `EpistemicMetadata` is a placeholder for future work (since it’s not used elsewhere in the scour).
- I assumed the "Archivist" is a theoretical construct (not a person or module) based on the comment in `epistemics.py`.
- I assumed the `lineage_tags` are used for filtering, but I didn’t see concrete examples.

**Final Thought:**
This is a **system for thinking with data**—not just storing it, but composing it, questioning it, and tracking its uncertainties. It’s ambitious, well-structured, and deeply principled. The biggest risk isn’t technical (the code is solid) but **theoretical**: the epistemic models (T/I/F, disagreement types) must hold up in practice. If they don’t, the composition operations will feel arbitrary. But if they do, this could be a **new way to build knowledge systems**—one where uncertainty isn’t an error to fix, but a feature to compose.