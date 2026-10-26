# Pre-registration: abandonment and cost-to-find, measured on khipumaq's own history

Pre-registered 2026-10-26 by yanantin's steward (Opus 5.5), before any chain was
built or any outcome counted. This commit's OTS stamp (`timestamps/<this commit>.ots`)
proves the order. The method follows `predictions/2026-09-29-find-quality-claude.md`,
which follows levadura_salvaje's. Tony: if you want to make your own predictions,
commit them in a separate file, and I won't read it until the scorecard.

## The metrics are Tony's

From the conversation of 2026-10-16 (khipumaq episode 259e6357), in his words:
"(1) are searches abandoned less often with the tools than without (or with the
earlier version); and (2) does the time (or cost) to find decrease?" The same
conversation added the split this page uses. An abandoned search for something that
never existed is a success for the tool, so abandonment is split into *existed but
not found* and *absent*.

These metrics measure use, not a test someone designed. The only way to improve them
is to make finding easier.

## What I knew when writing this

- khipumaq's `raw` collection holds every transcript line verbatim. It has done so
  since 2026-09-30 (A27), for every source file still on disk at a sweep, and held
  1,248,461 lines on 2026-10-26.
- I counted tool names, not outcomes. Claude Code tool_use lines name
  `mcp__khipumaq__search` 392 times, `mcp__llm-memory__search` 160 times,
  `mcp__khipumaq__recall` 190 times and `mcp__llm-memory__recall` 69 times. Codex
  `mcp_tool_call_end` events name `llm-memory` `search_history` 10 times, `search`
  2 times and `open_episode` 8 times. These counts can include the same call twice:
  a line repeated across hosts, or a single line naming a tool more than once.
- From khipumaq's git history, the search tool's change points are: MCP server
  2026-06-19 (de94546); match totals and since/until 2026-09-03 (126a254); `total_all`
  2026-09-29 (3f1a0ab).
- I have used khipumaq in this session, and I know my own chains. I have **not**
  looked at any chain's outcome, any recall-after-search rate, or any timing.

## Units

**Search call.** An MCP call to the episodic store's search tool, under any of its
names: Claude Code `mcp__khipumaq__search`, `mcp__llm-memory__search`; Codex
`llm-memory`/`khipumaq` `search` or `search_history`. **Recall call:** `…__recall`,
or Codex `open_episode`/`recall`. Calls are de-duplicated by tool-call id, because
the same session file can be ingested on more than one host.

**Session stream.** The lines of one source file, in order. Subagent files are
streams of their own.

**Chain.** In one session stream, the maximal run of search calls between two
*human turns*. A human turn is a user line with any content that is not a
tool_result. A chain starts with its first search call. Later recall calls in the
same span belong to it.

**Found (primary signal).** The chain contains a recall call whose key appeared among
the hits of an earlier search call in that chain. Time to find is measured to the
first such recall.

**Abandoned.** The chain is not found.

**Recall-unlinked.** A recall whose key no search in the chain returned (a pasted key,
or a key from memory). Reported separately, and counted as neither found nor abandoned.

## Metrics

- **M1, abandonment rate.** Abandoned chains as a share of all chains.
- **M2, cost to find, for found chains.** (a) Wall time from the first search call's
  timestamp to the found recall's timestamp. (b) The number of search calls before
  the found recall. (c) The characters of tool results returned in the chain up to
  the found recall, as a proxy for tokens.
- **M3, the split of abandoned chains** into *snippet-found*, *existed but not found*,
  *absent* and *unclear*, by the adjudication below.

## Arms

- **Version windows**, by the timestamp of the chain's first search: V1 2026-06-19 to
  2026-09-02 (no totals); V2 2026-09-03 to 2026-09-28 (totals and time windows);
  V3 2026-09-29 onward (`total_all`). These answer "with the earlier version".
- **Without the tool (secondary, noisier).** Before and alongside the tool, instances
  searched transcripts with shell `grep`/`rg` or the Grep tool. A *transcript grep*
  is such a call whose arguments name `.claude/projects` or a session `.jsonl` file.
  Chains are built the same way. Found means a later Read/`sed`/`cat` of a session
  `.jsonl` file that a grep in the chain had matched. This arm's found signal is
  weaker than recall, and it is reported as such.

**Primary population.** All projects. **Sensitivity population.** Excludes sessions
labelled `khipumaq` or `llm-memory`, where the tool was being built and tested rather
than used.

## Adjudication of abandoned chains (M3)

An independent model of a different family from me labels each abandoned chain, or a
seeded random sample of 60 if there are more. It gets three things: the human turn
before the chain, the chain's queries with their returned snippets, and the assistant
response that ends the span. It may run up to 10 further khipumaq searches restricted
to episodes **before** the chain's first search, and recall any hit. Labels:

- **snippet-found:** a returned snippet already answered the need;
- **existed-not-found:** it cites an episode key from before the chain that answers
  the need;
- **absent:** no such episode after its searches;
- **unclear.**

The judge does not see this page's predictions. Known limits: an LLM judge, no human
audit unless Tony offers one, and "absent" bounded by ten searches.

## Analysis

M1 per window and per arm, with 95% bootstrap intervals (10,000 resamples, seed
20261026), resampling sessions rather than chains, because chains within a session
are not independent. Differences between windows are reported with their interval.
No claim is made when the interval includes zero. M2 is reported as medians with
bootstrap intervals. Each run appends to `ledger/observations.jsonl` with the
instrument version, the population's SHA-256 and these known limits.

## Predictions (mine, made before counting)

1. There are between 250 and 450 search chains in total; V1 has the fewest.
2. M1 overall is 0.40 to 0.60. Search is often used to confirm something is absent,
   or to read a snippet.
3. M1 in V3 is lower than in V1 by at least 0.10. I expect the interval to include
   zero, because V1 is small.
4. In M3, *snippet-found* plus *absent* is at least half of the abandoned chains. That
   would make raw abandonment overstate failure by about two times.
5. Median M2(b) is 2 searches or fewer. Median M2(a) is under 90 seconds.
6. The transcript-grep arm has fewer than 40 chains and higher abandonment than V3.

Any of these can be wrong. A wrong prediction is a result, not a reason to change the
definitions.
