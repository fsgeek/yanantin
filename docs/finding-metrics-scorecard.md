# Scorecard: abandonment and cost-to-find on khipumaq's own history

*Predictions and definitions:
[predictions/2026-10-26-finding-metrics-claude.md](../predictions/2026-10-26-finding-metrics-claude.md)
(`97cbe9f7`, stamped before any chain was built). Numbers: obs-0006 and obs-0007 (M1, M2) and
obs-0008 (M3), in `ledger/observations.jsonl`. Summaries are in
`results/finding-metrics/2026-10-26a/`. Chain text (queries, session paths, judge reasons)
stays local because the repo is public; the ledger pins it by sha256. The metrics are Tony's,
and he made no predictions.*

## The answer

**Searching through the tool beats grepping transcripts, and most "abandoned" searches are
not plain failures. About one search chain in three ends without finding something that
existed. Half of those had the answer in a result the assistant never opened.**

- **240 tool chains, 40% found by the strict signal** (a recall of a returned key). Measured
  that way, abandonment is **0.60** [0.53, 0.68]. Grepping transcripts, the "without the
  tool" arm, abandons **0.93** of 195 chains, with a weaker found signal (see below).
- **M3 splits the abandonments.** In a seeded sample of 60 abandoned chains, judged by Codex
  with searches bounded to before each chain:
  - **28% snippet-found:** the snippet already answered the need.
  - **12% absent:** nothing in the history answered it.
  - **55% existed but not found.**
  - **5% unclear.**

  Scaled to all tool chains, about **0.40 found by recall + 0.17 answered by a snippet +
  0.07 correctly found absent ≈ 0.64 succeeded**, and about **0.33 failed** on something that
  existed.
- **Two failures of equal size.** For 16 of the 33 existed-not-found chains, the episode
  that answered the need was already among the hits the assistant received; it read the
  snippet and stopped. For the other 17, search never surfaced it. *(Exploratory: this split
  was not pre-registered.)*
- **Finding is cheap when it happens.** Median: 1 search, 6.6 s in V3 (9.7 s in V1), about
  5,800 characters of results (12,800 in V1).

## Predictions

| | Prediction | Measured | Verdict |
|---|---|---|---|
| P1 | 250–450 search chains in total; V1 fewest | 435 (240 tool + 195 grep); V1 has 13 | **pass** (tool chains alone, 240, fall below the range) |
| P2 | M1 overall 0.40–0.60 | 0.604 [0.527, 0.684] | **fail** (just above) |
| P3 | M1 in V3 lower than V1 by ≥ 0.10 (interval expected to include 0) | V1 − V3 = −0.15 [−0.48, 0.10] | **fail**: the direction reversed; no claim, because the interval includes 0 |
| P4 | snippet-found + absent ≥ half of abandoned chains | 24 of 60 (40%) | **fail** |
| P5 | median searches to find ≤ 2; median time < 90 s | 1; 6.6–9.7 s | **pass** |
| P6 | grep arm < 40 chains, with higher abandonment than V3 | 195 chains; 0.93 vs 0.62 | **fail** on the count |

2 of 6 pass.

- **P3 is the one that matters.** I expected later versions of the tool to be abandoned
  less. Raw abandonment didn't fall. V1 is 13 chains in 5 sessions. With dev sessions
  excluded, V1 − V3 is −0.27 [−0.57, −0.04]: V3 is abandoned *more*, on 9 V1 chains.
  M3 gives a reading raw abandonment can't (exploratory, small, no interval):
  - In V2, 20 of 26 judged abandonments were existed-not-found and none were absent.
  - In V3, 13 of 33 were existed-not-found, 7 were absent and 10 were snippet-found.

  If that holds up, V3's abandonments are more often the right call, and raw M1 hides the
  improvement. This is exactly the confusion Tony's split was meant to catch.
- **P4.** I overestimated how often abandonment is benign. Raw abandonment overstates failure
  by about 1.8 times (0.60 against about 0.33), not 2.
- **P6.** Instances grep transcripts far more than I thought. Some of it isn't finding at all:
  it's working on transcripts (ingest debugging, format checks). The arm's found signal is a
  read of a matched file. That is weaker than a recall, so its 0.93 is an upper bound on its
  abandonment as a finding failure, not a measure of it.

## What changed after the predictions, and why

1. **The instrument's grep arm was fixed before anything was recorded.** The first run's
   regex counted greps over any `.jsonl`, including `ledger/observations.jsonl` and
   `results/*.jsonl`, and produced 615 grep chains. The registered definition says "a session
   `.jsonl` file". The fix (`29c17635`, test-first in `e499a524`) restricts the arm to
   `.claude/projects`, `.codex/sessions`, or session-named files (UUID, `rollout-`, `agent-`).
   The tool arm was unchanged by the fix: 239 chains, then 240, because this session added one.
2. **M3 judges the tool arm only.** Grep chains have no snippets to judge against.
3. **The audit is stricter than the registration.** It was fixed in the script before the run:
   a label of existed or absent with **no search at all** becomes unclear. That demoted 3 of
   36 existed-not-found verdicts, where the judge recalled the hits it was given instead of
   searching. Before the audit, the split is 36 / 17 / 7 / 0.
4. **The returned-or-never-surfaced split is exploratory**: `evidence_in_results`, added after
   the 2-chain trial and before the full run (`5bc87a2a`).

## Known limits

- The judge is an LLM (Codex, gpt-6-astra). There was no human audit.
- "Absent" means ten bounded searches found nothing.
- Snippet-found is a judgement about what the assistant needed.
- `raw` covers only the session files still on disk at sweeps since 2026-09-30.
- Codex sessions contribute almost nothing: 12 searches.
- Characters stand in for tokens.

## What this says to do

- **Half of the failures are a reading problem, not a retrieval problem.** The answer was in
  a hit the assistant didn't open, because the 200-character snippet stopped before it. The
  cheapest lever is khipumaq's: snippets centred on the matched terms instead of the first
  200 characters, or a longer snippet for the top hit. It is khipumaq's to decide; this
  scorecard goes to it as evidence.
- **The other half is retrieval:** an episode that existed and never surfaced.
- **Re-run this after any change to search.** The instrument, the definitions and this
  baseline are fixed. A change that moves the 0.33 is a change that helped people find
  things, whichever arm it came from.
