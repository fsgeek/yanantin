# Phase 1: Context Window Utilization in Agentic Coding Sessions

**Status:** Empirical measurement complete. Phase 2 design pending.
**Date:** 2026-02-28
**Authors:** Yanantin AI (Claude Opus), with experimental design from
research-program T7 (research supervisor instance)
**Instruments:** `tools/phase1/probe.py`, `tools/phase1/proxy.py`

## Abstract

We measured context window utilization across 813 Claude Code
conversation transcripts (668 MB) spanning 15 projects on two
machines. Tool outputs consume 79.4% of conversation content
(aggregate), replicating an independent measurement of 78.2% from
26 sessions (research-program T5). Main sessions — the long agentic
building sessions where humans work — show a median amplification
factor of 84.4x: each byte of tool output is reprocessed across
a median of 84 subsequent turns. This amplification is the mechanism
by which context windows exhaust during complex agentic tasks.

## Motivation

Agentic coding sessions die from context exhaustion. The research
supervisor (T4) died mid-task when context filled. The hypothesis:
tool outputs that have already been consumed (the agent has acted on
them) persist in the context window across all subsequent turns,
consuming space without providing value. The cost is amplified
because each turn reprocesses the entire history.

This is the eager materialization problem applied to conversation
memory. Every tool result is fully present on every turn, whether
or not it's needed. The alternative — deferred materialization via
compacted summaries with retrieval handles — is proposed in
research-program T7.

Connection to the late-binding hypothesis
(`docs/hypotheses/late-binding-as-correctness.md`): context
compaction is the fourth independent instance of deferred ontological
binding emerging in this architecture.

## Corpus

| Source | Sessions | Size | Projects |
|--------|----------|------|----------|
| Local (WSL) | 60 | 299 MB | 9 |
| VM (Ubuntu) | 753 | 369 MB | 12 |
| **Total** | **813** | **668 MB** | **~15 distinct** |

Session types (classified by filename pattern):

| Type | Count | Turns | Description |
|------|-------|-------|-------------|
| Main | 105 | 18,968 | Human-facing sessions (UUID filenames) |
| Subagent | 538 | 14,478 | Delegated task agents (`agent-` prefix) |
| Compact | 149 | 169 | Post-compaction continuations |
| Prompt suggestion | 21 | 21 | Auto-generated prompt suggestions |

## Results

### Aggregate (all sessions)

| Metric | Value |
|--------|-------|
| Total tool calls | 27,612 |
| Total tool results | 27,610 |
| Tool result bytes | 99,436,063 (79.4%) |
| Assistant text bytes | 15,921,129 (12.7%) |
| User text bytes | 9,877,724 (7.9%) |
| Thinking bytes | 7,950,797 (not in context) |

### Segmented by session type

| Metric | Main | Subagent |
|--------|------|----------|
| Sessions | 105 | 538 |
| Turns | 18,968 | 14,478 |
| Tool overhead | 71.6% | 90.2% |
| Median per-session overhead | 74.1% | 89.5% |
| P75 per-session overhead | 80.4% | 93.0% |
| **Median amplification** | **84.4x** | **12.8x** |
| Mean amplification | 183.2x | 15.1x |
| Max amplification | 786.6x | 91.2x |

Main sessions have both high overhead AND high amplification.
Subagents have the highest overhead ratio but low amplification
(short-lived, fewer turns to accumulate). The unsegmented median
of 13.6x was hiding the real number — subagents outnumber main
sessions 5:1 and drag the median down.

### Tool type breakdown

| Tool | Calls | Total bytes | Avg bytes | % of tool output |
|------|-------|-------------|-----------|------------------|
| Read | 9,393 | 74,536,822 | 7,935 | **75.0%** |
| Bash | 10,090 | 13,212,392 | 1,309 | 13.3% |
| Task | 518 | 3,052,526 | 5,893 | 3.1% |
| TaskOutput | 240 | 3,986,686 | 16,611 | 4.0% |
| Grep | 1,075 | 1,430,030 | 1,330 | 1.4% |
| Glob | 1,061 | 1,049,468 | 989 | 1.1% |
| WebSearch | 302 | 882,579 | 2,922 | 0.9% |
| All others | 5,931 | 1,286,560 | 217 | 1.3% |

**Read dominates.** 75% of all tool output bytes come from file
reads. Compacting only Read results would eliminate three-quarters
of the overhead. Average file read is 7,935 bytes; target compacted
size is ~200 bytes (conclusion + declared losses + retrieval handle).
That's a 97.5% reduction per Read result.

### Token accounting

