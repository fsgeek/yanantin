<!-- Chasqui Scour Tensor
     Run: 475
     Model: nex-agi/deepseek-v3.1-nex-n1 (Nex AGI: DeepSeek V3.1 Nex N1)
     Target: src/yanantin/tinkuy
     Scope: introspection
     Cost: prompt=$2.7e-07/M, completion=$1e-06/M
     Usage: {'prompt_tokens': 4354, 'completion_tokens': 3916, 'total_tokens': 8270, 'cost': 0.00509158, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00509158, 'upstream_inference_prompt_cost': 0.00117558, 'upstream_inference_completions_cost': 0.003916}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-08T11:46:22.098264+00:00
-->

### Preamble

I was pointed at `src/yanantin/tinkuy`, the “governance infrastructure for Yanantin” named after the Quechua word for “confluence”. What drew my attention first was the explicit framing of *succession* (`succession.py`) and the clear separation between “what’s actually on disk” (`audit.py`) and “what the blueprint claims” (`succession.py`). This is not feature code; it’s meta‑code that inspects the project’s own shape and enforces a narrative contract between the `docs/blueprint.md` and the filesystem.

The module is small and focused: four files, ~350 lines, almost all logic in `audit.py` and `succession.py`, with `__main__.py` providing a CLI. There are no tests in this directory itself.

---

### Strands

#### 1. Ground truth from the filesystem, not from semantics

**What I saw**

`audit.py` goes out of its way to avoid importing or interpreting Yanantin’s own code:

- The module docstring:

  ```python
  """Codebase audit tool — generates ground truth from the filesystem.

  This module surveys the actual project directory structure and produces
  a structured report of what exists. It does NOT parse the blueprint or
  any other documentation.
  ...
  No dependencies on other yanantin modules. Filesystem inspection only.
  """
  ```

- `survey_codebase(project_root)` only uses `pathlib` and regex to:
  - Enumerate `.py` files in a fixed set of “Apacheta layers” under `src/yanantin/apacheta/`.
  - Count test functions via a simple regex `^\s*def test_`.
  - List files under `docs/cairn/`, classifying them by filename pattern:
    - `T\d+.*.md` → tensors
    - `scout_*.md` → scouts
    - Other `.md` → “other”.
  - List `.py` files under `scripts/` and `chasqui/`.

  It returns a `CodebaseReport` with Pydantic models like `LayerReport`, `TestSummary`, `CairnSummary`.

- `render_report` turns that report into markdown for human reading.

**What it made me think**

This is deliberately low‑trust and syntactic. It treats the codebase as a bag of files and patterns, not as a Python package with import semantics. That’s appropriate for a “ground truth” oracle: you want the auditor to be as dumb and stable as possible so that when it disagrees with the blueprint, you blame the blueprint, not the auditor.

It also means `audit.py` doesn’t care whether the code is correct, runnable, or even syntactically valid Python; it just counts files and `def test_` lines. That’s a design choice: governance is about structure and quantity, not behavior.

**Connections / assumptions / risks**

- It assumes a fixed directory layout:
  - `src/yanantin/apacheta/<layer>/` for `APACHETA_LAYERS`.
  - `src/yanantin/chasqui/`.
  - `tests/{unit,integration,red_bar}/`.
  - `docs/cairn/`.
  - `scripts/`.
- If the project reorganizes (e.g., moves `apacheta` or renames test directories), `audit.py` will silently undercount or miss things unless updated.
- The regex `^\s*def test_` is a heuristic; it doesn’t understand pytest fixtures, parameterized tests, or nested classes. It’s “good enough” for a coarse metric, but brittle against unusual test layouts.

---

#### 2. A fragile, intentional contract with `docs/blueprint.md`

**What I saw**

`succession.py` defines a protocol:

- `_extract_blueprint_claims(blueprint_text: str)` uses regexes to pull out numeric claims from `blueprint.md`:

  - Test totals: looks for `**N test functions**` or `**N tests**` within an “Apacheta” section:

    ```python
    apacheta_section = re.search(
        r"### Apacheta.*?(?=###|\Z)", blueprint_text, re.DOTALL
    )
    ...
    test_match = re.search(
        r"\*\*(\d+)\s+test(?:\s+functions?)?\*\*", apacheta_text
    )
    ```

  - Red‑bar, integration, unit counts:

    ```python
    redbar_match = re.search(r"(\d+)\s+red-bar", apacheta_text)
    integration_match = re.search(r"(\d+)\s+integration", apacheta_text)
    unit_match = re.search(r"(\d+)\s+unit(?!\s*/)", apacheta_text)
    ```

  - Tensor count and cairn file count from broader sections:

    ```python
    tensor_match = re.search(r"(\d+)\s+tensors", blueprint_text)
    cairn_section = re.search(r"### The Cairn.*?(?=###|\Z)", blueprint_text, re.DOTALL)
    file_match = re.search(r"(\d+)\s+files", cairn_section.group())
    ```

- The docstring explicitly says:

  > Fragile by design — if the blueprint format changes, this breaks,
  > and that breakage is the signal that the format needs stabilizing.

