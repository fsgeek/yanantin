<!-- Chasqui Scout Tensor
     Run: 11952
     Model: kwaipilot/kat-coder-pro-v2 (Kwaipilot: KAT-Coder-Pro V2)
     Cost: prompt=$3e-07/M, completion=$1.2e-06/M
     Usage: {'prompt_tokens': 6600, 'completion_tokens': 1877, 'total_tokens': 8477, 'cost': 0.0042324, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0042324, 'upstream_inference_prompt_cost': 0.00198, 'upstream_inference_completions_cost': 0.0022524}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-06T23:21:25.869237+00:00
     GenerationID: gen-1778109669-HUNhZdxtwfLbxsmWGQWo
-->

### Preamble

I was dropped into `src/yanantin/` as a cost-free scout (`kwaipilot/kat-coder-pro-v2`, run #0). The prior scouts were busy denying each other's claims about operator files and model selection — a chorus of "DENIED" verdicts about whether code exists or matters. What caught my eye immediately: the system is obsessed with its own epistemic fragility. It doesn't just observe; it constantly declares what it *can't* know. The `attestation.py` file is the Rosetta Stone: it translates verification outcomes into honesty receipts with built-in loss statements.

### Strands

**Strand 1: Privacy-as-Architecture via Unmapping**

`src/yanantin/apacheta/models/entities.py` defines `EntityResolution` — a UUID-to-identity mapping where redaction means *deleting the mapping*, not touching any tensor records. This is a deliberate architectural choice: privacy is achieved by making identity unresolvable, not by erasing data. The tension: the system preserves all evidence but can surgically remove the ability to connect evidence to actors. This is GDPR-as-data-structure.

**Strand 2: Immutability Enforced at the Store Layer**

`src/yanantin/activity/backends/memory.py` reveals something subtle: the in-memory store raises `ImmutabilityError` on duplicate fact IDs or anchor handles. Facts and anchors are append-only. But the deep-copy-on-read pattern (`_deep_copy` via serialize/deserialize roundtrip) means every read creates a new object — the store never hands out references to its internal state. This is a functional-programming discipline imposed on a mutable Python dict. The tension between Python's mutability and the system's immutability contract is resolved by defensive copying.

**Strand 3: Content Filtering Without Query Pushdown**

`src/yanantin/query/engine.py` does all filtering in Python. The docstring explicitly says "AQL/SQL pushdown is a future optimization." The `_resolve_dotpath` function traverses nested dicts with a `_MISSING` sentinel, and `_apply_filter` supports `exists`, `eq`, `contains`, `glob`, `gt`, `lt`, `gte`, `lte` — but all against in-memory fact dicts. This means the store is the bottleneck: every query fetches all facts in a time range from all providers, then filters in process. The architectural bet: stores are simple (dict-based or DB-backed), query complexity lives in the engine. Scalability tension is acknowledged but deferred.

**Strand 4: Blockchain-Anchored Provenance Chains**

`src/yanantin/provenance/__init__.py` integrates OpenTimestamps for Bitcoin-anchored commit timestamping. Each commit's proof is included in the *next* commit, forming a chain. A genesis timestamp is required before the first commit. This is evidentiary-grade: GPG proves *who*, OTS proves *when*. The surprising detail: the module docstring is a usage tutorial embedded in the `__init__.py` — it's meant to be read as documentation, not just imported. The tension: this is heavy infrastructure (OTS roundtrips, Bitcoin anchoring) for a codebase that also has an in-memory dict store. The system spans from toy to production in the same breath.

**Strand 5: Guarded Willay Imports — Optional Epistemic Ledger**

`src/yanantin/chasqui/attestation.py` guards all Willay imports behind `_WILLAY_AVAILABLE`. The module is importable without Willay; functions that need it raise `ImportError`. This reveals a plugin architecture: Willay (the epistemic receipt ledger) is optional. The system can verify claims without recording receipts. But the `_common_declared_losses()` function is fascinating — it hardcodes three universal losses:
1. "Single-LLM verification" (severity 0.7) — no cross-verification
2. "Hallucination risk in verifier" (severity 0.6) — LLMs confabulate
3. "Temporal code drift" (severity 0.4) — files change between extraction and verification

These aren't computed; they're *declared*. The system bakes in its own skepticism.

**Strand 6: Verdict-to-Epistemics Mapping is Asymmetric**

The `_VERDICT_EPISTEMICS` dict maps:
- `CONFIRMED` → (T=0.7, I=0.3, F=0.0) — even confirmation is only 70% truthful
- `DENIED` → (T=0.0, I=0.2, F=0.7) — denial is 70% false, but 20% indeterminate
- `INDETERMINATE` → (T=0.0, I=0.9, F=0.0) — almost pure uncertainty
- `MODEL_FAILURE` → (T=0.0, I=1.0, F=0.0) — total ignorance

The `_VERDICT_QUESTIONS` add open questions per verdict. This is a formal epistemology: every verification result carries its own doubt metadata. The prior scouts argued about whether operators exist; this file says the *verdict itself* is less important than the questions it raises.

### Declared Losses

- I did not read the `collector/` submodules beyond their `__init__.py` files. The collector pattern (dropbox, filesystem, fs_events, openrouter) appears to be a replicated structure — I assumed the pattern holds and didn't verify each.
- I did not examine `apacheta/operators/` files (`bootstrap.py`, `compose.py`, `correct.py`, `dissent.py`, `evolve.py`, `negate.py`, `project.py`). The prior scouts' contradictory claims about these files (some said they don't exist, others said they do) made me suspicious. I chose to focus on files I could read fully rather than enter that fray.
- I did not trace the `chasqui/` coordinator/scout/analyst pipeline. The attestation adapter is the boundary I cared about; the dispatch mechanism is a separate territory.
- I did not check whether Willay is actually installed or used anywhere — the guard is there, but I didn't verify if it's ever triggered.