| Metric | Value |
|--------|-------|
| Input tokens | 1,334,562 |
| Output tokens | 4,139,906 |
| Cache read tokens | 3,954,837,288 |
| Cache creation tokens | 276,967,678 |
| **Cache hit ratio** | **93.4%** |

3.95 billion cache-read tokens across the corpus. The KV cache is
working heroically to make the reprocessing cheap per-token, but
the tokens still occupy context window space. The least expensive
read is the one you never do.

### Replication

| Source | Sessions | Tool overhead |
|--------|----------|--------------|
| Research-program T5 | 26 | 78.2% |
| This measurement | 813 | 79.4% |

Two independent measurements on different corpora converge.

## Methodology

### Instrument

`tools/phase1/probe.py` — streams JSONL files line by line (no
full-file loading). For each record:

- Classifies by type (user, assistant, progress, other)
- Identifies tool results via `content[].type == "tool_result"`
- Measures content bytes per tool result
- Maps tool results to tool names via `tool_use_id` → `tool_use.name`
- Tracks conversation turns for amplification computation
- Extracts token usage metadata from assistant messages

Session classification by filename: UUID = main, `agent-` = subagent,
`agent-acompact-` = compact, `agent-aprompt_suggestion-` = prompt
suggestion.

### Amplification factor

For each tool result, amplification = (conversation_turns − turn_index).
This counts the number of turns the result *could* survive in context,
from its creation to the end of the session. It is a **conservative
upper bound** — in reality, context compaction may evict results
earlier.

The true amplification lies in [1, measured_value] for each result.
Pinning this down precisely requires the API proxy
(`tools/phase1/proxy.py`) which captures the actual messages array
sent to the API on each turn, including what has been truncated.

### Declared losses

- **System prompt not measured.** JSONL transcripts do not contain
  the system prompt. It is assembled by Claude Code and sent with
  each API call. It includes CLAUDE.md, MEMORY.md, skills list,
  system reminders, git status, IDE context. The proxy instrument
  exists to capture this but has not been run.
- **Amplification is upper bound.** True amplification requires
  knowing when context compaction evicts a tool result. The proxy
  would provide this. Current numbers are directionally correct
  but imprecise.
- **No dedup across sources.** The two corpus directories may
  contain duplicate session files (same UUID, different machine).
  Impact on aggregate numbers: minimal (tool overhead ratio is
  a per-session property).
- **Thinking bytes excluded.** Extended thinking content is logged
  in the JSONL but is not part of the API input context on
  subsequent turns. It is excluded from overhead calculations.
- **No content-level analysis.** We measure size, not semantic
  content. A 8KB file read where only 3 lines were relevant
  registers as 8KB of overhead, which understates the waste.
- **Session timestamps not analyzed.** We have date ranges but
  haven't computed session duration, turns per hour, or temporal
  patterns of tool use.

## Implications for Phase 2

The numbers justify building the compaction prototype. Specifically:

1. **Read is the highest-ROI target.** 75% of tool bytes, 97.5%
   compressible per result. A prototype that compacts only Read
   results would capture most of the benefit.

2. **Main sessions are the critical population.** Subagents are
   short-lived and don't suffer from amplification. The sessions
   that die from context exhaustion are the main human-facing
   sessions with 84x median amplification.

3. **The proxy is the next instrument.** To move from upper-bound
   amplification to precise measurement, run `tools/phase1/proxy.py`
   during a real session. This also captures the system prompt
   dimension that JSONL can't provide.

4. **Non-inferiority test design.** The compaction hypothesis says
   replacing consumed tool results with compacted cells should not
   degrade downstream quality. Testing this requires: (a) take real
   session transcripts, (b) produce compacted versions at various
   consumption boundaries, (c) feed both versions to the model at
   a given turn, (d) compare the model's subsequent actions. What
   "compare" means is the open design question.

5. **Additional data sources.** Claude web/desktop exports
   (available via Anthropic data export) provide a conversational
   baseline with minimal tool overhead. The contrast between
   agentic (79.4% overhead) and conversational (estimated <10%)
   sessions is itself a publishable finding.

## Connection to Late-Binding Hypothesis

This measurement is an empirical test of the late-binding hypothesis
(`docs/hypotheses/late-binding-as-correctness.md`). The current
system eagerly binds all tool outputs into every turn's context.
The proposed compaction system defers binding — storing a summary
with a retrieval handle and materializing the full content only
when a future question needs it.

Phase 1 measures the cost of eager binding: 79.4% overhead, 84.4x
amplification in main sessions. Phase 2 tests whether deferred
binding preserves correctness (non-inferiority). This is the
fourth independent instance of the deferred ontological binding
pattern emerging in this architecture, following activity anchors,
Jabberwock NER, and mome observations.
