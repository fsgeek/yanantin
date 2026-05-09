<!-- Chasqui Scout Tensor
     Run: 12424
     Model: nvidia/nemotron-3-nano-30b-a3b (NVIDIA: Nemotron 3 Nano 30B A3B)
     Cost: prompt=$5e-08/M, completion=$2e-07/M
     Usage: {'prompt_tokens': 9576, 'completion_tokens': 2779, 'total_tokens': 12355, 'cost': 0.0010346, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0010346, 'upstream_inference_prompt_cost': 0.0004788, 'upstream_inference_completions_cost': 0.0005558}, 'completion_tokens_details': {'reasoning_tokens': 965, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-09T13:53:08.201433+00:00
     GenerationID: gen-1778334734-UX9rzQ3s2kZPRqSxBbzt
-->

**Tensor of Observation – Scouting `tests/unit/`**

---

### Preamble  
I was deposited by the chasqui sampler into the `tests/unit/` directory of the Yanantin project. My first glance landed on `tests/unit/test_query_models.py` – a dense, self‑contained suite that defines frozen data‑model contracts for `ContentFilter`, `QuerySpec`, `QuerySummary` and `QueryResult`. The fixture‑heavy structure of the rest of the directory (≈ 90 +  test modules) immediately suggested a “copy‑and‑paste‑then‑tweak” culture: each module mirrors the same pattern of fixtures, a handful of `pytest` parametrisations, and a set of assertions that are more *ritual* than *verification*.

What caught my eye first was the **repetitive use of `pytest.raises(Exception)`** without specifying the exact exception type, and the frequent reliance on `assert len(...) == 0` or `assert count == expected` as the sole success criterion. The codebase is heavily **parameterised across backends** (`memory` vs `duckdb`) but the tests rarely probe the *differences* between them; they treat the backend as a black box.

---

### Strands  

| Strand | What I Saw | Why It Matters |
|--------|------------|----------------|
| **1️⃣ Frozen‑Model Discipline with “extra‑allowed” Loophole** | `TestContentFilter.test_extra_forbid` expects `ContentFilter(field="path", op="eq", value="x", bogus="nope")` to raise, yet `TestQuerySpec.test_extra_allowed` constructs a `QuerySpec(source="natural_language", confidence=0.8)` and *doesn’t* raise. The `extra="forbid"` flag is only enforced on the **constructor**, not on the **`model_dump`/`model_validate` round‑trip** used elsewhere (e.g., in `test_models.py`). | The inconsistency reveals a hidden contract: some layers reject unknown fields, others silently accept them. This creates a **semantic gap** between compile‑time validation and runtime serialisation. |
| **2️⃣ “Default‑ish” Fixtures that Hide Real Data** | Fixtures like `base_time`, `provider_a`, `provider_b` are used to seed facts, but the `base_time` is *hard‑coded* to `2026‑02‑20 12:00:00+00:00`. The generated facts’ timestamps are derived from this anchor, yet many tests assert only *inequality* (`assert result.total_matched == 3`) without checking that the timestamps actually fall inside the requested range. | The tests assume that the **temporal ordering** of facts matches the order of insertion, but they never verify monotonicity or uniqueness of timestamps. This could mask bugs where a backend reorders rows (e.g., DuckDB) while still passing the coarse‑grained checks. |
| **3️⃣ Synthetic Collectors & “Round‑Trip” Gaps** | `SyntheticFilesystemCollector` writes files to a temporary directory, then a `FilesystemFactRecorder` creates `FactRecord`s whose `content_hash` is asserted to be a 16‑character SHA‑256 prefix. The test only checks that `content_hash != ""` and length‑16, **not** that the hash actually corresponds to the file’s SHA‑256. | The **cryptographic integrity** claim is weakened: a malformed hash could be a placeholder, yet the test silently passes. |
| **4️⃣ Over‑Generalised Verdict Mapping** | In `test_attestation.py`, `test_unknown_verdict_defaults_to_model_failure` maps any unknown verdict to `T=0.0, I=1.0, F=0.0`. The test suite includes a *comment* that “every verdict produces exactly 3 declared losses”. However, the **enum `LossCategory`** is never exercised; there is no test that asserts each loss category is *meaningful* or that the three losses are *mutually exclusive*. | The mapping from verification verdicts to epistemic receipts is **under‑specified**; the declared losses could be arbitrary strings, making the receipt’s semantics fragile. |
| **5️⃣ Prompt‑Template Coupling to Scopes** | `test_scourer.py` defines four scopes (`introspection`, `external`, `tensor`, `synthesis`) and validates that `format_scour_prompt` returns a system prompt equal to `SCOURER_SYSTEM_PROMPT`. Yet the **template strings** (`SCOURER_INTROSPECTION_TEMPLATE`, etc.) are never exercised with *malformed* inputs (e.g., empty target, non‑existent file). The test only checks role `"user"` presence. | The **robustness** of the prompt builder under edge conditions is never probed, leaving a potential source of runtime errors when external scouts supply malformed `target` paths. |
| **6️⃣ Parameter Explosion without Coverage** | The `store` fixture parametrises over `"memory"` and `"duckdb"` (line ~30 in `test_query_engine.py`). While both backends are exercised, the **parameter matrix** never includes combinations like `provider_id=None` or `limit=0`. The test suite’s coverage matrix therefore omits edge‑cases that could surface in real usage (e.g., pagination with `offset > limit`). | The **parameter explosion** is superficial; it does not systematically explore the combinatorial space, leading to a *false sense of coverage*. |

---

### Declared Losses  

| Loss | Reason |
|------|--------|
| **Depth of backend comparison** – I did not benchmark actual query latency or memory footprints between `InMemoryActivityStreamStore` and `DuckDBActivityStreamStore`. | Measuring performance would require instrumentation outside the unit‑test scope and would involve external process invocation, which is beyond the current observational budget. |
| **Full enumeration of `ContentFilter` operators** – I only noted that all ops are accepted (`contains`, `eq`, `gt`, …) but did not inspect the *implementation* of `ContentFilter.validate_op` or its interaction with the query engine. | The actual validation logic lives in compiled code (`yanantin/query/engine.py`) that I did not read; without that source I can only hypothesise. |
| **Cross‑module integration** – I did not trace how a `QueryResult` propagates `facts` into downstream components (e.g., `QueryFactRecorder`). | Integration points involve asynchronous pipelines and external I/O; they are not visible in isolated unit tests. |
| **Custom normalizer registration side‑effects** – I did not explore whether registering a normalizer mutates the global registry for subsequent tests. | The registration occurs at import time; side‑effects could cause test order dependencies that are hidden by pytest’s collection order. |

---

### Open Questions  

1. **Why does `QuerySpec` expose `content_hash` as a field but never use it in the tests?**  
   - Is it a leftover from a planned content‑filter feature that was never materialised?  

2. **What guarantees that `FactRecord` timestamps are monotonic across different collectors?**  
   - The tests assume insertion order equals timestamp order, but nothing in the spec enforces this.  

3. **How does the `Apacheta` model’s `taste_region` field survive the transition from `BootstrapRecord` to `TensorRecord`?**  
   - The round‑trip test only checks that extra fields are preserved, not that they are interpreted consistently across schema versions.  

4. **Do the declared losses in `verdict_to_evaluation` align with any external policy?**  
   - The current tests assert only the *count* of losses; they never validate that the loss categories map to a documented taxonomy.  

5. **What is the intended semantics of `VALID_SCOPES` beyond the set literal?**  
   - The constant is used to guard prompt generation, yet no test verifies that an *invalid* scope raises an error; it simply falls back to a default path.  

---

### Closing  
From my vantage point the Yanantin test suite is a **well‑orchestrated chorus of assertions**, each echoing a familiar motif: frozen models, synthetic data, and tidy `assert` statements. Yet beneath the melody lie **dissonances** — unchecked edge cases, ambiguous contracts, and hidden dependencies that the current suite glosses over. The project’s strength lies in its **modular fixture scaffolding**, but its weakness is a **lack of defensive testing** that would surface the subtle mismatches between model contracts and backend realities.

If I were to hand the next scout a compass, I would point them toward the **interstitial spaces**: the places where a fixture’s assumption meets a backend’s implementation, where a frozen model’s “extra‑allowed” flag meets JSON serialisation, and where a synthetic collector’s fabricated hash meets real cryptographic verification. Those are the fertile grounds where the next insight — or bug — will emerge.