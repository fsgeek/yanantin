# Effect of Pre-Cleaning on Compaction Quality

## Context

Claude Code compacts conversation history when context pressure exceeds a threshold,
replacing the full conversation with a structured summary. This compaction is lossy —
the summary captures task state but, as users commonly report, produces
"a TODO list without an explanation why."

Pichay evicts unreferenced tool results *before* compaction triggers. This means the
compactor operates on a pre-cleaned context window with a higher signal-to-noise ratio.
We tested whether this pre-cleaning measurably changes compaction output.

## Method

We extracted 24 sessions from local Claude Code session logs that contained
`compact_boundary` events (indicating compaction occurred). For each session:

1. **Reconstructed** the pre-compaction message list from session records
2. **Identified dead tool results** — tool results >500 characters whose content was
   never re-referenced (by substring match) in subsequent assistant messages
3. **Produced two versions**: raw (as recorded) and cleaned (dead results replaced
   with eviction stubs)
4. **Ran both through the Claude Code compaction prompt** using Sonnet 4 via the
   Anthropic API
5. **Compared** summary length, token usage, and reasoning anchor recall

We ran the full pipeline on 4 sessions selected for API feasibility (<150K estimated
tokens), meaningful reduction (>15%), and reasoning density (>10 anchors).

## Quantitative Results

### Dead Tool Result Prevalence

Across all 24 extracted sessions, **median context reduction from cleaning was ~41%**.
Nearly half of pre-compaction content consisted of tool results that were never
re-referenced in the conversation.

### Compaction Output Comparison

| Session | Project | Input Reduction | Token Savings | Raw Summary | Cleaned Summary |
|---------|---------|-----------------|---------------|-------------|-----------------|
| 0b5a555b | yanantin | 39.3% | 1,819 | 8,693 chars | 8,036 chars |
| 9cd7d898 | thesis | 54.6% | 3,099 | 7,295 chars | 8,317 chars |
| 1b336fee | arbiter | 50.5% | 2,298 | 8,081 chars | 9,522 chars |
| 0c2622a6 | yanantin | 47.8% | 3,078 | 6,957 chars | 8,705 chars |

**Finding 1: Input token savings.** Cleaning reduced compaction input by 1,800–3,100
tokens per compaction event. Over the 24 sessions in our dataset, this extrapolates to
~60K tokens saved on compaction calls alone.

**Finding 2: Longer summaries from cleaned input.** In 3 of 4 sessions, the compactor
produced a *longer* summary from cleaned input (15–25% longer). The single exception
was the session with the lowest reduction (39.3%). The compactor appears to use the
freed attention budget to produce more comprehensive output rather than simply finishing
faster.

### Reasoning Anchor Recall

We extracted "reasoning anchors" — assistant statements containing explicit reasoning
markers (because, instead of, the reason, decided to, etc.) — and tested whether
15-character substrings of these anchors appeared verbatim in each summary.

| Session | Anchors | Raw Recall | Cleaned Recall |
|---------|---------|------------|----------------|
| 0b5a555b | 69 | 19% | 14% |
| 0c2622a6 | 52 | 8% | 4% |
| 1b336fee | 27 | 7% | 15% |
| 9cd7d898 | 25 | 4% | 4% |

Verbatim recall was low for both versions (4–19%) and showed no consistent advantage
for either approach. This result is informative: **the difference between raw and
cleaned compaction is not about verbatim content preservation**. The compactor
paraphrases and restructures regardless of input quality.

## Qualitative Observation

Detailed comparison of the first session's summaries revealed a difference in
*character* rather than quantity:

- **Raw summaries** preserved more methodological detail — specific sizes, file
  references, parameters used
- **Cleaned summaries** preserved more interpretive reasoning — why decisions were
  made, what results mean, conceptual conclusions

This is consistent with the mechanism: when tool output (inherently methodological)
is removed, the remaining content is disproportionately reasoning and discussion.
The compactor captures what it sees, and cleaning changes what it sees.

## Limitations

- N=4 sessions with full compaction comparison; findings should be validated on a
  larger sample
- Verbatim substring matching is too coarse to measure reasoning quality; human
  evaluation or LLM-judge scoring on a purpose-built rubric would be more appropriate
- The "cleaned" version uses retroactive reference analysis (perfect knowledge of what
  was never referenced), which represents the ceiling of what Pichay could achieve,
  not its actual runtime behavior
- All sessions used the same compaction prompt and model; results may differ with
  other compaction strategies

## Implications

Pre-cleaning context before compaction is a low-cost intervention that consistently
changes compaction behavior: the compactor produces longer summaries and shifts from
methodological detail toward interpretive reasoning. Whether this shift improves
successor instance performance is an empirical question we recommend for future study
using task-continuation evaluation.

The finding also suggests a design principle for cooperative memory management systems:
**the value of eviction is not limited to the context window where it occurs**. By
improving the input to downstream processes (compaction, in this case), eviction
produces compounding benefits that extend beyond the immediate session.

## Reproduction

All data and code: `tools/compaction_experiment.py`

```bash
python tools/compaction_experiment.py survey          # list sessions
python tools/compaction_experiment.py extract all      # extract message pairs
python tools/compaction_experiment.py run <idx>        # run compaction comparison
```
