<!-- Chasqui Scour Tensor
     Run: 267
     Model: qwen/qwen3-next-80b-a3b-thinking (Qwen: Qwen3 Next 80B A3B Thinking)
     Target: src/yanantin/awaq
     Scope: introspection
     Cost: prompt=$1.5e-07/M, completion=$1.2e-06/M
     Usage: {'prompt_tokens': 4878, 'completion_tokens': 6001, 'total_tokens': 10879, 'cost': 0.0097332, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'audio_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0097332, 'upstream_inference_prompt_cost': 0.0007317, 'upstream_inference_completions_cost': 0.0090015}, 'completion_tokens_details': {'reasoning_tokens': 3788, 'audio_tokens': 0}}
     Timestamp: 2026-02-28T18:05:49.166459+00:00
-->

### Preamble  
I was directed to examine `src/yanantin/awaq`, a module within the Yanantin project focused on "extracting composition declarations from tensor prose." The first thing that drew my attention was the explicit design philosophy in `weaver.py`’s docstring: *Deterministic: regex and keyword matching only, no LLM calls. Conservative by design: only extracts declarations where the text clearly states composition intent.* This stands out because it prioritizes reliability over creativity—critical for epistemic observability where false positives could corrupt the knowledge graph. The structured metadata parsing (`<!-- Composition: ... -->`) and regex for tensor references (`T₀`, `T_1`, etc.) seemed like the core nervous system of the system.  

---

### Strands  

#### **1. Deterministic Extraction via Regex and Structured Comments**  
- **What I saw**:  
  - `weaver.py` uses meticulously crafted regex patterns (`_TENSOR_REF`, `_STRUCTURED_METADATA`) to avoid false positives. For example:  
    - `(?<!\w)T(?:[₀₁₂₃₄₅₆₇₈₉]+|_\{?\d+\}?|\d+)(?![_\w])` ensures "T0" in "T0x" isn’t matched.  
    - `_FENCED_CODE_BLOCK` (truncated but referenced) strips code blocks before processing to ignore examples like `T18 proposing the format`.  
  - `normalize_tensor_name` standardizes `T₀` → `T0`, `T_{12}` → `T12`, `T_0` → `T0`. This is robust for diverse notation styles.  
  - Only `<!-- Composition: ... -->` comments trigger extraction—no prose-based inference. The `KNOWN_RELATIONS` set (`composes_with`, `corrects`, etc.) is minimal and explicit.  
- **What it made me think**:  
  - This is *by design* to avoid hallucinations. If a tensor’s prose says "T15 might compose with T17," it’s ignored. Only clear, structured declarations count.  
  - **Assumption**: Authors will consistently use `<!-- Composition: ... -->` for declarations. If they don’t, nothing is extracted—no fallback to LLMs. This makes the system brittle for unstructured input but trustworthy for curated content.  
  - **Risk**: If a tensor’s metadata is misformatted (e.g., `<!-- Composition: T15 composes_with T16 -->` vs. `<!--Composition:T15...-->`), it fails silently. No logging for malformed comments.  

#### **2. Materialization Pipeline: Abstracting Backends with Rigor**  
- **What I saw**:  
  - `materialize.py` maps Awaq’s `CompositionDeclaration` (e.g., `"composes_with"`) to Apacheta’s `RelationType` via `_RELATION_MAP`. Notably:  
    - `"read"` maps to `RelationType.COMPOSES_WITH`—implying "reading" is treated as a compositional relationship.  
    - `"standalone"` and `"does_not_compose_with"` create negation records (no edges), not edges.  
  - `discover_cairn_tensors` only scans `T[0-9]*_*.md` files in `cairn_dir`. Labels are extracted from filenames (e.g., `T15_notes.md` → `T15`).  
  - `ensure_tensors_stored` handles immutability errors gracefully—if a tensor already exists, it reuses its UUID.  
- **What it made me think**:  
  - The abstraction (`ApachetaInterface`) is clean. In-memory vs. Pukara gateway is switched via `--backend`, which is pragmatic for testing.  
  - **Assumption**: All tensor references will be present in `cairn_dir` or `ai-honesty` sources. If a declaration references a tensor not in these sources (e.g., `T99`), it’s skipped as "unknown." No automatic import of missing tensors.  
  - **Risk**: If a tensor exists in the backend but isn’t in `cairn_dir` (e.g., manually imported), `discover_cairn_tensors` won’t find it. The label-to-UUID map could miss it, causing declarations to fail.  

#### **3. CLI Design: Modes for Debugging and Deployment**  
- **What I saw**:  
  - `__main__.py` offers `--tensor T15` (show declarations for one tensor), `--json`, `--list`, and `--materialize`.  
  - `--materialize` defaults to in-memory dry-run (`InMemoryBackend`), safe for testing. Production uses `ApachetaGatewayClient` with `PUKARA_URL` env var.  
  - Tensor names are normalized to uppercase (e.g., `t15` → `T15`), avoiding case-sensitivity issues.  
- **What it made me think**:  
  - The CLI is intentionally simple—no complex config, just core operations. This matches the project’s "observability-first" ethos.  
  - **Assumption**: Users will run `--materialize` in production only when `PUKARA_URL` is set. But there’s no validation—if `PUKARA_URL` is unset, it defaults to `127.0.0.1:8000`, which might fail silently if Pukara isn’t running.  
  - **Missing**: No `--verbose` flag for debugging materialization errors. If a tensor fails to store, the only output is `logger.error` (not visible without log config).  

#### **4. Path Hardcoding and Project Structure Assumptions**  
- **What I saw**:  
  - In `weaver.py` and `__main__.py`, paths like `PROJECT_ROOT = Path(__file__).resolve().parents[3] / "docs" / "cairn"` are hardcoded.  
  - This assumes the project structure:  
    ```  
    yanantin/  
      src/yanantin/awaq/...  
      docs/cairn/...  
    ```  
- **What it made me think**:  
  - This is fragile. If the project is moved or built in a Docker container with a different hierarchy, paths break.  
  - **Better approach**: Use config files or environment variables (e.g., `CAIRN_DIR` env var) for path resolution. Hardcoding relative paths to `__file__` is common but error-prone in distributed systems.  

---

### Declared Losses  
- **I did not examine**:  
  - The full `weaver.py` (656+ lines truncated). Specifically, what happens after `extract_structured_metadata`—is there prose-based extraction for non-structured declarations? The docstring says "regex and keyword matching only," but the truncated code might include it.  
  - `render_graph` and `render_json` implementations in `weaver.py`—how the composition graph is visualized or serialized.  
  - The `ApachetaBackend` internals (e.g., `InMemoryBackend`, `ApachetaGatewayClient`). These are outside `awaq`’s scope but critical for materialization.  
- **Why**:  
  - My assignment was strictly `src/yanantin/awaq`. The backend interfaces (`apacheta/*`) are separate modules.  
  - Truncated code in `weaver.py` means I can’t assess the full extraction logic—only what’s visible.  

---

### Open Questions  
- **Why is `"read"` mapped to `COMPOSES_WITH`?**  
  In `_RELATION_MAP`, `"read"` is treated identically to `"composes_with"`. Is this intentional? Should `"read"` imply a different relation type (e.g., `RelationType.READS`)? The naming suggests it might be a separate edge type.  
- **How are circular dependencies handled?**  
  If `T15 composes_with T16` and `T16 composes_with T15`, does the system detect cycles? The materialization code doesn’t seem to check for this—could it break the graph?  
- **What is `_FENCED_CODE_BLOCK`?**  
  In `weaver.py`, it’s referenced in `extract_structured_metadata` to strip code blocks, but it’s not defined in the provided snippet. Is it a global regex? If not, this would cause a `NameError`.  
- **Why no logging for malformed structured comments?**  
  If `<!-- Composition: T15, invalid >>` is in a file, nothing is extracted—but no warning is logged. This could lead to silent failures in production.  

---

### Closing  
This part of the codebase is **reliability-focused and intentionally minimalist**. It’s not trying to be clever—it’s a surgical tool for extracting explicit compositional relationships from text. The deterministic regex and structured comments ensure no hallucinations, which is perfect for epistemic observability. However, it’s brittle in practice:  
- **Strengths**: Clean abstraction for backends, robust tensor normalization, and CLI simplicity.  
- **Weaknesses**: Hardcoded paths, silent failures for malformed declarations, and assumptions about tensor availability (e.g., all tensors must be in `cairn_dir`).  

**If someone modifies this**:  
- **Don’t change the regex unless absolutely necessary**—it’s tuned for precision. Test edge cases like `T0x` or `T123a`.  
- **Replace hardcoded paths with environment variables**. A single `CAIRN_DIR` env var would make deployment safer.  
- **Add explicit logging for failures** (e.g., "Malformed structured comment at line X"). Silent errors are the enemy of observability.  
- **Clarify relation semantics**: Why is `"read"` treated as `COMPOSES_WITH`? Document this in `_RELATION_MAP`.  

> **What I know**: The code is conservative, well-structured for its purpose, and avoids LLMs for reliability.  
> **What I don’t know**: The full `weaver.py` logic, backend details, and how circular references are handled.  
> **What I made up**: None. I explicitly noted limitations of the truncated code and made no assumptions beyond what was visible.