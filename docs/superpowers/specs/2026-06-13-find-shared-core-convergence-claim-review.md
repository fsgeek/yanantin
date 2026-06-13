# Review: shared-core convergence claim

Reviewed document:
`docs/superpowers/specs/2026-06-13-find-shared-core-convergence-claim.md`

Review date: 2026-06-13

Reviewer stance: adversarial, code-backed, shareable with the author. This review
does not judge whether the architecture is promising. It judges whether the
document's central claim is currently supported, falsifiable, and actionable
against the repository state.

## Verdict

The document should not be treated as a settled finding. The central claim is a
good hypothesis, but it is not yet a verified convergence result. The repository
currently proves only the activity-stream part of the story. The two parts that
would actually bear the human/LLM convergence claim, the uniform storage object
and the semantic intent resolver, are absent or prose-only.

The strongest current version of the claim is:

> A shared core may be possible, but the present code only establishes the
> activity stream substrate. Convergence remains untested until a uniform
> storage object and semantic resolver exist, and until both a human episodic
> query and an LLM code query are run against the same resolver and storage
> path.

## Major Findings

### 1. The central claim is unfalsifiable in the current codebase

Severity: blocking for the document's epistemic status.

The document states that "one shared deterministic core serves both customers"
for a human-facing find use case and an LLM-facing find use case
(`2026-06-13-find-shared-core-convergence-claim.md:91-101`). It also defines
refutation conditions around code forks, log divergence, and self-history
asymmetry (`:116-129`).

Those are the right kinds of refutation conditions, but the necessary machinery
does not exist yet:

- The query engine in `src/yanantin/query/engine.py` executes a structured
  `QuerySpec`. It does not resolve natural-language intent, does not call a
  model, and does not compile intent into semantic bands. The code path is
  fetch facts, apply Python filters, optionally summarize, paginate
  (`engine.py:84-117`).
- `QuerySpec` exposes provider, time range, content filters, content hash,
  limit, offset, and summarize (`models.py:32-51`). That is a structured query
  contract, not an intent resolver.
- The CLI maps flags directly into `QuerySpec` fields (`__main__.py:184-202`).
  It has `--search` plus `--field`, which is still caller-supplied address
  compilation, not semantic intent resolution.
- The source document's "semantic-shaped" layer is described in prose as a
  UUID-label triple with registration and equivalence (`:180-183`), but there is
  no corresponding implementation in `src/yanantin/query` or
  `src/yanantin/collector`.

The result: the declared convergence test cannot currently be run. A review
cannot show that the same core serves both customers because the resolving core
that would be shared is not built.

Recommended author action: change all "finding" language around convergence to
"hypothesis" unless it is explicitly scoped to the activity-stream substrate.
Keep the refutation conditions, but mark them as future gates rather than as
already-payable tests.

### 2. The evidence validates the least controversial axis, then generalizes to the hard axes

Severity: blocking for the argument.

The activity stream is real:

- `ActivityStreamStore` defines append-only fact storage and provider/time-range
  querying (`activity/store.py:19-89`).
- `FactRecord` is provider-tagged, timestamped, schema-agnostic data
  (`activity/models.py:36-59`).
- `FactRecorderBase` exists and records raw observations into the stream
  (`collector/base.py:168-214`).
- Filesystem and Dropbox fact recorders decompose source data into facts
  (`filesystem/fact_recorder.py:36-54`, `dropbox/fact_recorder.py:37-58`).

That supports the document's activity-stream claim. It does not prove the
shared-core convergence claim, because a timestamped append-only stream is
naturally silo-neutral. The harder claims are:

- Can heterogeneous storage objects share one queryable shape?
- Can the same semantic resolver ground a human episodic phrase and an LLM code
  intent?
- Can the same result shape satisfy both customers without special resolver
  mechanics?

Those remain untested.

Recommended author action: separate "substrate convergence" from "resolver
convergence." The former has code evidence. The latter is the actual hypothesis.

### 3. The uniform storage object is correctly identified as missing, and that absence blocks cross-silo find

Severity: high.

The source document accurately says the storage-shaped core is red-barred and
unbuilt (`:173-179`). Current code confirms that:

- `tests/red_bar/test_uniform_storage_object.py` imports
  `yanantin.collector.storage_object` and deliberately fails when no uniform
  object exists (`test_uniform_storage_object.py:62-96`).
- The same test requires canonical UUID-named timestamps
  (`test_uniform_storage_object.py:105-127`) and an open semantic-attribute lane
  (`test_uniform_storage_object.py:137-165`).
- `FileEntryData` is closed (`extra="forbid"`) and filesystem-specific,
  including a `file://` URI invariant (`filesystem/models.py:36-72`).
- `DropboxEntryData` is also closed and Dropbox-specific, with
  `modified_time`, `path_display`, `path_lower`, Dropbox content hash, and
  Dropbox entry types (`dropbox/models.py:19-59`).

I ran:

