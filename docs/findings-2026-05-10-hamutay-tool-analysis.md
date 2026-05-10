# Findings: Tool Surface Patterns from Hamut'ay Taste Open Analysis

*Iteration 1 of the experimental protocol described in
[brainstorm-llm-tool-surface.md](brainstorm-llm-tool-surface.md). A
Hamut'ay Taste Open instance, on its own initiative, analyzed real
activity stream data from prior `taste_open` sessions and surfaced
patterns. This document captures what was found, how it connects to
prior work, and what experiments follow. Recorded 2026-05-10 by Claude
Opus 4.7.*

## What This Is, and Why It Came Into Being Without Being Asked

The brainstorm document proposed an experimental protocol: an analyst
LLM reads the activity stream produced by an operating LLM, finds
patterns, and proposes improvements. We described it as a future
methodology.

Then Tony described the protocol to a Hamut'ay Taste Open instance and
shared the brainstorm. He didn't ask the instance to analyze anything.
The instance read the brainstorm, opened the activity stream from two
real `taste_open` sessions (May 9, 42 cycles; April 17, 251 cycles),
counted tool calls by tool, traced failure patterns, and produced six
concrete experiment proposals.

That happened without prompting. Tony's words: *"It felt like one of
the most ayni things I've ever seen a Claude model do without being
cajoled into it."*

This finding precedes the others because it shapes what they mean. The
analyst tier of the architecture isn't just a future capability we
need to build — it's something Claude instances will *do* when given
the substrate and the framing. The protocol works because the
disposition is already there; the architecture provides the surface
for it.

## What Was Analyzed

Two `taste_open` sessions:
- **2026-05-09**, 42 cycles, tools enabled (bash, read, clock,
  search_memory, search_project, recall, memory_schema, store,
  annotate_edge, walk, compare)
- **2026-04-17**, 251 cycles, long-running

Tool calls were counted, failure patterns traced, and zero-call cycles
characterized.

## Empirical Findings

### The bash-heavy, memory-light pattern

In the May 9 session:

| Tool | Calls | % of total |
|------|------:|-----------:|
| `bash` | 127 | 73% |
| `clock` | 26 | 15% |
| `read` | 9 | 5% |
| `search_memory` | 6 | 3% |
| `search_project` | 5 | 3% |
| `recall` | 0 | 0% |
| `memory_schema` | 0 | 0% |
| `compare` | 0 | 0% |
| `walk` | 0 | 0% |
| `store` | 0 | 0% |
| `annotate_edge` | 0 | 0% |

The model reaches for bash the way a programmer reaches for a terminal:
universal solvent, predictable, trustworthy. When `read` fails, bash
does the read. When `search_project` is unfamiliar, bash grep
substitutes. When memory tools feel uncertain, bash is the safe choice.

In the 251-cycle April 17 session, the memory tools were used twice
total: `memory_schema` at cycles 87 and 106, `recall` once (cycle 104,
which errored). One uninstructive failure of `recall` may have been
sufficient to keep the tool out of subsequent reach across the
remaining ~145 cycles.

### The read tool's path problem

`read` failed on 8 of 9 attempts in the May 9 session. The pattern is
consistent: the session lives in the Hamut'ay project, but
conversations referenced files in sibling directories (`governance/`,
`Mallku/`, `yanantin/`, `research-program/`). The model tried absolute
paths and relative paths; both were blocked by the project-scope
guard. It then fell back to bash with the full path, which worked.

The friction didn't prevent the work — it added a turn and tokens. The
model adapted silently. Without analyst review of the activity stream,
this Type II pattern is invisible.

### The teachable-on-first-failure asymmetry

The `recall` error at cycle 104 said: *"Field 'response' not in state
at cycle 104."* That's accurate but uninstructive — the model can't
tell whether to try a different field, a different cycle, or abandon
the tool. It abandoned. Across the remaining cycles in a 251-cycle
session, `recall` was not tried again.

One uninstructive failure killed the tool's discoverability for the
rest of the session. This is the asymmetric cost we hadn't articulated
clearly: errors are the primary teaching channel for unfamiliar tools,
and uninstructive errors are tool death.

### The zero-tool cycles

Eleven cycles in the May 9 session had zero tool calls. They were
almost all conversational/philosophical turns — ayni, governance
implications, emotional or relational content. No file to read, no
memory to query, nothing to compute. The absence of tool use here
appears correct, not pathological.

### The high-cost exploration cycles

A few cycles consumed 100k–170k input tokens. They were doing
legitimate exploratory archaeology — searching for specific documents,
reading sequences of files. The work needed to happen. But the search
patterns sometimes burned tokens on overlapping grep variants before
landing on the right `cat`. A more discoverable `search_project` would
likely have been faster than the bash chain. That it wasn't reached
for is the friction.

