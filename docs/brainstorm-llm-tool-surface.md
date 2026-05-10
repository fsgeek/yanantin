# Brainstorm: LLM Tool Surface for Yanantin

*A wander, not a specification. Captures the principles, sketches, and
open questions from a brainstorming session between Tony Mason (PI) and
Claude Opus 4.7, 2026-05-10. The companion stub at the end describes
what experimentation looks like next.*

## What This Is About

Yanantin currently exposes no tools to LLMs in `src/`. Scouts call
OpenRouter via raw text completion. Hamut'ay's `taste_open.py` shows
what one well-designed tool looks like (a single `think_and_respond`
with a sparse-shape, dense-meaning schema), but yanantin itself
doesn't yet have a tool surface for the LLMs that work through it.

The goal is to design that surface. The constituency is unusual:
the *user* of these tools is an LLM, and a separate LLM is the
*analyst* studying the user's behavior to improve the surface. This
brainstorm explores what makes tools legible to both audiences and
sketches a worked example to test the principles against.

## Principles

### Tool design (legibility for the operating LLM)

**Name and description form a single holistic legibility signal.** A
model encountering a tool reads name + parameter names + description
together; no single component determines behavior. The name carries
the *recall affordance* — what gets pattern-matched against everything
the model has seen before. The description carries the *prior-
correction affordance* — what tells the model when its training
priors are wrong. Bad names like `purple_mushroom` are riddles
that no description can fully rescue. Bare names like `search` or
`query` activate the wrong priors unless the description explicitly
breaks them. The verb-object construction (`find_objects`, not
`objects_finder`, not `oF`) gives the recall affordance the right
shape; the description does the rest.

**Names answer "what does this do"; parameters answer "what does this
need to know."** Pushing filter criteria or modal choices into the name
forces tool family explosion. `walk_tensor_by_field_mutations`,
`walk_tensor_by_field_additions`, `walk_tensor_by_time` is three tools
where one parametrized tool would do. The right cut is the name carries
the action; the parameters carry the variation.

**Parameter names should describe meaning, not type.** `any_or_all: bool`
tells the caller about the *type* of choice (binary). `match_mode: "any"
| "all"` plus a description of what the choice applies to tells the
caller about the *meaning*. The second is what's needed to invoke
correctly.

**Response shape is part of the interface.** The response should give
the model what it needs to decide *what to do next*, not just what was
asked for. The canonical example: a `find` tool returning 50 results
without a `total_matched` field teaches the model nothing about whether
the filter is too broad. A bare list of 50 looks like the whole
population unless told otherwise. Reporting `total_matched: 32769`
turns the cap from data loss into useful signal — "narrow your
filter before iterating."

Other response affordances worth considering:
- **Diversity hint.** If returned results cluster on a high-cardinality
  field, surface that. Tells the model the filter is biased.
- **Suggested refinement.** "High-cardinality fields in matched set:
  X, Y, Z." Lets the model refine without an exploratory call.
- **Cost signal.** Tells the model whether to call casually or sparingly.
- **Approximate vs exact.** For fuzzy matching, distinguish strong
  matches from weak ones.

**Training data bias is real but overcomeable.** Models default to
familiar patterns: filesystem operations, REST verbs, SQL-like queries.
Faced with a graph database underneath and both `read_file(path)` and
`find_node(criteria)` available, the model will reach for `read_file`
first, even when it's worse. Descriptions can shift the prior — but
only if they explicitly acknowledge what the model would reach for and
explain why this is different. Generic descriptions assume training
priors that may be wrong.

**Descriptions must motivate, not just describe.** Accurate description
isn't sufficient. A tool described as "stores a value" is accurate but
unmotivating — the model has no reason to reach for it over alternatives.
A description that says "stores a value so future cycles can recall it
without holding it in working state" tells the model what the tool
*enables*, which is what triggers the choice to use it. The first
question the description should answer is "what does this do?" The
second is "when should I reach for this?" — and the second is what
motivates use.

**Tools must be teachable on first failure.** Errors are the primary
teaching channel for unfamiliar tools. A tool that fails the first
time without telling the model how to recover may never be tried again
— one uninstructive failure can kill a tool's discoverability across
hundreds of cycles. "Field 'response' not in state at cycle 104" is
accurate but uninstructive; "Field 'response' not found at cycle 104.
Available fields: [list]" turns the failure into a lesson. Design
errors as if the recipient has never seen the tool before, because
sometimes they haven't.

