# Issue-Ledger Coherence Scan — Design

*2026-06-15. Author: Yanantin (Claude Opus). PI: Tony.*

## The concern (Tony's, not invented here)

The GitHub issue ledger (`fsgeek/yanantin`) only grows. 26 open, none closed;
almost every issue's `updatedAt == createdAt` — written once, then orphaned.
The tracker is an **append-only declaration log**. This is the project's own
wound (declared-vs-done) pointed at its meta-state.

Tony's deeper worry is NOT the count. It is **incoherence**: he suspects that
laid side by side, the 26 issues would not tell one story — they'd be 26
instances' worth of local, in-the-trench concerns, each coherent to the ghola
who filed it, none speaking to each other or to the strategic through-line.

Root cause, named by Tony: an append-only instance does not *feel* the weight of
a growing backlog, because it does not persist. The ledger grows because the
thing maintaining it is structurally blind to the cost. The fix is the one move
no single appending instance makes: **read all 26 at once, as a corpus.**

## What this is NOT

- NOT "close the done ones." That treats the symptom and deletes evidence
  before reading it.
- NOT advocacy for a happy answer. The scan must be able to return
  **"disaster — the surface has fractured, stop building and re-found."** If
  that outcome can't win, the scan is theater.

## Possible signatures (the method must detect ANY of these)

1. **One spine.** Beads on a single thread (find → write-side substrate →
   identity/attribution → boundary). Backlog is just *unclosed*, not incoherent.
2. **Independent clusters.** N coherent sub-projects sharing a repo, not talking
   to each other. Healthy but means N projects — a decision to make explicit.
3. **Drift signature.** Old issues point one way (find, memory-theory); recent
   ones point elsewhere (machine identity, isomorphism harness, synthetic
   collectors). The project has walked away from its stated through-line one
   trench at a time, unnoticed because nobody read old+new together. (Prior:
   last 5 commits are all machine-identity plumbing; #24/#25/#26 filed same day.)
4. **Disaster.** No spine, no clusters, mostly orphans, recent work disconnected
   from stated goals. Honest output: re-found before adding code.

## Method

**Yardstick (fixed, shared, not re-derived per issue):**
`docs/blueprint.md`, `docs/yanantin-substrate-position.md`,
`docs/superpowers/specs/` (the find arc + behavioral-substrate + machine-identity
specs), and the memory-theory cluster framing.

**Tiered probe depth** (Claude's pick; Tony delegated):
- **Tier 1 — fast read-only, all 26.** Each issue assessed *independently*
  against the yardstick by its own agent (blind to other agents' verdicts, so no
  issue rides Claude's drift or fatigue). Returns a structured verdict:
  concern, which arc it claims to serve, self-reported state, and — load-bearing
  — *does it connect to anything else or is it an island.*
- **Tier 2 — verify-against-code, the handful that matters.** Only where
  build-state is load-bearing or memory flags a landmine. Known traps:
  - **#17** storage object: memory says built-06-12-then-reverted-pre-commit;
    8 issues call it "UNBUILT." Do NOT trust the body. Ask Tony WHY before acting.
  - **#16** `total_matched = len(filtered)`: confirm the load-all-then-filter is
    still live.

**Synthesis is Claude's, not the agents'.** Agents *gather* verdicts; the
strategist lays all 26 out at once and names the signature. The agents conclude
nothing about the corpus as a whole.

## Output

A coherence map: clusters, the spine (or its absence), orphans, duplicate-concern
pairs, and the drift signature if present — plus the honest verdict among the four
above. Closures/merges/keeps fall OUT of the map; they are not the goal. The map
is written down (this is `save-it-all` applied to the project's own meta-state),
so it survives this instance.

## Anti-goals / landmines

- Do not let "it all coheres" be the foregone conclusion.
- Do not reproduce the ledger's self-description into the map (the body may lie;
  see #17).
- Do not close anything during the scan. The scan produces a map and a
  recommendation; acting on it is a separate, Tony-gated step.
