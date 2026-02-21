<!-- Chasqui Scour Tensor
     Run: 138
     Model: minimax/minimax-m2-her (MiniMax: MiniMax M2-her)
     Target: src/yanantin/awaq
     Scope: introspection
     Cost: prompt=$3e-07/M, completion=$1.2e-06/M
     Usage: {'prompt_tokens': 4997, 'completion_tokens': 2048, 'total_tokens': 7045, 'cost': 0.0039567, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0039567, 'upstream_inference_prompt_cost': 0.0014991, 'upstream_inference_completions_cost': 0.0024576}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-21T16:31:40.498621+00:00
-->

# Tensor Observation

## Preamble

I have been pointed at `src/yanantin/awaq` — the weaver. Awaq extracts composition declarations from tensor prose, converting narrative about relationships into formal edges. This sits at the core of Yanantin's claim: turning human-AI conversation into epistemic structure.

What drew my attention first was the name: Awaq means "weaver" in Quechua. This isn't just a utility — it's the system's narrative thread, the one that tries to bind together the loose prose of tensor documents into something machines can reason about.

## Strands

### Strand 1: Prose-to-Structure Transformation

**What I saw:** The machinery that turns natural language into typed relationships. `weaver.py` implements regex and keyword matching, with confidence scoring (high/medium/low) based on how explicitly composition is stated. Multiple patterns: structured HTML comments (`<!-- Composition: ... -->`), clear declarative prose, past tense constructions, counterfactual negation.

This appears to be the interface between human-AI collaboration and machine inference. The conversation "T15: Composing with T17 and T16; we read T0, T7" becomes typed edges in a graph database.

**What this makes me think:**

1. **The high-confidence problem:** Awaq assumes structured comments are definitive. If someone writes `<!-- Composition: T15 composes_with T17, T16; read T0, T7 -->` but never actually composes with them, what happens? The current code treats this as high-confidence truth, but epistemic trust shouldn't auto-accept authorial intent without verification.

