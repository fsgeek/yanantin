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
- `top_directories`: up to 10 directories with counts, at the deepest level that still summarizes
  (see the interface). This is the brainstorm's diversity block, and the cue for narrowing ("626 of
  1,409 are under `.cache/uv`");
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

6. **An unknown machine name raises `ValueError`, naming the indexed machines.** An empty result would
   read as "no such file there". The real case: Tony says "gazelle", the index knows it as
   `pop-os`. (The spec was silent until the blind tests forced the choice. Codex's tests expected
   zero results; its two assertions were changed to match this decision.)
7. **Coverage lists every registered source, walked or not.** "Registered, never walked" is part of
   what makes "no matches" believable.
8. **`path_segments` are directory names:** a segment that matches only the file name does not count
   (caught by the blind tests).

## Judging the tool when its customers are AI

Tony, 2026-11-09: AI customers "will tend to accept what [is] offered and not provide useful
(actionable) information on what would improve the tool." So the tool is judged by behavior, not by
asking:
- **fallback**: a `find_objects` call followed by `find`/`rg`/`ls` for the same thing (from khipumaq's
  session records) is a reported failure;
- **refinement**: a query followed by a narrower one means the summary didn't do its job;
- **repetition**: `duplicate_of`;
- **use**: whether a returned path is read or edited within the next few turns.

Actionable criticism comes from adversarial roles (break it), not satisfaction questions (rate it).

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

## Interface (Python)

```python
from yanantin.find import CompiledQuery, FindResult, find_objects, FIND_PROVIDER_ID

query = CompiledQuery(name=None, name_contains=None, path_segments=(), modified_after=None,
                      modified_before=None, machines=(), limit=20)
result = find_objects(db, query, *, activity, obfuscator,
                      collection="Objects", view="objects_find", registrants="StorageRegistrants")
```

- `CompiledQuery` is frozen. It raises `ValueError` when no condition is given, or when
  `limit < 0`. `modified_after` and `modified_before` are timezone-aware datetimes. `after` is
  inclusive and `before` is exclusive. `machines` are hostnames.
- `activity` is an `ActivityStreamStore`. Coverage reads each source's landing facts through it:
  the latest `data["walk"]["started"]` among facts with `data["walk"]["all_names"]`, as
  `recorder/storage/local/linux/walks.py:latest_walk_start` computes it. The call appends its own
  fact through it under `FIND_PROVIDER_ID = uuid5(NAMESPACE_DNS, "yanantin.find")`.
- A source's machine name is the parenthesized suffix of its registrant's `registrant_name`, as in
  `"linux-local-storage collector (wam-desktop)"`. Without a suffix it is the first 8 characters of
  the source ID. Sources are provider UUIDs as strings.
- `FindResult` (frozen):
  - `total_matched: int`
  - `by_machine: dict[str, int]`
  - `top_directories: list[tuple[str, int]]`: at most 10, by count descending (ties by name). A
    directory is `file://` plus the first *k* components of the hit's directory path, where *k* is
    the **deepest depth, at most 6, at which the top 10 directories hold at least 75% of all
    matches**. *k* = 1 always qualifies. A hit whose directory has fewer than *k* components counts
    under its whole directory. Revised 2026-11-09 from "up to its last /", which on real data
    spread 1,409 `pyproject.toml` files over about 1,400 directories with a top bucket of 4. The new
    rule gives depth 4 (`/home/tony/.cache/uv`) for those, depth 5 for a month's window, and depth 6
    for `.ssh`.
  - `coverage: list[dict]`: each `{"machine": str, "last_walk": datetime | None}`
  - `hits: list[dict]`: each `{"uri", "machine", "modified", "size"}`, newest `modified` first,
    at most `limit`
  - `fact_id: UUID`: the fact recorded for this call
  - `duplicate_of: UUID | None`
- The recorded fact's `data` holds `query` (the arguments), `query_shape`, `total_matched`,
  `by_machine`, `returned` (the hit URIs), `elapsed_ms`, and `duplicate_of`. The `query_shape` of
  two queries is equal when every condition is equal. `limit` is not a condition, and the order of
  `path_segments` and `machines` does not matter.
- A missing view raises; find never falls back to a scan.