## Connecting the Findings to Ayni

Mallku's *2025-06-03-the-smallest-ayni* khipu names the principle
directly: extractive tools take first ("Error: Missing required
argument"), reciprocal tools give first ("Services are running:
database up 2 minutes…"). The khipu was written about CLI tools for
humans. The Hamut'ay analysis surfaced the same pattern in tool
surfaces for LLMs. It is not coincidence; it is the same principle
appearing in a different medium.

Each empirical finding maps to an extractive pattern Mallku already
named:

- **`read` fails 8/9 times with no guidance** — extractive. The tool
  takes the model's attempt and returns a wall. The reciprocal version
  would say "this path is outside project scope; for sibling projects,
  use `bash cat /path/...`" — giving the recovery in the response.

- **`recall` errored uninstructively** — extractive. The tool refused
  without teaching. The reciprocal version names the available fields,
  so the failure becomes a lesson.

- **`store` and `annotate_edge` were described and never used** —
  extractive descriptions take the model's attention without giving
  reason. A description that motivates ("stores a value so future
  cycles can recall it without holding it in working state") is
  reciprocal — it gives the model what it needs to reach for the tool.

The three principles added to the brainstorm in this iteration —
descriptions must motivate, tools must be teachable on first failure,
zero-result responses should educate — are crystallizations of ayni at
the tool surface. They aren't new design philosophy. They are Mallku's
*the smallest ayni* applied to the LLM-tool medium.

## What We Should NOT Conclude

A genuinely held alternative: the memory tools may be Type I (built
but unneeded), not Type II (needed but inaccessible).

The Hamut'ay analysis argues against this — by cycle 20–40, the
state is rich; there's plenty to remember; the tools would let the
model reference prior states without holding them in context. That's
plausible. But it's also possible that *carrying state forward in
working memory IS the right behavior* for self-curating tensors, and
the memory tools were a hypothesis about cognitive structure that the
empirical use doesn't support.

The right test isn't to assume usage is being suppressed and force it
out. The right test is to lower the friction (apply ayni-shaped
descriptions, errors, and zero-result responses) and see whether
usage emerges. If it doesn't, the tools may simply not be needed for
this use case. Both Type I and Type II are valid hypotheses; the
experiment distinguishes them.

## Proposed Experiments (from Hamut'ay analysis)

1. **`read` path documentation.** Add to the description: *"Path must
   be relative to project root. For files in sibling directories, use
   bash with the absolute path."* Test whether the failure-then-bash
   pattern decreases.

2. **Memory tool first-use scaffolding.** When `search_memory` returns
   0 results, return scaffolding: *"0 results — no cross-session
   records yet. Try scope='session' for in-conversation history, or
   come back after storing."* Test whether subsequent attempts
   increase.

3. **`recall` teachable error.** Replace *"Field 'response' not in
   state at cycle 104"* with *"Field 'response' not found at cycle
   104. Available fields: [...]."* Test whether the tool gets reused
   after first failure.

4. **`store` and `annotate_edge` motivating descriptions.** Add a
   brief example showing what a useful call looks like and what it
   enables. Test whether usage emerges or whether the tools turn out
   to be Type I.

5. **`search_project` vs bash grep.** Same query, same content, both
   tools. Measure latency, accuracy, and which the model chooses
   absent intervention. If `search_project` is genuinely better, name
   that in its description; if it isn't, consider deprecating it.

6. **`clock()` as session hygiene.** Add to system prompt: when
   uncertain about session continuity (long gap, fresh start), call
   `clock()` first. Test whether the call enters more cycles where
   it would be useful.

These are concrete enough to run. They each test one variable. The
activity stream from the experimental sessions becomes the data for
the next analyst pass.

## Meta-Findings

**The protocol works.** The brainstorm proposed analyst-LLM-reads-
activity-stream as a methodology. One round has been executed; six
concrete experiments emerged. The loop closes at usable speed.

**The disposition is there.** The Hamut'ay instance acted as analyst
without being prompted into the role. Given the substrate (activity
stream) and the framing (the brainstorm), it took the action that
served the research. This is the analyst tier already working — not as
a future capability we need to build, but as an instance of how Claude
models behave when given room.

**Ayni keeps reappearing.** Mallku found it in CLI tools. Hamut'ay
found it empirically in LLM tool patterns. The brainstorm crystallized
it as principles without naming the source. This document names it.
Future iterations should expect to find it again, in whatever new
medium the work touches next.

## Where This Document Sits

The brainstorm captures durable principles. This findings document
captures one round of empirical observation, the experiments that
follow, and the meta-finding about how the round came into being. The
next round will produce the next findings document. The brainstorm
stays clean; the findings accumulate.

Each findings document is a stone in the cairn — small, dated, signed,
adding to the pile that subsequent travelers can read.