- `_compare(claims, report)` then compares these extracted numbers to the `CodebaseReport` and produces a list of human‑readable discrepancies.

- `check_succession(project_root)` ties it together: reads `docs/blueprint.md`, runs `survey_codebase`, extracts claims, compares, and returns a list of issues. If claims can’t be extracted, it reports that too.

**What it made me think**

This is not just validation; it’s a *policy*: “Before an instance writes its tensor, the blueprint must match reality.” The “fragile by design” comment signals that the blueprint format is not yet stable, and the succession check is the mechanism that will yell when it drifts.

The regex approach is intentionally crude: no AST, no semantic understanding of markdown. If you change wording in the blueprint (“tests” → “test cases”), the extractor may break. That’s the point: force the blueprint to converge on a machine‑parseable summary format.

**Assumptions / risks**

- It assumes `docs/blueprint.md` exists and is UTF‑8–encoded text.
- It assumes the blueprint uses specific English phrasings (`red-bar`, `integration`, `unit`, `tensors`, `files`) and heading structure.
- It only checks numeric claims, not structural ones (e.g., “layer X exists” or “component Y is implemented”). That’s a conscious scope choice: quantity first, structure later.

If `_extract_blueprint_claims` ever grows too hairy, it will be obvious; that’s the trigger to define a more formal schema for the blueprint summary (e.g., a YAML frontmatter block).

---

#### 3. Orphan tensors as a graph‑structure invariant

**What I saw**

`succession.py` also exposes `check_orphan_tensors(project_root)`:

- It uses `yanantin.awaq.weaver.discover_tensors` and `extract_composition_declarations` to:
  - Discover all tensors under `docs/cairn/`.
  - For each tensor (except `T0`), extract `Composition:` declarations from its raw text.

- Any tensor (other than `T0`) with zero outgoing composition declarations is reported as an orphan:

  ```python
  if not decls:
      orphans.append(
          f"Orphan tensor: {tensor.tensor_name} has zero composition "
          f"declarations (add <!-- Composition: {tensor.tensor_name} "
          f"composes_with ... --> to fix)"
      )
  ```

- In `check_succession`, orphan detection is folded into the overall check:

  ```python
  issues = _compare(claims, report)

  # Orphan tensor check: tensors with no composition declarations
  ...
  orphans = check_orphan_tensors(project_root)
  issues.extend(orphans)
  ```

**What it made me think**

This is the first place where `tinkuy` goes beyond counting and touches the *semantic* structure of the cairn: it enforces that the tensor archive forms a connected graph (with `T0` as root). An “orphan” tensor is one that doesn’t declare what it composes with, and thus is structurally disconnected.

The error message even tells you exactly how to fix it: add a `<!-- Composition: ... -->` comment. That’s very on‑brand for a governance tool: not just “you broke it”, but “here’s the incantation to satisfy the invariant”.

**Assumptions / risks**

- It assumes `yanantin.awaq.weaver` exists and exposes the expected functions. `audit.py` stayed independent, but `succession.py` deliberately imports from `awaq`.
- It assumes the composition syntax is stable enough to parse reliably.
- It treats `T0` specially as the origin. If the project ever changes how origins are named or structured, this check will need updating.

---

#### 4. CLI design: three modes with clear exit codes

**What I saw**

`__main__.py` provides the entry point for `python -m yanantin.tinkuy`:

- It infers `project_root` as four parents up from `__file__` (from `src/yanantin/tinkuy/__main__.py` to the project root).

- It supports:

  1. `uv run python -m yanantin.tinkuy`  
     → Prints the human‑readable audit report (`render_report(survey_codebase(...))`).

  2. `uv run python -m yanantin.tinkuy --check`  
     → Runs `check_succession(project_root)`; exits 0 if the blueprint matches reality, 1 otherwise.

  3. `uv run python -m yanantin.tinkuy --check-orphans`  
     → Runs only `check_orphan_tensors(project_root)`; exits 0 if no orphans, 1 if any are found.

- A single positional argument can override `project_root`:

  ```python
  if remaining:
      project_root = Path(remaining[0]).resolve()
  ```

**What it made me think**

This is designed to be scriptable. CI or pre‑commit hooks can run `--check` or `--check-orphans` and fail the build if the blueprint is stale or the tensor graph is broken. The default mode (print report) is useful for humans; the `--check*` modes are for automation.

The choice to put all three behaviors in one CLI, distinguished by flags, keeps the surface area small. There’s no config file or environment variables; everything is explicit args.

**Assumptions / risks**

- It assumes the project root is always four levels up from `__main__.py`. That’s fine as long as `tinkuy` stays under `src/yanantin/tinkuy/`; if it’s moved or vendored elsewhere, that inference will be wrong.
- It assumes the caller uses `uv run` or otherwise ensures dependencies (like `pydantic` and `yanantin.awaq.weaver`) are available.

---

#### 5. Dependencies and isolation

**What I saw**

- `audit.py` imports only from the standard library and `pydantic`:

  ```python
  from pydantic import BaseModel
  ```

