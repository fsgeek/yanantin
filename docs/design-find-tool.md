# The find tool, v1: files across machines, for instances and for Tony (2026-11-09)

*This builds on two earlier documents, which hold most of the reasoning:*
- *`docs/brainstorm-llm-tool-surface.md` (2026-05-10): tool legibility, `limit=0` returning
  counts, a diversity block, zero-result responses that teach, and one activity record per call;*
- *`docs/superpowers/specs/2026-06-16-index-backed-find-design.md`: time prunes first, the engine
  supplies `total_matched`, a find-event with `duplicate_of`, and fail-stop with no fallback.*

*This record adds what real use taught (the first-find case, 2026-10-29) and the decisions v1 makes.*

## Why now

The objects index holds 19M files from four machines and answers in milliseconds, but no instance
can call it: every query so far was hand-written Python and AQL. Tony's hypothesis: "a surprisingly
large amount of work is spent trying to find things … anything we can do that reduces tool output
is a win." The first real case (his 333-model sweep, wrongly remembered as "in GPN") showed:
- the remembered *where* was wrong and the *when* was right;
- the answer was split across khipumaq and the index;
- the miss was self-inflicted (`LIMIT 30` plus `| tail`, with no counts first).

## The tool

`find_objects`, one verb for v1. `get_object` and `sample_objects` (from the brainstorm) follow
once the case log shows they are needed.

Arguments. Every one is optional, but at least one condition is required.
- `name`: exact file name.
- `name_contains`: a substring of the name. Measured on 19M objects: 150 ms warm, 3.3 s cold.
  A prefix match takes 9 ms. The description states these costs.
- `path_segments`: directory names that must all appear in the path, matched exactly
  (`.ssh` is not `ssh`).
- `modified_after` / `modified_before`: ISO dates. **The cheapest narrowing there is**, so the
  description says to use it whenever the person remembers *when*.
- `machines`: hostnames to restrict to. **The default is every machine.** A machine is a facet,
  not a scope, because people remember *when* and *why*, not *where*.
- `limit`: the number of paths returned, default 20. `limit=0` returns the summary only.

The response always leads with the summary:
- `total_matched`, from the engine;
- `by_machine`: counts per hostname;
- `top_directories`: up to 10 parent directories with counts. This is the brainstorm's diversity
  block, and the cue for narrowing ("410 of 592 are under `.cache/uv`");
- `coverage`: each indexed machine with the time of its last landed walk, and the plain statement
  that nothing else is searched (Windows drives, the Mac and cloud accounts, until they are walked).

Then up to `limit` hits, each `{uri, machine, modified, size}`. A zero-result response repeats
`coverage`, so "not found" can't be mistaken for "doesn't exist."

## Recording

Each call appends one fact to `activity_facts` on arango-objects, under the find tool's own
provider. The fact holds the arguments, `total_matched`, `by_machine`, the returned URIs,
`elapsed_ms`, a normalized `query_shape`, and `duplicate_of` (the key of the most recent fact with
the same shape). Tony asked: "How many times do you reach for the search tool and run the same
search you've run before?" `duplicate_of` measures it. The case log is a query over these facts,
and find's own history can be found by time like anything else.

## Decisions

1. **A structured query type** (`CompiledQuery`, gh #19): frozen, with no raw strings reaching
   AQL. Every value is a bind variable.
2. **Fail-stop.** If the view is missing, find raises; it never falls back to a scan.
3. **Machine names** come from the registrant name, e.g. `… collector (wam-desktop)`. A source
   whose registrant names no host (this WSL) is labelled by its short ID until the
   source→hostname map exists.
4. **The time field is `modified` for v1.** `created` (statx birth time, Linux only so far)
   comes later.
5. **Two front ends, one core:** an MCP server for instances, and a CLI for Tony that reads one
   query per line from a file or interactively, through the same loop.

## Tests (live `apacheta_test`, plain and obfuscated, no mocks)

- The summary is correct with `limit=0`: totals, per-machine counts, directories.
- `name_contains` and `name` agree on an exact name.
- The time window narrows, and its bounds are inclusive and exclusive as documented.
- A zero-result response carries coverage.
- A repeated query records `duplicate_of` pointing at the first query's fact.
- Nothing asked → refused. Missing view → raises.

## Not in v1

Ranking (results are ordered by `modified`, newest first), content search, the khipumaq join (the
first case crossed stores, and that join is the north star's cross-tenant seam, its own design),
and cloud and Windows sources (they wait for the identity design).
