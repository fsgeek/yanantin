# Scorecard: substring vs BM25 for finding things in the records lane

*Predictions: [predictions/2026-09-29-find-quality-claude.md](../predictions/2026-09-29-find-quality-claude.md)
(`43d90127`, stamped before any engine existed). Instrument and judge prompt frozen at `cf0a01b3`,
before any judging. The instrument was built by a separate instance, and the judge prompt was
written blind from the intent section. Neither saw the predictions. Numbers: obs-0001 to
obs-0004 (`ledger/observations.jsonl`). Tony made no predictions.*

**Wire BM25.** Neither result that would have stopped it happened. BM25 over passages (A2)
finds something useful for **76%** of the real queries Hamut'ay instances asked. Today's `find()`
rule manages **37%**, and `search_memory`'s rule **45%**. On multi-word queries the gap is 67%
against 13–15% (obs-0004). On queries where both BM25 and substring return results, BM25 is
**as precise** (0.72 against 0.70, obs-0004). The precision gap I predicted doesn't exist.

| | Prediction | Measured | Verdict |
|---|---|---|---|
| F1 | A0 zero-result rate 55% (45–70%) | 57.4% | **pass** |
| F2 | A1 zero-result 45% (35–60%), A1 < A0 | 47.5% | **pass** |
| F3 | A2 zero-result ≤ 10% | 5.0% | **pass** |
| F4 | success@10: A1 0.35 (0.25–0.50), A2 0.65 (0.50–0.80), A2 ≥ 1.5 × A1 | A1 0.446, A2 0.762 (1.71×) | **pass** |
| F5 | precision@10 on non-empty queries: A1 0.55 (0.40–0.70), A2 0.40 (0.25–0.55), A2 < A1 | A1 0.706, A2 0.549 | **fail** (A1 above its range) |
| F6 | A2 − A3 success@10 ≥ 0.05 | 0.119 | **pass** |
| F7 | A2 pooled recall ≥ 0.70 and above A1's | 0.681 (A1 0.333) | **fail** (below 0.70) |
| F8 | judge flip rate ≤ 10% | 1.7% (3 of 173) | **pass** |

6 of 8 pass (obs-0001, obs-0002, obs-0003).

Both failures are misses against my own numbers, not against the decision:
- **F5.** I underestimated how precise substring is when it returns anything: 0.71. It
  rarely returns anything for a sentence, but what it returns is on target.
- **F7.** BM25 missed its pooled-recall target by two points. It still found twice what
  substring found.

## What the failures and one unplanned check show

**BM25 doesn't trade precision for recall here.** F5's "A2 < A1" held on the pre-registered
metric, but that metric averages each arm over the queries it answered, and those sets differ.
- A1 returned something for 53 queries.
- A2 returned something for 96. That includes 44 where substring returned nothing, and BM25
  was useful on 28 of those.
- On the 52 queries where both returned results, precision is 0.717 for A2 and 0.700 for A1.

So BM25's lower average comes from attempting the hard queries, not from diluting the easy
ones. This check was **exploratory, not pre-registered** (obs-0004). Treat it as a finding to
confirm, not as a scored prediction.

**The underscore rule matters** (F6). Treating `_` as a space adds 12 points of success@10
(0.762 against 0.643) and 13 points of MRR (0.667 against 0.533). Hamut'ay instances name
fields `reward_function` and search for "reward function", and without the rule BM25 inherits
the mismatch that made them guess field names.

**Today's `find()` is the worst arm on every metric.** It doesn't even match the only real
consumer's reach: A1, which looks inside nested values, beats it everywhere. Replacing it removes
nothing that anyone uses. It has no callers.

## What this changes

1. `find()` gets a passage index: one unique `(session, path, value)` per passage, a
   `text_en` BM25 view, and the underscore rule applied at index and query time. It keeps the
   `FindResult` shape. Snippets and `matched_fields` fall out of passages for free.
2. Hamut'ay's `search_memory` is the consumer to move onto it. That's a hamutay change, so it's
   offered, not made.
3. Next measurements: precision on the same queries, pre-registered this time, and a
   known-item arm.

## Limits

- **Queries.** 101 natural queries from 17 sessions. They were written against a
  recency-ordered substring engine, which if anything favours A0 and A1. All ran across the
  whole corpus, though most were scoped to one session.
- **Judging.** One LLM judge (`gpt-6-astra`) with no human audit. The re-run sampled 10% of
  *queries* (173 labels), not 10% of labels as pre-registered, because a byte-identical prompt
  covers a query's whole pool.
- **Pooled recall only counts what reached the pool.** It is only a lower bound on what any arm
  misses.
- **Judge blinding was audited, not enforced.** The judge ran in an empty directory. Its event
  logs show no command execution in any of the 95 cached judgments, only answers. Its
  read-only sandbox would still have permitted reads.
- **Record text is not published.** The repo is public, and the records lane has never been
  published. The manifest pins the withheld passages and queries by sha256. The judgments
  and retrieval published here hold only ids, labels and scores.

## Deployed (2026-09-29)

- **Deployment.** `find()` runs on the passage index as of `38fd3f25`. The production sync
  added 8,567 passages, the same number the instrument derived, and a second sync added 0.
- **Replay** of the 101 frozen queries through production `find()` (obs-0005, a replay, not
  a prediction):
  - 5 queries return nothing, the same as A2.
  - Record-level success@10 is 0.812. It isn't comparable one-to-one with A2's passage-level
    0.762, because one record hit carries all of that record's matched passages.