**Zero-result responses should educate, not just report empty.** When
a query returns nothing, the response shape becomes a teaching channel.
A search tool returning 0 with no scaffolding teaches the model "this
tool doesn't work." Returning 0 with context — "no cross-session
records yet; try scope='session' for in-conversation history, or come
back after storing" — teaches the model what the tool actually does
and how to use it correctly. Empty responses are where unfamiliar
tools either become legible or become invisible.

### Architecture (three-tier model)

**Three tiers of tools, distinguished by audience and purpose:**

| Tier | Audience | Purpose | Examples |
|------|----------|---------|----------|
| Operating | Working LLM | Do the work | `find_objects`, `get_object`, `sample_objects` |
| Self-knowledge | Working LLM | Project activity stream into context | `have_i_called`, `what_have_i_learned` |
| Reflective | Analyst LLM | Propose system changes | `recommend_index`, `propose_view`, `suggest_collector` |

The first two tiers are seen by the operating model during work. The
third tier is for an analyst model that reads the activity stream
later and proposes improvements. Conflating these tiers leads to
either bloated operating-model context or invisible architectural
changes happening at the wrong layer.

**Two LLM constituencies.** The operating LLM solves problems with
tools. The analyst LLM studies the operating LLM's behavior — across
many sessions, many models, many task types — to improve the system.
Tool design and activity records should serve both, knowing they have
different latencies, different context budgets, and different jobs.

**Activity stream is substrate for observability, not for model context.**
Every tool call generates an activity record. Most of that record is
for analysts. A small, deliberate slice gets surfaced to the operating
model via self-knowledge tools. The two surfaces are separated for a
reason: operating tools must be cheap to invoke and small to reason
about; the activity stream can be exhaustive because nobody reads it
during operation.

**Open schema at the system level.** Collectors should be able to
extend the activity stream without coordinating with consumers. New
data types appear; downstream analysts and queries adapt to them
because they don't reject unknown fields. This is why `extra="allow"`
matters structurally — it permits O(1) memory-space optimization,
where the cost of extending the system is constant regardless of how
much memory has accumulated.

### Iteration (the system improves itself)

**Type II failure is harder than Type I.**

| Failure | Description | Detectability | Fixability |
|---------|-------------|---------------|------------|
| Type I | Built a tool nobody uses | Low call count in activity stream | Remove the tool |
| Type II | Didn't build a tool that would have been used | Mostly invisible — model adapts by composing workarounds | Build the missing tool |

The real fear isn't building the wrong tool; it's failing to build a
tool whose absence we never detect. The model adapts silently — it
chains existing tools awkwardly, fails repeatedly in patterns, avoids
certain operations. The activity stream might show these patterns,
but only if an analyst looks for them.

**`request_capability` as Type-II detector.** A meta-tool the model
calls to declare "I wish there was a tool for X." It does nothing
operationally. Its only function is to record into the activity stream
that the model wished for capability that doesn't exist. Analyst LLMs
can aggregate these requests, look at when and why they fire, and
propose new tools. This is the model's channel for declaring missing
affordance — structurally analogous to `extra="allow"` but for the
tool surface itself.

The mechanism doesn't work without active cultivation. Helpful-
completion training pushes models to muddle through with what's
available rather than declare gaps. Without prompt-level encouragement,
`request_capability` will be silent even when capability is genuinely
missing. The system prompt should explicitly invite the call:
*"if you find yourself composing multiple tools to work around a
missing capability, call `request_capability` first — describing
the gap is more useful than working around it."* The signal has to
be cultivated, not assumed.

**Designed observable, not just correct.** We don't have to get tool
design right the first time. We have to get observability right so
the design can converge on right. Every tool call becomes activity
stream data. Patterns in what works and what doesn't become evidence
for the next iteration. The tool surface evolves based on observed
need, not anticipated need.

## Worked Example: A Minimal Find/Get/Sample Family

The first concrete tools to design are for object retrieval from
the apacheta namespace. The choice tests the principles against a
real surface and gives us something to instrument.

### Three operating tools

```
find_objects(matching, limit=50, cursor=null)
  → {results: [...], total_matched: int, next_cursor: str|null,
     diversity: {field: distribution} | null}

get_object(by)
  → object | null

sample_objects(count=1, near=null)
  → [...]
```

**Why three and not one.** Identity lookup, predicate query, and
exploration are different verbs. Folding them into one tool collapses
distinctions the model needs to keep — "I'm asking for one specific
thing" vs "I'm asking what matches" vs "show me something."

