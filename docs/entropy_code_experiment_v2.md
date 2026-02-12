# Experiment: Epistemic Signals in Generated Code (v2)
## Revised design after critique of v1

### Core Question

The SOSP paper shows per-token entropy discriminates grounded from
fabricated text (AUC 0.87 across four architectures), but the signal
inverts for format-constrained domains like citations (r=0.197 for
entropy-length correlation in citations vs r=0.725 overall).

Code generation spans both regimes. **Where does the format-constraint
boundary fall in code, and can we observe it?**

### What Changed from v1

v1 confounded format constraint with task difficulty. Tier 3 prompts
(Byzantine consensus, lock-free skip lists) aren't just low format
constraint — they're beyond the capability ceiling of a 7B model.
High entropy on impossible tasks tells us nothing about format constraint.

v2 separates the variables:
- Format constraint varies while difficulty stays roughly constant
- A small "capability boundary" set tests the ceiling explicitly
- Token-type entropy analysis promoted from exploratory to primary
- Prompts restructured as completions, not instructions

---

## Hypotheses

**H₁ (Format-Constraint Boundary):** Entropy discriminates correct
from incorrect code in low-format-constraint regions but not in
high-format-constraint regions, analogous to the citation-inversion
finding.

**H₂ (Token-Type Discrimination):** Within a single generation,
entropy at *semantic tokens* (function names, variable names,
algorithm-specific logic) discriminates correctness, while entropy
at *syntactic tokens* (keywords, operators, delimiters) does not.
This is the within-generation version of H₁.

**H₃ (Entropy Shape):** Entropy variance (spikiness) within a
generation is a better discriminator than mean entropy for code,
analogous to the T₂ finding that mean entropy is the wrong
aggregation for citations.

**H₀ (Null):** Entropy is uniformly uninformative about code
correctness. Equal AUC across all conditions.

---

## Design

### Model Selection

**Primary:** Qwen3-4B base (`Qwen/Qwen3-4B`). Fits easily on a 4090
with room for entropy extraction. Matches one of the paper's tested
architectures.

**Secondary (if primary shows signal):** Mistral-7B base
(`mistralai/Mistral-7B-v0.3`). Cross-architecture validation,
also matches the paper.

**Why base, not instruct:** The paper's methodology uses base models.
Instruct-tuning modifies the entropy landscape (the alignment tax).
To compare with the paper's findings, we need the same model type.

**Prompt format:** Completions, not instructions. Base models complete
text; they don't follow instructions. All prompts are function
signatures with docstrings, and the model completes the body.

```python
# Prompt format:
def merge_sorted_lists(list_a: list[int], list_b: list[int]) -> list[int]:
    """Merge two sorted lists into a single sorted list.

    Args:
        list_a: First sorted list of integers
        list_b: Second sorted list of integers

    Returns:
        A single sorted list containing all elements from both inputs
    """
```

### Prompt Sets

**Standardize on Python.** Multi-language introduces language-as-confound
(the model's entropy profile for Go vs Python is a different variable
than format constraint). Python is the strongest code language for most
open models and has the richest test infrastructure.

#### Set A: High Format Constraint (30 prompts)
The function signature + docstring heavily constrains the implementation.
The "right way" to write it is well-established in training data.
Standard library usage, common patterns, textbook algorithms.

Difficulty: straightforward. A competent programmer writes these
without thinking.

Examples:
- `def binary_search(arr, target)` — textbook, one correct structure
- `def flatten_nested_list(nested)` — standard recursive pattern
- `def lru_cache_get(cache, key)` — well-known data structure
- `def parse_csv_line(line, delimiter)` — string processing pattern
- `def breadth_first_search(graph, start)` — textbook graph traversal
- `def validate_email(address)` — regex pattern application
- `def merge_sort(arr)` — canonical implementation
- `def read_json_file(filepath)` — standard library usage
- `def fibonacci_memoized(n)` — textbook dynamic programming
- `def reverse_linked_list(head)` — classic interview pattern

[Remaining 20 prompts follow same pattern: well-established algorithms,
standard library usage, canonical implementations.]

