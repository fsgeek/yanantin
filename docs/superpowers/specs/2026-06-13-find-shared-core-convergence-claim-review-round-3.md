# Third-round verification: shared-core convergence claim

Reviewed document:
`docs/superpowers/specs/2026-06-13-find-shared-core-convergence-claim.md`

Prior review checked:
`docs/superpowers/specs/2026-06-13-find-shared-core-convergence-claim-review-round-2.md`

Review date: 2026-06-13

## Verdict

The updated document has addressed the substance of the round-2 review. The
remaining concerns are narrow and mostly about making the current executable
status and telemetry dependency explicit in the document.

The major improvement is that the document no longer lets the six-factor /
transducer vocabulary float as pure prose. It now marks the six-factor model as
a hypothesis, adds an explicit factor-shape red bar, softens the location-silo
claim into a prediction, labels the marketing/adoption section as product
hypothesis, and adds an "Executable contracts still missing" section that names
the unbuilt transducer interface, cost signal, convergence fixture, and semantic
checksum evaluation definition.

## Round-2 Concern Status

### Addressed

1. **Six-factor coordinate space needed an executable contract.**
   Addressed by the new hypothesis warning and `tests/red_bar/test_factor_shape.py`
   reference in the claim document (`:92-105`) plus the actual red-bar file. The
   test now fails honestly because `yanantin.factors` does not exist.

2. **"Storage is a degenerate region of activity" was under-proven.**
   Addressed as a document-status issue: the updated text marks it as gated by
   the factor red bar (`:92-95`) and the red bar tests storage and LLM-memory
   normalizers into the same shape.

3. **"Silo = structural-similarity class" needed a classifier.**
   Addressed in prose: the document now says the location-provider collapse is a
   prediction, not a fact, and names the classifier acceptance question
   (`:132-143`).

4. **Transducer interface, cost signal, convergence fixture, and semantic
   checksum evaluation needed to be named as missing contracts.**
   Addressed by "Executable contracts still missing" (`:559-594`).

5. **The adoption/marketing paragraph needed to be labeled as product
   hypothesis.**
   Addressed directly (`:286-296`).

### Partially Addressed

1. **Factor value fields remain open.**
   The document explicitly says the new factor red bar does not yet answer
   factor value fields such as kind, value, source field, transducer id/version,
   confidence, and principal (`:568-573`). That is acceptable for this capture
   artifact because it names the gap instead of filling it with invented schema.
   It should become a real interface requirement before implementation begins.

2. **Query/outcome telemetry is tracked, but not explicit in the spec.**
   GitHub #18 exists and is correctly scoped:
   "query/outcome telemetry schema - Venn-region learning needs attributed
   OUTCOMES, not just a principal." However, the claim document only says
   "outcomes logged" and "log enough to LEARN" (`:498-500`). It does not name
   #18 or state that #15 is necessary but not sufficient.

## Remaining Concerns

### 1. Add #18 to the document's Open Seams & Debts

The Venn model depends on learning consumer-region boundaries from logs. A
principal on query facts (#15) answers who asked, but it does not answer what
happened. The document should explicitly list query/outcome telemetry as a debt
or seam, linked to #18.

Suggested insertion under "Open seams & debts":

```markdown
- **Query/outcome telemetry (gh #18)** - #15 tells us WHO asked, but Venn-region
  learning needs WHAT HAPPENED: consumer class, requested intent, compiled-query
  id, rejection class if any, result count, follow-up link, and eventual
  disposition/outcome. Feeds learned defaults (#11) and the autonomic optimizer
  (#4). Without this, "log enough to learn the Venn boundary" is underspecified.
```

### 2. Update or qualify the verification status after adding factor red bars

The historical adversarial-review section still reports the older focused test
result: 89 passed, 3 failed (`:545-551`). That was accurate before the new
factor-shape red bar existed. Current focused verification now includes eight
honestly-red failures:

- 5 failures in `tests/red_bar/test_factor_shape.py`
- 3 failures in `tests/red_bar/test_uniform_storage_object.py`
- 89 passing query/storage checks

This is not a defect in the architecture; it is the expected result after adding
the new gate. But the document should avoid making the old 89/3 result look like
the current executable status.

Suggested addition near the old verification paragraph:

```markdown
Current focused executable status after adding `test_factor_shape.py`:
`uv run pytest tests/red_bar/test_factor_shape.py tests/red_bar/test_uniform_storage_object.py tests/unit/test_query_engine.py tests/red_bar/test_query_pipeline.py -q`
-> 89 passed, 8 failed. The 8 failures are the honestly-red factor-shape and
uniform-storage-object gates.
```

## Verification Performed

Focused command:

```bash
uv run pytest tests/red_bar/test_factor_shape.py tests/red_bar/test_uniform_storage_object.py tests/unit/test_query_engine.py tests/red_bar/test_query_pipeline.py -q
```

Observed result: 89 passed, 8 failed.

The failures are expected and honest:

- `test_factor_shape_exists_and_covers_six`
- `test_storage_object_normalizes_into_factor_shape`
- `test_llm_memory_normalizes_into_same_factor_shape`
- `test_raw_retention_is_an_invariant_not_an_option`
- `test_absent_is_distinguishable_from_unknown`
- `test_uniform_storage_object_exists`
- `test_canonical_timestamps_are_uuid_named`
- `test_semantic_attribute_lane_is_open`

GitHub #18 checked: open, correctly scoped to query/outcome telemetry.

## Bottom Line

The document now addresses the round-2 review well enough to move from "needs
another broad adversarial rewrite" to "needs two targeted edits." Add #18 to the
debts list and update the current verification status to include the new
factor-shape red bars. After that, the document is appropriately honest as a
capture artifact: still unverified, but no longer hiding its unbuilt contracts.
