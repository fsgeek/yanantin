# Addendum: before/after khipumaq's centred snippets (khipumaq 7d5d900)

Pre-registered 2026-10-26 by yanantin's steward (Opus 5.5), after the baseline scorecard
(`docs/finding-metrics-scorecard.md`) and before any chain with the new snippets was looked at.
The definitions, instrument and adjudication are those of
`predictions/2026-10-26-finding-metrics-claude.md`. This page adds only what's below.

## The change

On 2026-10-26 at 15:29Z, on all three machines, khipumaq's snippet became the 200-character
window that holds the most distinct literal query words. It used to be the first 200 characters
of the matched field. A match that only works through stemming still shows the field's opening.

## Windows

- **V4 (after):** chains in sessions whose first line is at or after 2026-10-26T15:29Z. A
  running session keeps the old server until it restarts. Taking the session's start as the
  cutoff stops a long session from being counted on the wrong side.
- **V3b (before):** chains in sessions that both start and end between 2026-09-29 and
  2026-10-26T15:29Z.
- **Excluded:** sessions that span the cutoff.

**Confound to name:** since 2026-10-24, khipumaq ingests after every turn (Stop hooks), so more
is findable during a session. Both windows are judged with `until` = the chain's first search,
so "existed" means existed when the search ran, whichever window. `evidence_in_results`
separates "it was in a returned hit" from "it existed but never surfaced". This addendum makes
that field pre-registered, no longer exploratory.

**Client split** (khipumaq 58a0dc6, since 2026-10-24): reported where the queries record links
a chain to its client. It is descriptive only, not tested.

## When

The re-run happens when V4 holds at least 100 tool chains, or on 2026-11-23, whichever comes
first. The same seed and the same adjudication sample size (60 of V4's abandoned chains, or
all of them if fewer) apply, plus 60 from V3b. The same judge model is used if it's available;
if not, the new model is named in the result.

## Predictions

1. Of the judged abandoned chains, the share that are existed-not-found **with the answer
   among the returned hits** falls from 27% (16 of 60 at baseline) to **≤ 15%** in V4.
2. The snippet-found share rises from 28% to **≥ 35%**.
3. **M1 (recall-based abandonment) moves by less than 0.10** in either direction, with an
   interval that includes 0. Better snippets turn some recalls into snippet answers, and that
   counts as abandoned under the strict signal. This is why M1 alone can't judge this change.
4. The estimated failure rate (M1 × the existed-not-found share) falls from about 0.33 to
   **≤ 0.25**.
5. The existed-not-found share where the answer **never surfaced** changes by less than 10
   points. Snippets can't fix retrieval.
