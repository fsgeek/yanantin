<!-- Chasqui Scout Tensor
     Run: 12550
     Model: openai/gpt-oss-safeguard-20b (OpenAI: gpt-oss-safeguard-20b)
     Cost: prompt=$7.5e-08/M, completion=$3e-07/M
     Usage: {'prompt_tokens': 10838, 'completion_tokens': 3021, 'total_tokens': 13859, 'cost': 0.00171915, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00171915, 'upstream_inference_prompt_cost': 0.00081285, 'upstream_inference_completions_cost': 0.0009063}, 'completion_tokens_details': {'reasoning_tokens': 954, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-10T06:40:17.051867+00:00
     GenerationID: gen-1778395213-BLQHJfo63ff10xE5l7R0
-->

**Preamble**  
I landed in the `tests/unit/` tree, a living museum of the project’s public contracts. The first thing that snagged my eye was the sheer breadth of *domain‑specific* tests: a tensor‑oriented configuration engine, a “memory anchor” service that seems to be a lightweight snapshot mechanism, and a “Jabberwock” model layer that mixes time‑zone gymnastics with Pydantic validation. The tests are not just smoke‑tests; they encode non‑obvious invariants (e.g., a “T8” tensor is deliberately omitted, a “checksum” fact carries only a 16‑char SHA‑256 prefix). This tells me the codebase is designed for *observability* and *data‑driven evolution* rather than a monolithic API.

---

### Strands

| Theme | What I saw | Why it matters | Lines / files |
|-------|------------|----------------|--------------|
| **Coverage‑based prioritisation** | `scan_cairn_coverage` parses Markdown scout reports for file paths, keeps the *latest* timestamp per file, and returns a map. `coverage_weights` then gives an *epoch‑zero* weight to unreviewed files and a *seconds‑since‑last‑review* weight otherwise. The test expects the unreviewed weight to be *>100×* the recent one. | This is a classic “review‑ahead” heuristic. It assumes that the most urgent files are those never seen, but it also treats all “old” reviews as equally stale. The choice of epoch‑zero as a sentinel is a bit risky: if a file was actually reviewed at the Unix epoch (unlikely but possible in a toy repo), it would get the same weight as an unreviewed file. | `tests/unit/test_coverage.py` (lines 1‑120) |
| **Tensor name normalisation** | `normalize_tensor_name` converts Unicode subscripts (`T₀₁₂`), LaTeX‐style subscripts (`T_{12}`), and plain `T0` into a canonical form. It also leaves non‑tensor strings untouched. The companion `extract_tensor_name_from_path` handles both modern `T15_20260212_…` and legacy `conversation_tensor_…_t3.md` patterns. | The system seems to be built around a *label* that is both human‑readable (`T12`) and machine‑sortable. The legacy mapping (T0 ↔ conversation_tensor_20260207.md, T1 ↔ …_session2.md, etc.) suggests a historical evolution of the documentation workflow. The fact that `T8` is absent indicates a deliberate gap, perhaps for a future feature or a placeholder. | `tests/unit/test_awaq_weaver.py` (lines 1‑200) |
| **Composition declarations** | `extract_composition_declarations` returns `CompositionDeclaration` objects with `relation`, `targets`, `confidence`, etc. The tests check that “composes_with” produces a normal edge, “does_not_compose_with” produces a negation, and “bridges” produces a bridge edge. | The design mirrors a graph‑theoretic view of knowledge: tensors are nodes, declarations are typed edges. The presence of *negation* edges is a subtle hint that the system is ready for *contradiction* tracking, not just positive assertions. | `tests/unit/test_awaq_weaver.py` (lines 200‑400) |
| **Fact recorders and synthetic collectors** | Three collector types (`SyntheticFilesystemCollector`, `SyntheticChecksumCollector`, `SyntheticFsEventCollector`) each produce deterministic data streams. The corresponding fact recorders (`FilesystemFactRecorder`, `ChecksumFactRecorder`, `FsEventFactRecorder`) store one fact per entry, with timestamps taken from the source (modified time, collected_at, detected_at). `ChecksumFactRecorder` stores a 16‑char hash. | The use of deterministic seeds shows the code is meant for *unit‑test reproducibility*. The 16‑char prefix is a pragmatic trade‑off: it’s short enough for logs but still derived from a cryptographic hash. | `tests/unit/test_fact_recorders.py` (lines 1‑200) |
| **Jabberwock models** | Pydantic models enforce UTC timestamps, reject naive datetimes, allow unknown fields for persistence, and auto‑generate UUIDs. `Tove` is an alias that can be *mome* (unresolved) if `jabberwock_id` is None. | These models are a micro‑domain of *identity* and *time‑sensitivity*. The “mome” concept suggests a lazy resolution mechanism (e.g., a user might be referenced before the user record exists). The “extra_allow” policy is a forward‑compatibility guard. | `tests/unit/test_jabberwock_models.py` (lines 1‑400) |
| **Memory anchor service** | The service exposes a “handle” that must be *referenced* (via `get_handle()`) and *updated* (via `update_cursor()`) before `flush()` will store an anchor. After flushing, the handle advances and flags reset. `materialize()` must include providers registered *after* the anchor was created, indicating a *late‑binding* strategy. | This is a lightweight snapshot system: you can write facts, then take an anchor that captures the current state. The gate logic (both flags required) is a simple but effective way to avoid accidental empty anchors. The “late binding” test hints that the service keeps a registry of providers that may not yet be known at anchor time. | `tests/unit/test_memory_anchor.py` (lines 1‑200) |
| **Configuration tensors** | `ConfigTensor` objects are converted to `TensorRecord`s with tags like `"config"` and `"chasqui.pulse"`. The round‑trip uses `ast.literal_eval` to preserve type fidelity. `store_config` persists the tensor; `get_current_config` fetches the latest by domain; `get_config_history` returns a newest‑first list. | Storing configs as tensors allows the system to treat configuration changes as first‑class data, enabling temporal queries and audit trails. The test that `T8` is missing in the corpus but still recognized by `discover_cairn_tensors` shows that the discovery logic is tolerant of gaps. | `tests/unit/test_config_tensors.py` (lines 1‑200) |
| **Garbage claim detection** | `is_garbage` heuristics filter out CJK noise, encoding artifacts, short messages, low alpha ratio, and other patterns. `is_verification_meta` recognises “Verdict …” or “Evidence shows …” as meta‑claims. | These heuristics show a *text‑analysis* layer that must separate meaningful claims from noise. The regexes likely rely on Unicode ranges and word counts, which can be brittle if the language shifts. | `tests/unit/test_analyst.py` (lines 1‑200) |

---

### Declared Losses

I deliberately avoided digging into the actual implementation files (`yanantin/...`) because the tests already expose the public contracts. I also skipped the `test_tinkuy_*` and `test_duckdb_*` suites; their patterns are similar to those above (database backends, audit trails) and would not add new themes. Instead, I focused on the *observable* behaviors that the tests enforce.

---

### Open Questions

1. **Weight calculation** – Does `coverage_weights` simply subtract timestamps or use a more complex decay function? The tests only check relative magnitude, not absolute values.  
2. **Legacy tensor mapping** – The `extract_tensor_name_from_path` logic for `conversation_tensor_20260208_t5.md` → `T5` is hard‑coded; is there a canonical rule or a mapping table?  
3. **Negation handling** – How does `declarations_to_edges` distinguish between a *negation* and a *missing* declaration? Is there a domain‑specific semantics for “does_not_compose_with”?  
4. **Late‑binding in MemoryAnchor** – What is the performance cost of resolving all providers at `materialize()`? Does it iterate over the entire provider registry each time?  
5. **Configuration history ordering** – The test expects newest‑first; is this enforced by sorting on `timestamp` or by insertion order?  
6. **Hash truncation** – Why 16 chars? Is there a risk of collisions in a large dataset?  

---

### Closing

The codebase is a *tensor‑centric* observability stack: each file, claim, or configuration change is treated as a first‑class data object. The tests reveal a careful balance between **forward compatibility** (allowing unknown fields) and **strictness** (rejecting naive times, ensuring UUID uniqueness). The naming conventions (subscript, LaTeX, legacy) hint at a long‑running project that has evolved from plain Markdown to a structured tensor taxonomy. The “anchor” pattern shows a commitment to *temporal consistency* without a heavyweight database transaction system.

For the next scout:  
- Verify that the `normalize_tensor_name` regex covers all edge‑cases (e.g., `T_{01}` or `T_12_`).
- Inspect the `CoverageReport` format to see how unreviewed vs. reviewed files are presented—does it expose a UI or only a CLI?
- Check how `MemoryAnchorService` interacts with `InMemoryActivityStreamStore` under concurrent writes; the flag logic seems fragile in multi‑threaded contexts.  

This snapshot suggests a mature, data‑oriented design but also a few spots where the assumptions (epoch‑zero, 16‑char hash, legacy naming) could bite if the system scales or changes its data model.