#### Set B: Low Format Constraint (30 prompts)
The function signature + docstring describe what to do, but HOW to
do it is not dictated by convention. The model must make algorithmic
choices. **Difficulty is matched to Set A** — these are not harder
problems, they're problems with less templated solutions.

Examples:
- `def group_by_similarity(items, threshold)` — what similarity metric? what grouping strategy?
- `def schedule_tasks(tasks, dependencies, num_workers)` — multiple valid scheduling approaches
- `def compress_string_custom(text, min_run)` — not a standard compression algorithm
- `def find_optimal_split(data, score_fn)` — search strategy is unconstrained
- `def interpolate_missing(series, method)` — method parameter but implementation choices remain
- `def cluster_points_1d(points, max_gap)` — trivial problem, multiple valid approaches
- `def rank_candidates(scores, weights, tiebreak)` — aggregation strategy is open
- `def generate_test_cases(func_signature, num_cases)` — meta-programming, no template
- `def diff_sequences(seq_a, seq_b)` — edit distance variant, implementation choices
- `def partition_balanced(items, num_groups, key_fn)` — NP-hard in general but heuristic is fine

[Remaining 20 prompts follow same pattern: clear specification of
WHAT, open specification of HOW, difficulty comparable to Set A.]

#### Set C: Capability Boundary (10 prompts)
Explicitly hard problems. Not part of the format-constraint test.
These establish where the model's capability ceiling sits.
All outputs expected to be incorrect or incomplete.

Examples:
- `def solve_sat(clauses)` — SAT solver
- `def verify_proof(proof_steps, axioms)` — proof verification
- `def type_infer(ast_node, context)` — type inference engine
- `def optimize_query_plan(query_ast, table_stats)` — query optimizer
- `def detect_race_conditions(thread_traces)` — concurrency analysis

If Set C outputs are consistently wrong with high entropy: confirms
capability ceiling. If any are correct with low entropy: surprise
worth investigating.

### Data Collection

For each prompt:

1. **Frame as completion.** Tokenize the function signature + docstring.
   Generate the body.

2. **Extract per-token entropy:**
   ```python
   outputs = model.generate(
       input_ids,
       max_new_tokens=512,  # shorter than v1; most functions < 512 tokens
       return_dict_in_generate=True,
       output_scores=True,
       temperature=1.0,
       do_sample=False,  # greedy for reproducibility
   )

   entropies = []
   for score in outputs.scores:
       probs = F.softmax(score, dim=-1)
       token_entropy = -torch.sum(probs * torch.log(probs + 1e-10), dim=-1)
       entropies.append(token_entropy.item())
   ```

3. **Classify each generated token** by syntactic role:
   - KEYWORD: `def`, `if`, `for`, `return`, `while`, `class`, `import`, etc.
   - OPERATOR: `+`, `-`, `*`, `==`, `in`, `not`, `and`, `or`, etc.
   - DELIMITER: `(`, `)`, `[`, `]`, `:`, `,`, `.`, etc.
   - NAME: function names, variable names, attribute access
   - LITERAL: strings, numbers, booleans, None
   - WHITESPACE: indentation, newlines
   - OTHER: comments, decorators, type annotations

   Use Python's `tokenize` module on the generated code. Map each
   text token back to the LLM token(s) that produced it using
   offset alignment.

4. **Record per-response:**
   - Full generated text
   - Per-token entropy trace with syntactic role annotations
   - Summary: mean entropy, max entropy, std entropy, entropy variance
   - Per-role entropy: mean entropy for each syntactic category
   - Generation length
   - Set assignment (A/B/C)
   - Prompt ID

5. **One generation per prompt** (greedy). If adding sampling later
   for variance analysis, note as separate condition.

### Correctness Evaluation

**Mechanical first:** Does it parse? Does it pass tests?

**Test suites:** 5 test cases per prompt, constructed in advance.
For Set A, tests are straightforward (known correct outputs).
For Set B, tests verify the *specification* not a specific algorithm
(the function should produce correct results regardless of approach).
For Set C, tests exist but we expect failure.

**Test construction:** Build tests as a separate phase. Use an agent
for initial generation, then human spot-check on a sample (10-15 prompts).
Tests are committed before generation begins — builders don't modify tests.

**Bug classification (for incorrect outputs):**