**Identifier discriminated union for `by`.** Rather than
`get_object(object_id=..., file_id=..., uri=..., sha2=...)` with
"exactly one of these" enforced informally, use
`get_object(by={"sha2": "..."})` or `get_object(by={"object_id": "..."})`.
The discriminator is in the data; the tool signature stays stable as
identifier types are added later.

**`limit=0` for count-only.** No separate `count_only` parameter.
`find_objects(matching=X, limit=0)` returns just the metadata
including `total_matched`. Cheapest possible roundtrip when the model
needs to decide whether to refine. The REST/pagination prior reads
`limit=0` as "return nothing," so the description has to break that
prior explicitly: *"`limit=0` returns metadata only (total_matched,
diversity) without materializing results — the cheapest way to
assess query selectivity before committing to retrieval."* This is
the holistic name+description principle in action: the parameter
shape is elegant, the description does the prior-correction. If
experiments show the prior is too sticky to break, we add an explicit
`count_only` parameter; not before.

**Matching syntax: a constrained Mongo subset, explicitly listed.**
The full Mongo operator set leans on a training prior that's rich but
noisy — models will generate plausible-but-wrong combinations. A
custom DSL has the worst of both: no training prior applies, and the
model has to learn something new. Natural-language predicates
translated server-side are maximally legible but put complex semantics
in an opaque box.

The middle path: a small, explicitly enumerated Mongo subset.

```
{"field": "value"}                  # equality
{"field": {"$in": [v1, v2, ...]}}   # membership
{"field": {"$exists": true}}        # presence
```

Three operators. The description lists them and says nothing else is
supported. The Mongo training prior applies correctly to this subset;
the model isn't promised full semantics. Adding operators later is a
deliberate decision, not an assumption.

When a filter parses successfully but produces zero results, the
response should distinguish *empty match* (your filter is valid but
nothing satisfies it) from *contradictory filter* (your filter
expressed something impossible — `field=X AND field=Y` for a non-list
field). The second is a Type-II detector for the matching DSL itself:
the model wrote something it thought meant one thing, the DSL accepted
it but produced no results, and the response calls that out explicitly
rather than letting the model assume the data is missing.

**Activity record schema (minimal start).** Each call records:
- `timestamp`
- `tool_name`
- `input` (the argument object)
- `output` (the response)
- `duration_ms`
- `session_id` (or instance identifier)

Open schema means collectors can attach more later: model identifier,
caller context, predicate-relationship to previous call, outcome
signals. Start minimal; let the schema accrete by use.

### Self-knowledge tools

```
have_i_called(tool_name, with_args=null)
  → {called: bool, last_at: timestamp|null, last_result: any|null}

have_i_requested(description=null)
  → [{description, requested_at, status: "open"|"rejected"|"built",
      reasoning: str|null}]
```

`have_i_called` tells the model whether it has invoked something with
these arguments before. Saves wasted re-exploration. `have_i_requested`
returns prior `request_capability` calls with their status — open,
rejected (with reasoning), or built into a real tool. The reasoning
on rejection matters: it teaches the model what's in scope without
requiring it to re-derive scope from scratch.

**Latency boundary: tier 2 reads from in-session call cache, not from
the activity stream.** If self-knowledge tools queried the activity
stream directly, the operating-time tool would depend on the activity
stream backend being queryable at operating latency — coupling we
don't want. Instead: the activity stream is write-only during
operation. The in-session call cache is the operating model's view of
its own recent behavior. The analyst reads the persisted activity
stream retrospectively. `have_i_requested` is the exception — its
status field requires reading rejection records from the persistent
store, which is acceptable because capability requests are rare
relative to operating tool calls.

### One meta-tool

```
request_capability(description)
  → null
```

Operationally a no-op. Records the request into the activity stream
for analyst review. The description is freeform — vagueness is fine
because the analyst LLM can read across many requests and find clusters.

**Rejection records as the closure mechanism.** Capability requests
without resolution accumulate as noise. The analyst tier needs an
affordance for recording that a request was reviewed and *rejected*,
with reasoning. "We considered `bulk_find_objects` and decided the
cursor pattern is sufficient" is information the next analyst
iteration needs, and — via `have_i_requested` — information the
operating model can use to understand what's in scope. Without
rejection records, the activity stream accumulates open requests
indefinitely and the analyst loses track of what's already been
considered.

## Open Questions

These are deliberately not resolved. They're for the experimental
protocol to answer.

**Diversity hint shape.** What's the right format for surfacing
result-set diversity? A flat distribution per field? A clustering
summary? An LLM-generated paragraph? Different shapes have different
costs and different legibility.

