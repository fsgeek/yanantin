<!-- Chasqui Scout Tensor
     Run: 8419
     Model: openai/gpt-oss-safeguard-20b (OpenAI: gpt-oss-safeguard-20b)
     Cost: prompt=$7.5e-08/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 9327, 'completion_tokens': 3274, 'total_tokens': 12601, 'cost': 0.001681725, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.001681725, 'upstream_inference_prompt_cost': 0.000699525, 'upstream_inference_completions_cost': 0.0009822}, 'completion_tokens_details': {'reasoning_tokens': 1525, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-28T11:04:27.327549+00:00
     GenerationID: gen-1774695864-s23NMtAtnMsxPOlafZy1
-->

**Preamble**  
I landed in the `tests/unit/` tree, which is a dense map of expectations for the rest of the codebase. The first thing that drew my eye was the sheer breadth of the test‑suite: from low‑level Pydantic models to a CLI that prints machine fingerprints, to a synthetic Dropbox generator that guarantees deterministic content hashes. The tests are written in a very “behaviour‑driven” style, so they expose the public contract of each component without revealing implementation details. That makes the tests a perfect proxy for the design intent.

---

### Strands

| Theme | What I saw | What it made me think |
|-------|------------|------------------------|
| **Tensor naming & legacy migration** | `tests/unit/test_awaq_weaver.py` shows `normalize_tensor_name` handling Unicode subscripts, LaTeX style subscripts (`T_{12}`), and plain names. `extract_tensor_name_from_path` parses modern `T15_20260212_...` and legacy `conversation_tensor_20260207_session2_t6.md` patterns. | The system is built around a “tensor” abstraction that started as a simple `T0` sequence but now must tolerate a variety of naming conventions. The tests imply that a migration layer is in place, and that the code must be resilient to future naming changes. |
| **Coverage‑based prioritisation** | `test_coverage.py` verifies that `scan_cairn_coverage` pulls file refs from markdown comments, keeps the latest timestamp per file, and that `coverage_weights` assigns a huge weight to unreviewed files. | The project treats “coverage” as a first‑class metric: unreviewed files get a weight ~1.77 B seconds (epoch 0), while recently reviewed ones get ~1 second. This suggests an intention to surface the most stale parts of the codebase to the AI. |
| **Prompt construction** | `test_scourer.py` tests `format_scour_prompt` for four scopes (`introspection`, `external`, `tensor`, `synthesis`). The system prompt is constant; the user message varies with the target (file, directory, or tensor). | The scout module is a thin wrapper that turns local file contents or existing tensors into a prompt for a LLM. The design is modular enough to switch scopes without touching the core logic. |
| **Synthetic Dropbox API** | `test_collector_dropbox.py` exercises `SyntheticDropboxCollector`. It guarantees deterministic `content_hash` (64‑char SHA‑256), `rev` strings, and a cursor that starts with `synthetic_cursor_`. | The synthetic collector is a lightweight test harness that mimics the real Dropbox SDK. By seeding the random generator, the same listing can be reproduced, which is crucial for reproducible tests. |
| **CLI machine‑config reporting** | `test_collector_cli.py` calls `python -m yanantin.collector` and expects a banner, JSON output with a set of machine‑specific keys, and a UUID when recording. | The collector is a thin wrapper that gathers system metadata (hostname, os, cpu, etc.) and optionally records a “tensor” in a local store. The fact that the CLI prints two JSON documents in `--json --record` mode indicates a simple, concatenated protocol. |
| **Precompact hook** | `tests/unit/test_precompact_hook.py` imports a hook from `~/.claude/hooks/precompact_tensor.py`. It tests scanning a JSONL session file for user and tool messages, extracting user text, tool uses, counting tokens, and formatting a new markdown tensor. | This hook is a bridge between a local LLM (Claude) and the tensor infrastructure: it consumes a chat log and compacts it into a single tensor file. The design is deliberately minimal (stdlib‑only), suggesting it must run in constrained environments. |
| **Apacheta data model** | `test_models.py` validates Pydantic models (`ApachetaBaseModel`, `ProvenanceEnvelope`, `EpistemicMetadata`, etc.). It checks default values, immutability, and round‑trips. | The data model is heavily typed and frozen, ensuring that once a tensor is created, its metadata cannot be mutated. The presence of `DisagreementType` and `NegationRecord` hints at a system that tracks conflicting or negated knowledge. |
| **Coverage‑weight calculation** | In `test_coverage_weights_unreviewed_gets_maximum_weight`, the weight for an unreviewed file is compared to the weight for a file reviewed one hour ago. The test uses `pytest.approx` and asserts the unreviewed weight is >100× the reviewed one. | The weighting scheme is a simple linear mapping from elapsed seconds to priority. The test suggests a design choice: unreviewed files should dominate the queue, but reviewed files still remain visible. |

---

### Declared Losses

* **Implementation details of `scan_cairn_coverage`** – I did not examine the regex that pulls file refs or how timestamps are parsed.  
* **Exact token‑counting algorithm in the precompact hook** – the tests reference `_quick_count` and `_detailed_scan`, but no concrete implementation is visible.  
* **Internal structure of the synthetic Dropbox generator** – beyond the public API, the algorithm that decides shared vs. non‑shared, file size distribution, and revision strings is unknown.  
* **How the CLI decides what “record” means** – is it writing to a local database, uploading to a remote, or just printing a UUID? The tests only check the output, not side‑effects.  

These are intentional losses: the test suite focuses on surface behaviour, not on hidden internals.

---

### Open Questions

1. **How does `format_scour_prompt` embed file contents for large directories?**  
   The test only checks that the content appears in the user message, but no size limits are asserted. Does it chunk or truncate?  

2. **What is the semantics of `SCOPE` values in the scout?**  
   The tests assert that the system prompt is constant, but the user message changes. Are there additional hidden scopes (e.g., `analysis`)?  

3. **How is the `EPOCH_ZERO` defined?**  
   The tests compare against a hard‑coded timestamp `2026‑02‑18T10:00:00+00:00`. Is `EPOCH_ZERO` simply `datetime(1970,1,1)`?  

4. **What happens if two reports reference the same file with conflicting timestamps?**  
   The test checks the latest timestamp, but does the system warn or merge?  

5. **What is the contract of the synthetic Dropbox collector’s `collect_batch` method?**  
   It returns a list of `DropboxListing`s, but how is the batch size interpreted relative to the total entries?  

6. **Does the precompact hook support nested sessions or multiple concurrent users?**  
   The test only uses a single `session.jsonl`.  

7. **Are there any concurrency safeguards in `claim_tensor_number`?**  
   The function is imported from the hook; the test only checks sequential claims.  

8. **Is the `ApachetaBaseModel` using Pydantic v2 or v1?**  
   The tests refer to `model_dump(mode="json")`, which is a v1 style; but the `model_validate` API is v2. This mix could be a source of subtle bugs.  

---

### Closing

The test suite paints a picture of a system that treats “tensors” as first‑class artefacts of a human‑AI partnership. Naming conventions, coverage metrics, and synthetic data generators all point to a design that must be robust to evolving file structures and external APIs. The heavy use of immutable Pydantic models and deterministic synthetic data shows a focus on reproducibility and auditability.  

For the next scout, focus on the implementation of the coverage parsing regex and the token‑counting logic in the precompact hook. Those are the most fragile and least documented parts. Also, explore the CLI’s side‑effects: where does a “recorded” tensor actually live? Is there a database or a simple file store? Understanding those will clarify how the system moves from a local snapshot to a persistent knowledge graph.