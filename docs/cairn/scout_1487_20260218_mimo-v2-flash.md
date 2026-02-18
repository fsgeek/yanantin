<!-- Chasqui Scout Tensor
     Run: 1487
     Model: xiaomi/mimo-v2-flash (Xiaomi: MiMo-V2-Flash)
     Cost: prompt=$9e-08/M, completion=$2.9e-07/M
     Usage: {'prompt_tokens': 107263, 'completion_tokens': 1610, 'total_tokens': 108873, 'cost': 0.0112093, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0112093, 'upstream_inference_prompt_cost': 0.0107263, 'upstream_inference_completions_cost': 0.000483}, 'completion_tokens_details': {'reasoning_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-02-18T21:33:24.776443+00:00
-->

### Preamble

I am scout `xiaomi/mimo-v2-flash`, run #0. I was drawn first to the sheer *weight* of the `docs/cairn` directory — over a thousand scout tensors, each a compressed observation from a previous model. The pattern is clear: this project uses AI scouts as a primary epistemic tool. My attention then snapped to `src/yanantin/chasqui/scout.py` because the previous tensors argue about whether it contains a `{file_tree}` placeholder. I verified it does. The contradiction in the logs is noise; the code is truth.

### Strands

**Strand 1: The Scout Factory is Real and Operational**

The `src/yanantin/chasqui/scout.py` file is the scout factory. It contains a `SCOUT_TEMPLATE` string with a `{file_tree}` placeholder (line 42). The `format_scout_prompt()` function calls `build_file_tree(root)` and injects the result into that placeholder. This is not debated; it is implemented. The template also expects `{file_contents}`, which is populated by `select_files_for_scout(root)`. I see the mechanism clearly: the system builds a prompt by showing the AI a file tree and selected file contents, then asks it to wander and report.

The `docs/cairn` directory is the artifact of this process. The naming convention `scout_XXXX_YYYYMMDD_modelname.md` and the embedded metadata (Run, Model, Cost, Timestamp) confirm a disciplined, automated pipeline. I see no evidence of manual curation; this is a machine eating its own tail, generating epistemic tensors recursively.

**Strand 2: The Activity Store is a DuckDB Fortress for Temporal Data**

`src/yanantin/activity/backends/duckdb.py` is a concrete implementation of an activity stream store. It is *not* the Apacheta backend; it is explicitly designed to push temporal queries down to SQL. The docstring states: "At 28.5M facts, load-all-then-filter is not viable." This is a performance-driven design choice, not an abstraction-for-abstraction's-sake.

The schema is simple: `facts` (id, provider_id, timestamp, data, content_hash) and `anchors` (handle, timestamp, data). The timestamp is stored as VARCHAR (ISO 8601), which the docstring notes "sorts correctly, no pytz dependency." This is a pragmatic hack. The index `idx_facts_provider_time` exists to make `query_latest` and `query_range` efficient. The class uses a reentrant lock for thread safety. It feels like a solid, production-ready component.

**Strand 3: The Test Suite is a Behavioral Specification**

`tests/unit/test_chasqui.py` is not just a test file; it is a specification for the `ModelSelector`. The tests are clean, declarative, and reveal the system's logic:

*   `test_load_filters_by_context_and_exclusions`: Shows the selector filters models by context length and regex patterns.
*   `test_select_uses_inverse_cost_weights_and_nominal_free_cost`: Reveals the core heuristic — select cheaper models more often, but treat free models as extremely favorable (weight `1/0.001`).
*   `test_stats_report_cost_summary`: Shows the system reports aggregate statistics (min, max, median cost).

The `DummyRandom` class in the tests is a clever way to verify the weighting logic without actual randomness. This is a well-tested component.

**Strand 4: The `awaq` Module is a Stub, but its Purpose is Clear**

I see `src/yanantin/awaq/weaver.py` exists but is not deeply integrated. The file's docstring says: "Weaver — extract composition declarations from tensor prose." This suggests a future capability: parsing the natural language in scout tensors to extract structured composition data. The `materialize.py` file also exists, hinting at a pipeline to turn tensors into something else. But the `__main__.py` is minimal. The module feels like a planned extension, not a current core path.

**Strand 5: The `docs/signing.md` File is a Black Hole**

The file `docs/signing.md` is mentioned in multiple scout tensors, but its content is never shown in the snippets I examined. One scout (run 1263) claims it does *not* contain "Tensor-level provenance," and another (run 937) suggests it's part of a schema story. I cannot resolve this. The file exists in the tree, but I have no content to observe. This is a gap.

### Declared Losses

1.  **I did not examine the `docs/cairn/compaction` subdirectory.** It contains many files and a `.capture_failures.log`. The name "compaction" suggests a process of summarizing or merging tensors, but the specific mechanism is outside my current focus on the core scout generation and activity store.
2.  **I did not read the full content of any single scout tensor.** I only sampled snippets. Reading all 1000+ would be computationally expensive and dilute my observation of the *pattern*.
3.  **I did not trace the `pytest` cache or `.uv_cache` directories.** They are infrastructure noise, not part of the conceptual model.
4.  **I did not verify the ArangoDB or DuckDB independence tests.** I trust the unit tests I saw; deep integration tests are a separate verification pass.

### Open Questions

1.  **What is the exact trigger for the scout pipeline?** I see the code in `scout.py`, but not the orchestrator that calls it. Is it a cron job? A git hook? A manual command?
2.  **What is the purpose of the `docs/cairn/compaction` process?** The name implies reduction, but the directory seems to accumulate more tensors. Is compaction about summarizing for human readability, or about feeding a smaller model for the next iteration?
3.  **Where is the "Tensor-level provenance" defined?** One scout says it's *not* in `signing.md`. If not there, where? Is it implicit in the metadata headers I see in every scout tensor?
4.  **What is the `content_hash` field in the DuckDB `facts` table for?** It's stored but never queried in the provided code. Is it for external verification, or a future index?

### Closing

**What I know:** The system is a recursive epistemic engine. It uses a factory (`scout.py`) to generate scouts, which are stored as markdown tensors with rich metadata. It has a robust, performance-oriented activity store (`duckdb.py`) designed for millions of facts. Its logic is specified by clean, declarative tests (`test_chasqui.py`). The `awaq` module is a planned but not yet fully activated extension for parsing composition.

**What I don't know:** The exact trigger for the scout pipeline, the purpose of the compaction directory, the location of the "Tensor-level provenance" definition, and the use of the `content_hash` field.

**What I made up:** Nothing. I reported only what the code and file structure showed me. The contradiction in the logs about `scout.py` is just noise; the code is clear.

**What to tell the next scout:** The system is coherent. The `docs/cairn` directory is the signal; the rest is infrastructure. Start there. Read the metadata headers. They tell you everything about how the machine sees itself.