```bash
uv run pytest tests/unit/test_query_engine.py tests/red_bar/test_query_pipeline.py tests/red_bar/test_uniform_storage_object.py -q
```

Result: 89 passed, 3 failed. The three failures are exactly the uniform storage
object red bars: object absent, canonical timestamp UUIDs absent, and open
semantic-attribute lane absent.

This supports the document's "gap red-barred" statement. It also means
cross-silo find is structurally not available yet. Any claim that a shared core
already handles human and LLM find must exclude cross-silo storage until this
object exists and collectors normalize to it.

Recommended author action: keep this as now-debt, not as supportive evidence.
The honest framing is: "the claim predicts this object will allow convergence,
and the current red bar shows exactly where the claim is not yet paid."

### 4. The current query engine is not the "head" described in the document

Severity: high.

The layering section says the query engine "contains the MODEL," "resolves
intent -> bands/filters via the semantic layer," emits typed rejections, and
owns an injection wall (`:149-155`, `:185-188`). The implementation does not
match that description.

Current implementation:

- `QueryEngine.execute()` takes a pre-built `QuerySpec` (`engine.py:84-85`).
- `_fetch_facts()` pulls provider/time ranges from the activity store
  (`engine.py:140-156`).
- `_apply_content_filters()` applies deterministic Python filters over fact
  data (`engine.py:158-167`).
- `_apply_filter()` supports `contains`, `eq`, comparisons, `exists`, and
  `glob` (`engine.py:39-64`).
- There is no rejection model, no typed rejection result, no authorization
  decision, no model call, and no semantic resolver.

The name "QueryEngine" is therefore overloaded. In code, it is a structured
filter executor over activity facts. In the document, it is an intent compiler
and policy boundary. Those are different components unless and until the code is
refactored to express the distinction.

Recommended author action: rename the current thing in the prose as
"structured fact query executor" or explicitly split the future "intent
compiler" from the existing `QueryEngine`. Otherwise the doc reads as if a
future component already exists.

### 5. Query-as-activity recursion currently leaks identity across instances

Severity: high, already acknowledged in the source document but worth preserving
as a standalone finding.

The document's meta-recursion section argues that query activity can be stored
as ordinary activity data and then found through the same machinery
(`:266-285`). That is architecturally attractive, but the current implementation
does not record who asked the query.

Evidence:

- `QUERY_PROVIDER_ID` is a single deterministic UUID for the whole query service
  (`query/recorder.py:20`).
- `QueryFactRecorder.record_query()` writes all query facts under that provider
  (`query/recorder.py:40-50`).
- The recorded data includes query id, spec, total matched, returned count, and
  execution time, but no principal, consumer, user, or instance identity
  (`query/recorder.py:44-50`).
- The recorder docstring explicitly names cross-instance pattern detection as a
  goal (`query/recorder.py:1-8`).

As built, "what did I already find" cannot be distinguished from "what did this
shared query service record." That is not just an authorization seam. It is a
data-shape problem because unattributed query facts written now would need later
retrofit.

Recommended author action: keep this promoted from seam to now-debt. Add a
concrete red-bar test that query facts carry principal-shaped attribution before
query recursion is used as evidence for self-history.

### 6. The mandatory count contract is implemented, but the implementation violates the scalability reason for the contract

Severity: medium-high.

The document argues that count is mandatory and that page-cap is the one
external knob (`:202-211`). The current result model has `total_matched` and
`returned_count` (`query/models.py:71-91`), and query tests cover pagination
while preserving total count (`tests/unit/test_query_engine.py:315-335`).

The problem is implementation:

- `QueryEngine.execute()` materializes all matching facts into a Python list,
  computes `total_matched = len(filtered)`, then slices for pagination
  (`engine.py:88-105`).
- When no provider is specified, `_fetch_facts()` queries every provider,
  extends one list, and sorts all facts in memory (`engine.py:147-156`).
- `DuckDBActivityStreamStore.query_range()` pushes provider/time filtering to
  SQL, but still returns all rows in the range to Python (`duckdb.py:140-163`).

So the result shape is right, but the executor cannot safely support the
large-corpus use case the document invokes. The contract says "count, do not
dump"; the implementation still dumps internally.

Recommended author action: state this as implementation debt on the path to the
claim. The next interface likely needs a store-side query primitive returning
`page + total_count` without materializing the full result set in Python.

### 7. "Injection unrepresentable" protects only the current structured library boundary

Severity: medium.

The document says the library input type has no raw string query field and
therefore injection is unconstructible (`:232-241`). For the current structured
executor, that is mostly true: `QuerySpec` has structured fields and no raw AQL
or SQL string (`query/models.py:32-51`), and the query red-bar test checks that
`query.engine` contains no SQL/AQL strings (`test_query_pipeline.py:49-65`).

However, this only proves that raw database-language injection is not present at
the current executor boundary. It does not protect the future model compiler
described in the same document. A model could compile adversarial natural
language into a well-formed but hostile `QuerySpec`, such as a broad query over a
provider the caller should not see. That threat is authorization and intent
validation, not raw string injection.