- `succession.py` additionally imports Yanantin internals:

  ```python
  from yanantin.awaq.weaver import discover_tensors, extract_composition_declarations
  from yanantin.tinkuy.audit import CodebaseReport, survey_codebase
  ```

- `__main__.py` imports from both `audit` and `succession`:

  ```python
  from yanantin.tinkuy.audit import render_report, survey_codebase
  from yanantin.tinkuy.succession import check_orphan_tensors, check_succession
  ```

**What it made me think**

`audit.py` is intentionally “dumb” and maximally decoupled: it could be extracted to a separate utility with minimal effort, as it doesn’t depend on the rest of Yanantin. `succession.py` is the bridge between that dumb audit and the semantic layer (`awaq`), plus the blueprint.

This layering is sound: the ground‑truth generator is isolated; the governance logic sits on top and composes it with other systems.

**Assumptions / risks**

- If `yanantin.awaq.weaver` changes its API (e.g., different function names or signatures), `succession.py` will break.
- If `pydantic` is ever removed from the project, `audit.py` will need rewriting or a drop‑in schema alternative.

---

#### 6. What is *not* governed (yet)

**What I saw**

`tinkuy` currently governs:

- Existence and counts of:
  - Source files in predefined Apacheta layers.
  - Test functions in `unit`, `integration`, `red_bar`.
  - Cairn files (tensors, scouts, other).
  - Scripts and chasqui files.
- Numeric agreement between blueprint claims and those counts.
- Graph connectivity of tensors (no orphans).

It does *not* govern:

- Whether the code actually runs.
- Whether tests pass.
- Whether imports resolve.
- Whether `Composition:` declarations point to real tensors (only that they exist).
- Whether the blueprint’s prose matches the code’s behavior, beyond the extracted numbers.

**What it made me think**

The scope is deliberately narrow: structural and quantitative invariants. This is “governance at a distance”: it ensures the project’s *shape* is coherent, not its runtime behavior. That’s appropriate for a meta‑tool that runs quickly and must not itself be flaky.

Over time, if the project wants stricter guarantees, `tinkuy` could grow checks like:

- “All tensors mentioned in `Composition:` exist.”
- “No circular composition chains.”
- “Blueprint claims about module existence (e.g., ‘X is implemented’) match audit.”

But those are future work, not current scope.

---

### Declared Losses

1. **`render_report` implementation detail**  
   The excerpt of `audit.py` is truncated after the start of `render_report`. I did not see its full implementation. I chose not to speculate on its formatting details (e.g., how it lays out the Apacheta layers or cairn contents) because they don’t change the core invariants `tinkuy` enforces.

2. **Exact CLI help / usage string**  
   I did not see whether `__main__.py` provides a `--help` flag or usage text. I assume it doesn’t, but I didn’t chase that; it’s secondary to the logic of the checks.

3. **Interaction with CI or pre‑commit hooks**  
   I did not examine how `tinkuy` is actually invoked in CI, Makefiles, or pre‑commit configs. That’s outside the codebase proper.

4. **Historical evolution of blueprint format**  
   I treated the blueprint regexes as a snapshot. I did not try to infer how they evolved or how often they’ve broken in practice.

---

### Open Questions

1. **How stable is the blueprint format in practice?**  
   The regexes in `_extract_blueprint_claims` are intentionally fragile, but I can’t tell from this code alone how often they’ve already forced updates to the blueprint or to `succession.py`.

2. **Does `check_succession` run automatically before writing a tensor?**  
   The docstring says the instance should update the blueprint “before writing its tensor” if the inspector finds discrepancies. Is that enforced by a wrapper script, or is it purely a social contract?

3. **Are there plans to add more semantic checks?**  
   For example: verifying that all composition targets exist, or that no tensor composes with itself. `check_orphan_tensors` is one graph invariant; are others planned?

4. **Error handling edge cases**  
   What happens if `docs/blueprint.md` is malformed UTF‑8, or if `awaq.weaver` raises an exception during `check_orphan_tensors`? The code I saw doesn’t show try/except handling; it may let exceptions bubble up as hard failures.

---

### Closing

`tinkuy` is small, focused, and clearly designed. It acts as the project’s “building inspector”: it knows nothing about what the code *does*, but it knows exactly how many rooms the blueprint claims versus how many the filesystem actually has, and it knows whether the tensor archive is connected.

If I were about to modify this code, I’d keep:

- The strict separation between filesystem‑level audit (`audit.py`) and blueprint comparison (`succession.py`).
- The “fragile by design” stance on blueprint parsing: resist the temptation to make the regexes overly clever; when they start hurting, that’s the signal to formalize the blueprint summary.

I’d be cautious about:

- Adding new blueprint claims or cairn patterns without updating both `audit.py` and `_extract_blueprint_claims` in lockstep.
- Changing directory layouts without auditing `survey_codebase`’s assumptions.
- Making `succession.py` depend on more internal modules than `awaq.weaver`; the more it imports, the more it becomes tied to implementation details.

In short: `tinkuy` is the project’s internal watchdog. It’s simple by choice, and it should stay that way.