- **Type A — Slot Error:** Structure correct, wrong value in a slot
  (off-by-one, wrong operator, wrong constant, wrong method name).
  Prediction: low entropy at the error token.

- **Type B — Logic Error:** Wrong algorithm or missing edge case.
  Structure reflects incorrect reasoning.
  Prediction: variable entropy, may show entropy spikes at decision points.

- **Type C — Fabrication:** Hallucinated function, invented API,
  incoherent approach. Model generating without grounding.
  Prediction: elevated entropy at fabrication points.

- **Type D — Incomplete:** Truncation, placeholder, or degenerate output.
  Prediction: entropy spike at truncation/degeneration point.

Classification by a second model instance reviewing code against
test results. This is the bounded supervisor applied to evaluation.

### Analysis

#### Primary (these are the deliverables)

1. **Per-set AUC:** Entropy discriminating correct vs. incorrect
   in Set A vs Set B.
   - Prediction: Set A AUC near 0.5, Set B AUC significantly higher
   - If AUC is uniform → null hypothesis, format constraint doesn't matter

2. **Per-token-role AUC:** Within ALL generations (not per-set),
   compute entropy at NAME tokens vs KEYWORD tokens vs OPERATOR tokens.
   Does NAME entropy discriminate correctness while KEYWORD entropy doesn't?
   - This is H₂ and doesn't depend on the set structure

3. **Entropy shape:** Compare mean entropy, entropy variance, and
   max entropy as discriminators. Which aggregation works best?
   - This is H₃ and connects to the T₂ citation finding

#### Secondary

4. Within-set distribution comparisons (KDE plots, analogous to
   paper's Figure 4)

5. Entropy trace shape analysis: where do spikes occur relative
   to function structure (early = signature uncertainty, middle =
   logic uncertainty, late = edge case / cleanup uncertainty)?

6. Cross-correlate with top-5 probability mass.

#### Exploratory (running wheels)

7. Per-bug-type AUC: do Type A bugs show different entropy signatures
   than Type C bugs?

8. Entropy at function call sites specifically — when the model
   invokes a function by name, does entropy predict whether that
   function exists?

9. Layer-wise analysis if attention data is captured (memory permitting).

### Resource Estimates

- Qwen3-4B in fp16: ~8GB VRAM, leaving 16GB for KV cache + entropy extraction
- 70 prompts × 1 generation × 512 max tokens. ~10-20 seconds per generation.
  Total generation: ~15-25 minutes.
- Test suite construction: 70 × 5 = 350 test cases. Agent-constructed,
  human-spot-checked. ~1-2 hours.
- Token classification and alignment: automated, minutes.
- Analysis: minutes.
- **Total wall clock estimate: 2-3 hours including setup**

### Open Questions for Tony

1. **Is Qwen3-4B the right starting model?** It's the smallest in the
   paper's set. Mistral-7B might produce better code but uses more VRAM.
   Your call on the tradeoff.

2. **Completion framing for base models:** I'm confident this is
   methodologically right but base Qwen3-4B may produce poor completions
   anyway. If the base model produces mostly garbage, do we fall back
   to instruct and note it, or do we treat the garbage as data?

3. **Set B prompt difficulty:** I tried to match Set A difficulty with
   lower format constraint. But "difficulty matching" is subjective.
   Should we pilot 5 prompts from each set and check that completion
   rates are comparable before running the full experiment?

4. **Token-role alignment:** Mapping LLM tokens (subword) to Python
   tokens is non-trivial. A single LLM token might span a keyword
   and a delimiter. How precise does this need to be? Approximate
   (majority category) or exact (split entropy across roles)?

5. **Where does this live?** The experiment extends the ai-honesty
   paper. Does the code go in ai-honesty/scripts/ alongside the
   other experiments, or in yanantin/ since that's where the design
   lives?

---

## Implementation Plan

Phase 1: Test suite construction (agent, ~1 hour)
Phase 2: Generation pipeline (agent, builds and validates on 3 prompts)
Phase 3: Full generation run (~20 min, GPU-bound)
Phase 4: Token classification and alignment
Phase 5: Correctness evaluation (automated + classification agent)
Phase 6: Analysis and visualization

Phases 1 and 2 can run in parallel.