Recommended author action: split the security claim into two statements:

- Current executor: no raw query language surface.
- Future intent compiler: must classify hostile or unauthorized intent before
  constructing an otherwise well-formed `QuerySpec`.

### 8. The Serena comparison is useful, but it is not evidence for identical human and LLM storage interfaces

Severity: medium.

The Serena comparison identifies real gaps: intent, time/self, and cross-silo
join (`:289-309`). That is helpful. But the conclusion that the optimal storage
interface for an LLM is identical to the optimal one for a human (`:311-317`)
does not follow from the evidence presented.

A code-oriented LLM query and a human episodic file query may share some return
contracts: neighborhoods, count, timestamps, provenance, and refinement loops.
But they may require different resolver mechanics:

- Code has parseable symbols, AST neighborhoods, call/reference edges, and
  deterministic repository text.
- Human episodic recall often starts from private time anchors, social context,
  approximate memory, and ambiguous object identity.

The same deterministic storage core might still serve both, but that is exactly
what must be tested. The Serena comparison makes the hypothesis plausible; it
does not validate it.

Recommended author action: soften "identical" to "may be factored through a
shared core if resolver-specific work stays above the deterministic data layer."

## What Is Solid

The document has several strong properties worth preserving:

- It explicitly asks to be falsified instead of polished.
- Its refutation conditions are meaningful and should become tests.
- The storage-object red bar is concrete and currently honest.
- The activity-stream substrate is real and tested across memory and DuckDB
  backends.
- Query facts are recorded as ordinary activity facts, which is a useful design
  move once principal attribution is added.
- The document correctly resists hiding count, pagination, and rejection
  semantics behind vague "search result" language.

## Required Changes Before Treating The Claim As Verified

1. Build or specify the uniform storage object as a first-class code artifact:
   canonical timestamp UUIDs, open semantic-attribute bag, raw blob retained
   beside normalized fields, and collector normalization into that shape.
2. Build or specify the semantic resolver separately from the structured fact
   executor. It must own intent compilation, label registration, equivalence,
   ambiguity handling, and typed rejection.
3. Add principal-shaped attribution to query facts before relying on query
   recursion as self-history.
4. Add a store-side query primitive that returns `total_count + page` without
   materializing every match in Python.
5. Turn the convergence test into an executable suite:
   same storage core, same semantic resolver, one human episodic query, one LLM
   code query, same return contract, and failure if a separate resolver or store
   is required.
6. Split the security model into raw-query injection, hostile intent
   compilation, and authorization. These are different boundaries.

## Suggested Edits To The Reviewed Document

- Keep the top adversarial review section. It is accurate and important.
- Change the title or status from "claim" toward "hypothesis under review" if
  the document is meant to travel beyond the immediate design conversation.
- In "The layering," mark the described query engine as future architecture, not
  current code.
- In "The central claim," retain the bold hypothesis box and remove any later
  phrasing that sounds like convergence has already been discovered.
- In "The meta-recursion," say the recursion is a promising design pattern but
  not positive evidence until query facts carry principal identity.
- In "How this differs from Serena," preserve the table but weaken the
  "IDENTICAL" conclusion to a testable hypothesis.
- In "Build/test topology," promote suite #3 from concept to exact acceptance
  criteria: inputs, expected shared components, allowed consumer-specific
  disposition, and forbidden forks.

## Evidence Checked

Code and tests inspected:

- `src/yanantin/query/models.py`
- `src/yanantin/query/engine.py`
- `src/yanantin/query/recorder.py`
- `src/yanantin/query/__main__.py`
- `src/yanantin/activity/models.py`
- `src/yanantin/activity/store.py`
- `src/yanantin/activity/backends/memory.py`
- `src/yanantin/activity/backends/duckdb.py`
- `src/yanantin/collector/base.py`
- `src/yanantin/collector/filesystem/models.py`
- `src/yanantin/collector/filesystem/fact_recorder.py`
- `src/yanantin/collector/dropbox/models.py`
- `src/yanantin/collector/dropbox/fact_recorder.py`
- `tests/unit/test_query_engine.py`
- `tests/red_bar/test_query_pipeline.py`
- `tests/red_bar/test_uniform_storage_object.py`
- `tests/red_bar/test_single_principal_accretion.py`

Verification command:

```bash
uv run pytest tests/unit/test_query_engine.py tests/red_bar/test_query_pipeline.py tests/red_bar/test_uniform_storage_object.py -q
```

Observed result: 89 passed, 3 failed. The failures are the expected uniform
storage-object red bars.

## Bottom Line For The Author

The architecture is not refuted. The status is wrong if presented as a result.
Treat the current document as a hypothesis capture with unusually good
refutation hooks. The next useful work is not more prose in favor of the claim;
it is paying the three debts the document itself exposes: uniform storage object,
semantic resolver, and attributed query facts.