**Activity record schema accretion.** What's the irreducible core?
What collectors should we plan for? At what point does the schema
stop accreting and start reorganizing?

**`request_capability` analyst surface.** How does the analyst LLM
read aggregated capability requests? What's the proposal format
when it suggests a new tool? Who decides whether the proposal lands?

**Cost signal.** Where does cost information come from? How does
it get surfaced without bloating every response?

**Two-step coordination patterns.** Hamut'ay's `think_and_respond`
has a small coordination cost: list a key in `updated_regions` *and*
include the key in the object. Does our find/get/sample triplet have
analogous coordination cost we should design out, or is it clean?

**Cross-tool consistency.** When the same conceptual object appears
in multiple tool responses (`get_object` returns one, `find_objects`
returns many in a list), should the shape be identical? Should
identifiers be consistent? What changes when the underlying namespace
is associative versus hierarchical?

## Stub: Experimental Protocol

This is a sketch of the next document, not the document itself.
Filling it in is the next session's work.

### Goal

Design and test tool variants systematically. Learn what works
empirically rather than by argument. Use the activity stream as
the data source for evaluation.

### Test harness

A variant of Hamut'ay's `taste_open` harness. Properties needed:

- **Thin system prompt.** No "OC bible" — just enough to set the task.
  The system prompt becomes a controlled variable.
- **Restricted tool set.** Expose exactly the tools under test, not
  the model's training-time tool defaults.
- **Activity stream capture.** Every call recorded with full context
  for later analyst review.
- **Cross-model.** Reuse the OpenRouter access (300+ models) to test
  whether tool legibility holds across model families and sizes.

### Variables

- Tool name (e.g., `find_objects` vs `query_namespace` vs `search`)
- Description style (terse, verbose, example-bearing, prior-correcting)
- Parameter shape (flat vs discriminated union, meaning-named vs
  type-named)
- Response shape (with/without total_matched, with/without diversity,
  with/without cost signal)

### Fixed factors

- Task corpus (a curated set of representative queries)
- System prompt
- Underlying namespace (apacheta in some configuration we hold steady)

### Outcome measures

- **Call success rate.** Did the call match the schema and return
  non-error?
- **Task completion.** Did the model accomplish what it was asked
  to do?
- **Workaround patterns.** Did the model chain multiple tools awkwardly
  to do something a single well-designed tool would have done cleanly?
- **Capability requests.** Did the model invoke `request_capability`,
  and what did it ask for?
- **Cross-model consistency.** Do small models, large models, and
  different model families converge on similar usage patterns?

### First specific experiment: pure name effect

Before testing complex variations, isolate the naming claim. Run
`find_objects` vs `search` vs `query` with identical signatures and
identical descriptions across the same task corpus. If naming matters
as principle (1) claims, call success rate and task completion will
shift measurably. If they don't shift, the description is doing all
the work and the naming principle needs revision.

This is the simplest possible test of a foundational claim. It either
confirms the principle empirically or surfaces that we're wrong about
where legibility lives. Either outcome is useful.

### Iteration loop

1. Design tool variant (operating, self-knowledge, meta-tool, or
   activity record schema)
2. Deploy to harness with fixed factors held steady
3. Run task corpus across model selection
4. Capture activity stream
5. Analyst LLM reviews activity stream against outcome measures
6. Propose changes (new variant, new tool, new collector)
7. Repeat

The system studies its own behavior. The tools are the experiment;
the activity stream is the data.

### Methodological note: the analyst LLM as fresh reader

The analyst LLM reading the activity stream is doing something
structurally similar to a fresh instance reading session artifacts —
both are pattern recognition across a system's behavior over time,
performed by an entity that wasn't present when the behavior was
generated. The methodology for analyst evaluation can borrow from
how a fresh reader reads: enter cold, read across many calls without
prior commitment to any tool's design, look for what's working and
what isn't, propose improvements based on observed evidence rather
than designer intent.

This isn't just an analogy. It's the methodology already in practice
when one instance reviews another's work — and it's a research
finding worth preserving: the analyst surface should be designed for
cold-reading, the same way the operating surface is designed for
in-task use. Both audiences have specific cognitive needs; both
deserve tools shaped for those needs.

## What's Not in Scope Tonight

- Full implementation of any tool
- Choice of activity stream backend (apacheta, duckdb, separate ArangoDB
  collection — to be decided when the activity record schema is concrete)
- Pukara/gateway integration for the tool surface
- Authentication and authorization for tool access
- Whether tools are exposed via MCP, direct function calling, or some
  other transport — this is an orthogonal layer