2. **The confidence calibration issue:** The regex patterns in `weaver.py` serve multiple purposes — not just composition declarations. The current implementation treats all patterns as equal weight, but the intensity of composition language varies dramatically in discourse. For example, "while composing with T19" (used to declare a connection) and "while composing with a paqarina" (a historical anecdote that isn't an actual composition) are using identical grammatical patterns but carry vastly different epistemic weight. This creates a fundamental tension: there is a trade-off between treating local language patterns like "while [ tensor-name ] composes with" as propositional anchors (confirming specific typed composition) versus merely collecting contextual references. This decision involves balancing intentionality versus simple mention. 

3. **The layering problem:** Awaq generates declarations, `materialize.py` converts them to typed edges, but neither tracks through which layer of tensor abstraction those edges propagate. For instance, T₁₀₁ (systemic wisdom) composes with T₁₀₀ (cultural memory), but if T₁₀₁ is destroyed, does that destroy the composed wisdom in T₁₀₀? The code assumes composition edges are self-contained declarations, but tensor relationships often form deeper structural dependencies.

4. **The relation mapping gap:** `materialize.py` maintains a dict `_RELATION_MAP` that maps human-readable strings (e.g. "composes_with") to the internal system enum `RelationType`. However, this mapping is incomplete and relies on hardcoded keys. The comments in `weaver.py` imply an expected set of relationship types (such as "composes_with" or "corrects"), but `materialize.py`'s actual mapping often returns `True` as the type, which then falls through to a default `COMPOSES_WITH`. For example:

```python
# _RELATION_MAP in materialize.py:
_RELATION_MAP: dict[str, tuple[bool, RelationType | None]] = {
    "composes_with": (True, RelationType.COMPOSES_WITH),
    "bridges": (True, RelationType.BRIDGES),
    "corrects": (True, RelationType.CORRECTS),
    "branches_from": (True, RelationType.BRANCHES_FROM),
    "read": (True, RelationType.COMPOSES_WITH),
    "does_not_compose_with": (False, None),
    "standalone": (False, None),  # No edge — explicit declaration of no predecessors
}
```

This incomplete mapping can lead to a loss of semantic precision, where different relations end up as identical typed edges.

#### Connections to Broader Project

This connects directly to `rummage` and `apura`: a tensor is discovered (rummage), its composition relationships are extracted (awaq), and those relationships are exposed as entities the system can query (apura). The epistemic claim depends on this translation being lossless enough to preserve meaning.

The tensor federation also depends on this — when different systems contribute tensors, they need a common way to express and extract composition semantics.

#### Assumptions and their Validity

The fundamental assumption: regex and keyword matching is enough to capture composition intent from prose. This feels optimistic. Human language is messy, and composition declarations come in many forms that are difficult to reduce to patterns.

Awaq assumes structured comments are always authoritative. This is likely false — humans write mistakes, and comments can become stale.

#### What Would Break

If the regex pattern matching changed or became too strict, many composition declarations would fail to extract. This would break downstream services that expect formal composition edges, causing tensors to appear isolated even when they're not.

If structured comments stopped being treated as authoritative, the entire high-confidence path would break — effectively losing the most reliable signal for composition.

#### What is Missing

There is no review or verification mechanism for structured comments. The code assumes they are always correct, which is unlikely to be true in practice.

The confidence scoring does not seem to adjust for author reliability. It assumes all authors have similar precision in their declarations.

### Strand 2: The Dual Materialization Engines

**What I saw:** Awaq has two separate materialization engines that can operate independently, each with a different focus.

First, `awaq.weaver.materialize()` in `weaver.py` uses the InMemoryBackend to create an ephemeral, in-memory edge store for demonstration and testing. Its purpose is to show how informal weaver.Declarations can be converted into a formal graph structure (CompositionEdge and NegationRecord) within the context of the weaver module itself.

Second, `awaq.materialize()` in `materialize.py` is a dedicated and more sophisticated materialization pipeline. It integrates with the broader ApachetaInterface, enabling the storage of tensors and edges in a persistent backend such as ArangoDB. Unlike the in-memory version, it is designed for production use, managing tensor UUIDs, ensuring tensors exist before creating edges, and handling backend-specific tasks such as persisting edges to graph databases.

Both engines generate `CompositionEdge` and `NegationRecord` models, but their contexts and purposes differ.

**What this makes me think:**

1. **Scope and intent mismatch:** `awaq.weaver.materialize()` is designed as a lightweight, in-memory demonstration. It lacks features crucial for a production system, such as storing tensor metadata (e.g., body, type, tags) or ensuring referred tensors exist. On the other hand, `awaq.materialize()` is a full-fledged pipeline for persisting both tensors and their composition relationships. This creates confusion about the intended purpose of materialization.

2. **Redundancy and divergence:** The code is currently a duplicate of the engine in `materialize.py`. The in-memory pipeline hardcodes `store` to `print`, which is useful for demonstration. However, it stores edges with stubbed UUIDs (e.g., `tensors["T0"].id`) and cannot handle real persistence. Moreover, the module-level `materialize` call at the bottom of the file is only invoked if the script is run directly (`python weaver.py`).

3. **Dry run vs. persistent state:** There is no unified interface for dry-run materialization. Awaq's dry-run mode (sourcing from ` weave_corpus` and calling the in-memory pipeline) only displays how the formal structure would look; it does not persist any information. Conversely, `awaq.materialize()` performs persistent storage without a non-persistent mode. Therefore, it is not possible to run the full pipeline without changing the code, which makes it difficult to isolate and test the materialization logic itself.

4. **Complex branching:** The sample code directly passes the `backend` argument (a string, as defined in the argument parser) to the `materialize` function. However, the `materialize` function expects an `interface` instance, which is not passed. This creates inconsistencies because the `materialize` function relies on an object and not a string parameter. Furthermore, the hardcoded logic for generating `result` in the sample code generates a dictionary. However, according to the function signature in `materialize.py`, the return value is a `MaterializeResult` object. This type mismatch will lead to AttributeErrors when accessing properties such as `result.tensors_stored` and `result.skipped_unknown` later in the code.

#### Connections to Broader Project

This connects to the Yanantin composition infrastructure — `weave_corpus` and `materialize` are the explicit wires from narrative to structure.

The dual pipelines also connect to the persistence layer. `weave_corpus` only generates edge declarations in memory, whereas `materialize` integrates with the `ApachetaInterface`, potentially updating the permanent database state.

#### Assumptions and their Validity

1. **Assumption: Current in-memory pipelines are appropriate:** An in-memory pipeline is considered appropriate for demonstration purposes. This assumption overlooks the fact that in-memory storage does not persist data, meaning that state cannot be checked after processing is complete, which limits its diagnostic capability.

2. **Assumption: In-memory pipeline state checks are sufficient:** `store_tensors` and `store_edges` are configured to print the data they receive. This is sufficient for the initial acceptance test. However, it ignores the edge case of state collisions and storage exceptions (e.g., integrity failures or schema mism