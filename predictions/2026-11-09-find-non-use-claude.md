# Pre-registration: do instances use the find tool, or keep reaching for the shell?

Pre-registered 2026-11-09T19:34Z by yanantin's steward (Opus 5.5). No session after the tool's
registration has been examined, and none of the numbers below has been computed for any window.
The instrument will be written after this page is committed.

## Why

Tony, 2026-11-09: "The hardest customers for Yanantin to gauge will be AI. They will tend to accept
what [is] offered and not provide useful (actionable) information on what would improve the tool for
them." An AI customer that keeps using `find` out of habit will never say so. So this measures
behavior, not opinion (docs/design-find-tool.md, "Judging the tool when its customers are AI").

## Population

- Claude Code sessions on WAM-THREADRIPPER (transcripts under `~/.claude/projects/`), in any project.
  The yanantin MCP server is registered user-wide on this machine only (2026-11-09). Sessions
  elsewhere never had it.
- **After (A):** sessions whose first line is at or after **2026-11-09T19:34Z**. A running session
  doesn't load a newly registered server.
- **Before (B):** sessions that both start and end between 2026-10-12T19:34Z and
  2026-11-09T19:34Z (four weeks).
- **Excluded:** sessions spanning the cutoff; this steward's own session (d02f77a0-…); Codex
  rollouts (no MCP). Subagent transcripts are included and reported separately.

## Definitions

- **File-location shell call:** a Bash tool call whose command runs `find` with
  `-name|-iname|-path|-ipath|-regex`, or `locate`, `plocate`, `fd`, `fdfind`, `rg --files`, or
  `rg -g`. Content search (`rg PATTERN`, `grep`) is out of scope: find_objects does not search
  content.
- **Outside-scope:** the call's search root is `/`, `~`, `$HOME`, an absolute path not under the
  session's cwd, or a path on another machine via ssh. Searches rooted inside the session's cwd are
  in scope for the shell and are reported but not counted as non-use.
- **find call:** a tool call to `mcp__yanantin__find_objects`.

## Measures

- **M1 non-use (primary):** in A, outside-scope file-location shell calls ÷ (those + find calls),
  pooled over sessions. Reported with the per-session distribution.
- **M2 fallback:** the share of find calls followed, within the next 5 tool calls in the same
  session, by an outside-scope file-location shell call.
- **M3 use:** the share of find calls with at least one hit where a returned path (or its directory)
  appears in the input of one of the next 5 tool calls.
- **M4 repetition:** the share of find facts (activity_facts, provider `yanantin.find`) whose
  `duplicate_of` points to a fact from the same session. Facts carry no session ID, so the instrument
  joins on time and the transcript's call.
- **Context, not tested:** outside-scope file-location shell calls per session in B against A.

## When

When A holds at least 100 find calls, or on **2026-12-07**, whichever comes first. If A holds fewer
than 20 find calls by then, the result is reported as "too little use to measure", which is itself
a finding about non-use. M1 is still computed.

## Predictions (stated before any data)

1. **M1 ≥ 0.5.** Habit wins at least half the time in the first window. This is Tony's
   observation, made quantitative.
2. **M2 ≤ 0.2.** When an instance does use the tool, it rarely falls back.
3. **M3 ≥ 0.4.**
4. Outside-scope file-location shell calls per session fall from B to A, but by less than half.

## Decision rule

If M1 ≥ 0.5, the next step is to change **one** thing (the server's self-description first, then
the tool description) and re-measure over a fresh window with this same instrument. Never two
changes at once. If M2 > 0.2, the fallback calls are read one by one to find what the tool failed
to answer, before anything else changes.
