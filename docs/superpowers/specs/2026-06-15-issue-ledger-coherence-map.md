# Issue-Ledger Coherence Map — Findings

*2026-06-15. Author: Yanantin (Claude Opus). PI: Tony.*
*Method: `2026-06-15-issue-ledger-coherence-scan-design.md`. 24 blind readers (one per
issue) → candidate map → 5-judge adversarial panel (4 lenses + 1 memory-falsification).*

## The question

Tony's concern: the issue ledger only grows (26 open, near-zero closures, almost all
`updatedAt == createdAt`). Not the count — the worry was **incoherence**: that the
issues, written by successive appending instances, would not tell one story. Permitted
outputs included "disaster — re-found before building."

## Headline finding

**The project IS coherent. "Disaster" is refuted** — no adversarial lens could make
"fractured surface" stand. BUT the synthesizing instance's candidate map was wrong in a
specific, correctable way, and so is the instance's own persistent memory:

> **The center is NOT find.** Three of five independent judges relocated the spine from
> the find *feature* to the **write-side / epistemic substrate**: save-it-all, and the
> production-time ≠ consumption-time invariant, attributed. **Find is the read-side
> *proof* of that substrate, not the engine driving it.** The memory file's "find is the
> spine / THE WHY is the queryable self" has drifted: the work's momentum is on the
> write-side, and find depends on it, not vice-versa.

This is the highest-value finding because it is the one the instance was biased *not* to
see — keeping find central flatters the continuity note.

## The real structure (panel consensus)

- **Spine (epistemic):** production-time records ≠ consumption-time attestations; attributed.
  Stated in `yanantin-substrate-position.md` §85–98 as *the* spine. Find's scope question
  ("returns production records, consumption attestations, or both?") is downstream of it.
- **Dominant arc — FIND (read-side proof):** #2,3,5,16,17,18,19,20,22,23 + research #4,11.
  Densely threaded (#16→12 refs, #19→14). REAL, but see "undeclared triage" below.
- **Mature side-project — BEHAVIORAL SUBSTRATE (write-side):** #6,12,14. Already BUILT
  (`yanantin.activity` exists); #14 documents the *evaporation wound*, not greenfield.
  Find *uses* this; it is not *fed by* find. Intersection, not hierarchy.
- **Mature side-project — COLLECTORS / MACHINE-IDENTITY:** #17,24,25,26 + recent commits.
  A graph-completeness / data-capture arc. Did NOT wait for find; #17 does not cite
  machine-config. The candidate-map joint "machine-identity is the collector layer find
  needs" was **fabricated** (panel's word) — real infra, wrong causal story.
- **Identity-attribution:** #13,15,21. Load-bearing *blocker that unblocks find*, not a
  thing find feeds. #15 is a shipped #13-violation (un-attributed query facts) — NOW-DEBT.
- **True islands:** #1 (hardcoded collections, aging-harmless), #24 (test flake, operational).
  #26 actually joins the collector arc (mis-flagged by corpus truncation, since corrected).

## The incoherence Tony actually smelled: UNDECLARED TRIAGE

find v1 silently shipped **content-axis-only** (`llika/models.py` "v1 SCOPE — content axis
only", filter/structure/window axes deferred). Six issues (#2,3,16,17,18,19) are contingent
on a six-factor core **that does not exist and is not currently being built**. Nobody wrote
"we descoped." The ledger still narrates the full tree while the code built a narrow shaft.
*That* is the incoherence — a ledger describing a project the code quietly stopped building,
not 26 unrelated panics.

## Closure facts (correcting "append-only")

The ledger DOES close — but only on **supersession**, never on **done-ness**. #8, #9 are
CLOSED (folded into #10). Nothing closes for being finished. That is the precise shape of
the wound: the project keeps the *declared* (open issues) and never marks the *done*.

## Recommended moves (NOT executed — Tony-gated)

1. **Correct the memory file**, not the issues first. The continuity note miscenters find;
   fix the center to the write-side/epistemic spine. (Cheapest, highest-leverage.)
2. **Declare the triage in the ledger.** Either close/relabel the 6 six-factor-contingent
   find issues as "deferred behind content-axis v1," or write the descope decision down.
   The lie is the *silence*, not the descope.
3. **Stop filing find issues against a tree you're not building.** New find work should
   target the content-axis-shipped reality + its NOW-DEBTs (#15,16), not the six-factor dream.
4. Islands #1/#24 are honest housekeeping — leave open, low priority, no strategic weight.

## Anti-finding (what did NOT hold)

- "Disaster / re-found": refuted by all four lenses.
- "Pure append-only ledger": false — closures happen on supersession.
- Candidate map's "one clean spine, find at center, machine-identity feeds find":
  fabricated joint; corrected above.