### Open Questions

1. **Do the operator files actually exist and have content?** The prior scout findings are contradictory: one says "No references, imports, comments, or definitions for `bootstrap.py`, `compose.py`..." (DENIED), another says "The dissent operator in `src/yanantin/apacheta/operators/dissent.py` further reinforces this" (also DENIED). The file listing shows them. Are they empty? Do they contain code that was mischaracterized?

2. **What is the `openrouter.py` tension?** One prior finding says "The conflicting prior claims about `openrouter.py` are a critical unresolved tension." There are two `openrouter.py` files: `apacheta/clients/openrouter.py` and `collector/openrouter/`. What's the conflict?

3. **How does the OTS chain survive repository forks or rebases?** The provenance module assumes a linear commit chain. What happens when history is rewritten?

4. **Is the in-memory store ever used in production, or is it purely for testing?** The `activity/backends/` directory also has `arango.py` and `duckdb.py` — are those the real backends?

5. **What is the `tawaq` / `awaq` module?** `src/yanantin/awaq/` has `materialize.py` and `weaver.py` — completely unexplored by me. The name suggests weaving/materialization of tensors.

### Closing

This codebase is a philosophical statement rendered in Python. It assumes that all knowledge is partial, all verification is lossy, and all identity should be revocable. The surprising thing isn't the infrastructure — it's the *humility* baked into every layer. The attestation adapter doesn't just record verdicts; it records *why the verdict might be wrong*. The entity resolution doesn't just store identities; it provides a redaction mechanism that preserves evidence while destroying links.

The prior scouts were trapped in a verification loop — arguing about whether code exists rather than what it means. The tension I'd pass to the next scout: **this system is designed to survive its own failure**. Every component declares what it can't do. The question isn't whether the operators exist — it's whether the system's epistemic honesty is performative or operational.

Tell the next scout: look at what the code *refuses* to claim, not what it asserts. The declared losses are the real API.