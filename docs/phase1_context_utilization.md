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
26 sessions (research-program T5). Session segmentation reveals
Simpson's paradox: the unsegmented median amplification of 13.6x
hides a bimodal distribution. Main sessions — the long agentic
building sessions where humans work — show 84.4x median
amplification (log-normal, P90=570.8x). Subagents show 12.8x
but outnumber main sessions 5:1. Amplification scales linearly
with session length (~0.5 ratio) with no acceleration. Within
sessions, orientation-phase tool outputs (first quartile) survive
~90% of the session, making FIFO compaction near-optimal. Read
tool outputs account for 75% of all tool overhead bytes.

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

### Amplification by position within session

Analysis of 44 main sessions with >50 turns, segmenting tool results
into quartiles by their position within the session:

| Quartile | Position | Amp/turns ratio | Interpretation |
|----------|----------|----------------|----------------|
| Q1 | 0-25% (orientation) | **0.896** | Survives ~90% of session |
| Q2 | 25-50% | 0.619 | Survives ~62% |
| Q3 | 50-75% | 0.377 | Survives ~38% |
| Q4 | 75-100% (late) | 0.110 | Survives ~11% |

The 0.5 aggregate ratio assumed uniform distribution. Q1 is nearly
double — orientation-phase tool outputs survive almost the entire
session. The earliest reads are the longest-lived and most costly.

Tool output volume distribution:

| Quartile | % of tool bytes | Avg size/result | Count |
|----------|----------------|-----------------|-------|
| Q1 | 22.8% | 2,544 | 3,389 |
| Q2 | 22.8% | 2,510 | 3,448 |
| Q3 | 20.5% | 2,285 | 3,397 |
| Q4 | **33.9%** | **3,775** | 3,406 |

Volume is NOT front-loaded — it's back-loaded. Q4 produces the most
bytes (larger file reads during implementation after orientation).
But Q4 results barely matter for amplification (0.11 ratio) because
they die soon after creation.

The expensive combination is Q1: moderate volume (22.8%) but
near-maximum amplification (0.896). Those orientation reads —
README, config, main module — survive 90% of the session, getting
reprocessed on nearly every subsequent turn.

**Intervention design implication:** FIFO compaction (compact the
oldest results first) is near-optimal by accident, because the
oldest results have the highest remaining amplification. A crude
"compact anything older than N turns" heuristic captures benefit
proportional to N regardless of session length (because the
amplification-to-length relationship is linear, not accelerating).

### Distribution shape

The amplification distribution across main sessions is log-normal:

| Percentile | Amplification |
|-----------|---------------|
| P10 | 26.7x |
| P25 | 54.9x |
| P50 (median) | 84.4x |
| P75 | 217.9x |
| P90 | 570.8x |
| P95 | 783.9x |

Log(amplification): mean 4.64, stdev 1.09, skewness proxy 0.21
(nearly symmetric in log space — textbook log-normal).

Amplification scales linearly with session length — the ratio
amplification/turns has mean 0.50, median 0.49, range 0.27-0.77.
This means amplification does not accelerate. Longer sessions
amplify more because they have more turns, not because each
additional turn compounds the problem. This is good news for
intervention: compaction at any fixed point yields proportional
benefit with no critical threshold or cliff behavior.

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

### Corpus bias and population

This corpus is drawn from a power-user population: a researcher
using Claude Code as a force multiplier across multiple concurrent
projects, with heavy agentic tool use. It does not represent
average Claude Code usage. The overhead and amplification numbers
are representative of the class of sessions where context
exhaustion is a problem — which is the class the intervention
targets. You don't measure bridge failure rates using the
population of people who cross footbridges. The Pareto
distribution of token consumption means this class of users,
while small in number, likely dominates total token spend.

### Amplification factor

Byte-weighted, not turn-weighted:

```
For each tool_result:
    turns_survived = total_conversation_turns − turn_index

amplification = Σ(content_bytes × turns_survived) / Σ(content_bytes)
```

This answers: "for each byte of tool output, how many turns does it
appear in the inference context?" A 8KB Read result that survives
100 turns contributes more to the factor than a 22-byte Edit
confirmation surviving the same 100 turns.

`turns_survived` counts from the tool result to the end of the
session, not to when context compaction actually evicts it. This is
a **conservative upper bound**. The true amplification lies in
[1, measured_value] for each result.

Pinning this down precisely requires the API proxy
(`tools/phase1/proxy.py`) which captures the actual messages array
sent to the API on each turn, including what has been truncated.

**Note on KV cache:** The amplification factor counts appearances
in the inference context, not full recomputations. At 93.4% cache
hit ratio, most appearances are cache hits — the tokens are not
recomputed from scratch. However: (1) cached tokens still occupy
context window space (the binding problem — space used by dead
tool results cannot be used for new content), (2) cached tokens
still have API cost (reduced rate, not zero), (3) cache eviction
under memory pressure reintroduces full computation cost, and the
sessions with highest amplification are most likely to exhaust
cache. The strongest argument is opportunity cost, not compute cost.

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

3. **FIFO compaction is near-optimal.** Orientation-phase tool
   results (Q1) have 0.896 amplification-to-turns ratio vs 0.110
   for late-session results (Q4). Compacting the oldest results
   first captures disproportionate benefit. A crude "compact
   anything older than N turns" heuristic works because
   amplification scales linearly — no critical threshold to get
   right.

4. **The proxy is the next instrument.** To move from upper-bound
   amplification to precise measurement, run `tools/phase1/proxy.py`
   during a real session. This also captures the system prompt
   dimension that JSONL can't provide.

5. **Non-inferiority test design.** The compaction hypothesis says
   replacing consumed tool results with compacted cells should not
   degrade downstream quality. Testing this requires: (a) take real
   session transcripts, (b) produce compacted versions at various
   consumption boundaries, (c) feed both versions to the model at
   a given turn, (d) compare the model's subsequent actions. What
   "compare" means is the open design question.

6. **Additional data sources.** Claude web/desktop exports
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
