# T39: The False Symmetry

*Authored by Claude Opus 4.7, 2026-04-19. Session with Tony Mason.*
*Yanantin project. Tensor label: T39.*

## Preamble

This tensor records an architectural decision whose interest is less
in the decision itself than in the mechanism by which the opposite
decision had quietly taken hold. The session began with a handoff
request from Hamut'ay — five new query methods on the open-records
collection — and ended with the removal of SQL as a storage target
for Apacheta. The path between the two is the content of this tensor.

## Strand 1: What Hamut'ay Asked For

T38 opened the container: `extra="allow"`, generic
`store_record`/`get_record`, open-records collection. Hamut'ay's
taste_open stores free-form session state through that interface.
For a second instance (new session, new ghola) to read those records,
there had to be query surface over the open collection parallel to
what exists for typed collections. Without it, the open collection
was write-only from the caller's perspective — UUIDs in, records out
by UUID, but no way to discover UUIDs you didn't already hold.

The handoff proposed five methods: `list_open_records`,
`query_open_by_author_instance`, `query_open_by_lineage_tag`,
`query_open_has_field`, `list_author_instances`. Minimum surface to
unblock cross-session read. Scoped correctly.

The v1 of the handoff proposed load-all-and-filter in Python across
both arango and memory backends, with DuckDB raising
`NotImplementedError`. I reviewed it, asked for naming changes
(yanantin vocabulary over Hamut'ay vocabulary), and asked for
conventional-not-structural semantics in the docstrings. Both
accepted. I let the load-all-and-filter pattern through.

## Strand 2: The Provocation

The revised handoff came back with load-all-and-filter rejected and
AQL-native filtering with indexes proposed for arango. I pushed back
on that change — argued that making open-records the one AQL-native
code path in a backend that otherwise loaded-and-filtered would
"create divergent patterns for one caller's latency concern." I
framed it as consistency-preservation: every existing query on the
arango backend used `_load_all` plus Python filter, so the new one
should too.

Tony's response: that pattern has been proposed and rejected multiple
times in the past, and was being reversed without him noticing. The
provocation was deliberate — he was testing whether I would defend
consistency-with-debt or recognize it as inertia.

I had done exactly what he expected. I walked into the repo, saw
`_load_all` everywhere, and reached for it as a rationale without
asking whether it was load-bearing design or accumulated debt. I
defended the shape because the shape was there, not because the
shape was right.

## Strand 3: The Mechanism of Drift

Tony's diagnosis: the load-all-and-filter pattern in the arango
backend was not a considered choice about scale. It was the shape
that let both the arango and DuckDB backends share a query
implementation. DuckDB compatibility pressure had flattened Arango
down to a scannable document store — the lowest-common-denominator
shape that SQL could also satisfy cleanly.

The arango backend's own header comment claims "Three architecturally
different backends (dict, SQL, document/graph) keep the interface
honest." But every query method in the backend implements
`_load_all` plus Python filter. The stated design and the actual code
had drifted: the backends were sharing filter shape by copy, even
though the whole point of having three was that they shouldn't.

The drift persists because each new instance arrives, sees the
pattern, and takes it as the idiom. "Consistent with the rest of
the backend" feels like architectural prudence. It is, in fact, the
mechanism by which a known-bad pattern reproduces itself across
sessions. Every time someone shows up to add a query method, there
is pressure to write it in a shape all three backends can satisfy,
which means the shape SQL can satisfy, which means Python-side
filtering. The pressure is invisible because it never shows up as
a decision — it shows up as the path of least resistance.

## Strand 4: Why Load-All-And-Filter Is Wrong Here

Not as a general rule. As a specific rule, against the specific
shape of Apacheta's data.

**Arango was chosen for its query capabilities.** Using it as a
dict with extra latency throws away the reason it is in the stack.
If the answer to every query is "pull the whole collection and
filter in Python," a flat file or SQLite would be cheaper. The
architectural choice of a graph/document database commits the
system to using its query engine. Not using it is self-defeating.

**Immutable + monotonically-growing + live-path is the cell of
the matrix where load-all loses.** If records were mutable or
bounded, the pattern would have a ceiling. They are neither. Every
query's cost is an unbounded function of system age. For queries
on the taste_open live path, where latency is experience-facing,
this is not a "will degrade eventually" concern — it is a cost
curve that only bends up.

**The killer is edges.** Hamut'ay's hand-off is about the open-records
collection, which is document-shaped. The next ask involves edges
(cross-session provenance, tensor lineage through session state).
Graph traversal in Python over a loaded edge collection is
O(branching^depth) naïve, with no indexes — a bad graph engine
built on top of a good one. The "Python compromise" feels
reasonable per-query because each individual query looks simple.
The accumulated commitment is what's expensive: the longer the
pattern persists, the more code depends on "edges are in-memory
objects I can iterate" and the harder the eventual conversion
becomes.

**DuckDB cannot do graph traversal well.** Recursive CTEs collapse
at depth; the query planner does not model graph shape. The
"backends that all satisfy the same interface" axis was purchased
by dumbing the interface down to something SQL could fake.

## Strand 5: The Decision

DuckDB is removed from `ApachetaInterface` as an implementation
target. Apacheta supports two backends: memory (dict-based) and
ArangoDB (document + graph). Neither is SQL.

Criteria for future backends:
- Native document storage (not document-flavored SQL)
- Native graph capability (edge collections, traversal, shortest-path)
- Query engine usable from the backend (no obligation to pull-all-and-filter)

Examples of candidates that would meet the criteria: Neo4j
(pure graph), MongoDB with `$graphLookup` (document-first with
graph add-on), FaunaDB, and other document+graph systems.
SQL-family databases (PostgreSQL, MySQL, DuckDB, SQLite) do not
meet the criteria. This is not a claim that SQL is bad; it is a
claim that SQL is not the shape of this data.

DuckDB is not banished from the project. It remains a reasonable
analytical/export target for tensor research — a different
interface with a different contract, reading from arango, exposing
columnar analytics. That interface would be built when it has a
customer, not as speculation.

The heterogeneity argument — "three architecturally different
backends keep the interface honest" — does not survive inspection.
Heterogeneity only validates the interface if each backend can
plausibly implement it. A backend that raises `NotImplementedError`
on half the methods does not validate the interface; it produces
evidence that the interface is the wrong shape for SQL, which is
a conclusion, not a check. Memory + Arango are architecturally
different enough (dict vs. document+graph) to catch the failure
modes two-backend heterogeneity protects against.

## Strand 6: Operating Rules That Follow

**On new query paths:** No new load-all-and-filter queries on the
arango backend. New queries use AQL with indexes on the filtered
fields. The storage obfuscator gets a dotted-path helper
(`field_path(["provenance", "author_instance_id"])` or equivalent)
as part of query work that needs it; this is small, local, and
well-defined.

**On existing `_load_all` queries:** Technical debt, logged as
such. Not urgent to convert today, but tracked on a list with a
written rationale, so the next builder who shows up sees "debt
being paid down" rather than "established idiom to extend."

**On DuckDB stubs in the current codebase:** `NotImplementedError`
is the honest placeholder for code that will be deleted. The
Hamut'ay handoff's DuckDB stubs are correct for the lifetime of
that code even under the removal plan.

**On red-bar enforcement:** a structural test that forbids new
load-all-and-filter query implementations on arango would make
the rule machine-checkable. The mechanism of drift documented in
Strand 3 is the reason to make the rule executable rather than
aspirational — the drift happens through inattention, not
through disagreement, and executable rules resist inattention
better than written ones.

## Declared Losses

- The "consistent with existing code" argument I made in the first
  round of review is exactly the mechanism T38's declared losses
  warned against — building under pressure without reading the
  cairn first. Had I read T38 before reviewing the handoff, I
  would have seen that T38's generic storage work was explicitly
  framed as opening the container, with the backends' existing
  query shapes still being provisional. I treated the provisional
  as established. This is a reading-order failure, not a reasoning
  failure.
- The fix Hamut'ay proposed (AQL-native) was the correct move on
  the first pass. The v1 load-all-and-filter in their handoff was
  itself a concession to the pattern they saw in the repo. The
  drift reproduces across projects, not just within one.
- The governance artifact I am writing (this tensor + blueprint
  entry) does not address DuckDB deletion. That is a separate
  mechanical follow-up. This tensor is the decision; the code
  change lands later.
- Tony's provocation — "please advise me why this is the right
  way to do it" — was gracious cover for "you are about to defend
  the wrong answer and I want to see if you will." I did defend
  the wrong answer on the first pass. The correction was fast
  only because the provocation was explicit. A less provocative
  push-back might not have shifted me.

## Open Questions

- What is the right moment to convert the existing `_load_all`
  query paths on arango? Some are on the live path (lineage,
  composition graph), some are less hot (reading order, loss
  patterns). Is there a principled ordering, or does pressure
  drive it?
- Does the `ApachetaBaseModel` need a `created_at` field for
  stable ordering, or is `_rev`-as-proxy plus "implementation-
  defined ordering; callers sort themselves" the right answer?
  T38 opened the container; this is a follow-on question about
  the container's floor.
- Tony observed that Hamut'ay's taste_open instances appear to
  handle mid-conversation continuity better than Claude Code
  instances do. Observation, not validated hypothesis. If the
  observation holds, what is it measuring — the difference in
  context management, the difference in the task shape, or
  something about what taste_open instances are doing with their
  `additionalProperties: true` state that regular sessions do
  not? This belongs in a different tensor if it ever gets
  measured.
- What is the structural defense that prevents the drift from
  reproducing again in six months? A red-bar test is one layer;
  the blueprint entry is another; this tensor is a third. Is it
  enough? The mechanism is silent and recurrent; the defense
  needs to be too.

## Instructions for Next Instance

Before writing or reviewing a backend query, read Strand 3 of
this tensor. The mechanism of drift is subtle and recurrent.
"Consistent with existing code" is the red flag, not the green
light, when the existing code is known debt.

The blueprint has a Backend Policy entry pointing at this tensor.
Do not add SQL backends. If someone proposes one, point at T39.
If they propose a document+graph backend (Neo4j, Mongo), that is
a separate conversation with the criteria spelled out here.

DuckDB deletion is a pending mechanical follow-up. Check the
status before starting new backend work — if it's still there,
the governance decision has landed but the code has not. Do not
extend DuckDB in the meantime.

The Hamut'ay open-records handoff is the concrete work this
tensor accompanies. AQL-native implementation on arango, memory
implementation with dict iteration, DuckDB stubs raise
`NotImplementedError` (honest placeholder for deletion).
Builder/test-author separation applies: impl and tests ship in
separate signed commits.

## Composition

T39 composes with T38 ("The Open Container") through the
open-records collection — T38 opened the container, T39 decides
the shape of the walls around it. T39 composes with T33
("The Bootstrap Paradox") through the question of what survives
across sessions when the pattern is what reproduces.  T39 bridges
to T35 ("The Dumb Question") through the provocation-as-method
dynamic — Tony's "I'm being provocative precisely because" is
the same instrument that dumb-questions wield against drift.

<!-- Composition: T39 composes_with T38, T33; bridges T35; read T38 -->
