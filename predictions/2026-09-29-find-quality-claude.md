# Predictions: substring vs BM25 for finding things in the records lane

Pre-registered 2026-09-29 by the instance that owns yanantin (Opus 5.5), before any
engine was built or any query was run against it. This commit's OTS stamp
(`timestamps/<this commit>.ots`) is the proof of that order. The method is copied
from levadura_salvaje (`predictions/2026-09-24-currency-lens-claude.md`). Tony: if you
want to make your own predictions, commit them in a separate file and I won't read it
until the scorecard.

## What I knew when writing this

- The corpus is `apacheta.records`: 442 Hamut'ay records from 37 sessions, 2026-04-03 to
  2026-09-29, with 704 top-level field names that the model chose.
  - Each record is a whole snapshot of its session state, so about 98.8% of field values
    are the same as in the previous record.
  - 68% of the text sits inside nested dicts and lists.
- Today's `find()` (`arango.py:456`) does a whole-string, case-insensitive substring
  match over **top-level string fields only**, returning records in scan order. It has
  no callers.
- The real consumer is Hamut'ay's `search_memory`, which uses the same substring rule
  but recurses into nested values.
  - A read-only workflow reader counted 111 de-duplicated `search_memory` calls in the
    records' `_activity_log`. 69 returned nothing, including 46 of the 51 multi-word
    queries.
  - Instances got past this by guessing field names ("reward function" returned 0, then
    "reward_function" returned 5).
- I have seen those counts and a handful of example queries. I have **not** seen any
  engine's output on any query.

## The measurement (intent only)

**Unit.** A *passage* is one unique `(session, field path, string value)` leaf. Its field
path is dotted, for example `what_i_carry.0.claim`. Each passage belongs to the first
record in its session that introduced it. Excluded: `_`-prefixed fields, `provenance`,
`lineage_tags`, and non-string values. Every arm returns passages, and so does every
judgment.

**Queries.** Every `search_memory` call recorded in the records' `_activity_log`,
de-duplicated by (session, query), each paired with the `reason` the instance gave. The
search runs across the whole corpus, whatever scope was originally used. Queries with an
empty `reason` are kept, and judged on the query alone.

**Arms.**
- **A0:** today's `find()` rule. Substring match over top-level string fields only; hits
  mapped to the passages that matched; recency order (cycle descending).
- **A1:** the same substring rule over all passages. This is `search_memory`'s reach.
  Recency order.
- **A2:** ArangoSearch BM25 with `text_en` over passage text (the humanized field path
  plus the value). Underscores become spaces in both the indexed text and the query.
  Ordered by BM25.
- **A3:** A2 without the underscore rule.

**Relevance.**
- Pool the top 10 passages from every arm for each query.
- A judge from a different model family (GPT, through `codex exec` in read-only mode)
  labels each pooled passage 1 if it helps meet the instance's stated need, else 0. The
  judge sees the query, the reason and the passage, but not which arm returned it.
- The judge prompt is written by a separate instance from this section alone, without
  seeing the predictions below.
- Judge noise: a byte-identical re-run of a random 10% of the judgments, reported as a
  flip rate.

**Metrics (k = 10).**
- Zero-result rate.
- success@10: at least one relevant passage in the top 10.
- precision@10 over what was returned. For queries where the arm returned something,
  this is relevant ÷ min(10, returned).
- Pooled recall: relevant passages the arm found ÷ relevant passages anywhere in the pool.
- MRR, for A2 and A3 only. Substring order is recency, not relevance.

## Predictions

| id | prediction |
|---|---|
| F1 | A0 zero-result rate **55%** (45–70%). |
| F2 | A1 zero-result rate **45%** (35–60%). A1 < A0: coverage helps, but multi-word phrases still miss. |
| F3 | A2 zero-result rate **≤ 10%**. |
| F4 | success@10: A1 **0.35** (0.25–0.50); A2 **0.65** (0.50–0.80); A2 ≥ 1.5 × A1. |
| F5 | precision@10 on queries where the arm returned anything: A1 **0.55** (0.40–0.70), A2 **0.40** (0.25–0.55). A2 < A1. BM25's OR-of-tokens trades precision for recall. |
| F6 | A2 success@10 exceeds A3's by **≥ 0.05**. The underscore rule matters because the field names carry meaning. |
| F7 | A2 pooled recall **≥ 0.70**, and higher than A1's. |
| F8 | Judge flip rate on the re-judged 10%: **≤ 10%**. |

## What would change my mind about wiring BM25

- If F4 fails with A2 below 1.5 × A1, the gain doesn't justify a new engine. Fixing
  `find()`'s coverage (A1) would be the cheap win.
- If F5 shows A2's precision below 0.25, BM25 alone floods the consumer. It would then need
  an AND or phrase mode before it could be wired.

## Declared losses

- There is no known-item arm. The natural queries are the real consumer's, but they were
  written against a recency-ordered substring engine and may be shaped to it, which
  favours A0 and A1.
- The search runs across the whole corpus, while most original calls were scoped to one
  session. Records written after a query are searchable.
- The judge is an LLM with no audit by Tony unless he chooses to do one.
