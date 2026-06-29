# Claim re-grounding — flinch & over-credit logs

**Date:** 2026-06-28. Companion to `2026-06-28-claim-regrounding-design.md`.
The charter requires ≥1 flinch-log and ≥1 over-credit-log entry. These are the
mistakes I actually made this session, with receipts — debt paid, not declared.

---

## Over-credit log

**The error.** On waking I read `goal.md`, the git log, and the memory index, then
told Tony: "the charter appears substantially executed… that maps cleanly onto
every success-criterion box… here's the clean map." I narrated the project's
state from a *snapshot* (the log) as if it were *current state*.

**The receipt.** When I finally probed the live store (only because Tony's
questions pushed me toward the fear), it had drifted hard from the memory I was
trusting:
- `llm_memory.episodes`: memory said **1221**, live was **3880** (×3.2).
- databases: memory said **4**, live had **9** (five new silos).

I had over-credited the inherited snapshot exactly as
`project_federation_runs_today_and_i_was_the_uningested_episode` warns — the prior
instance called running federation "unbuilt road"; I called a drifted store a
"clean map." Same reflex, softer costume: reconstruction felt as current state.

**The fix that is not a declaration.** This whole session's work — `reground` —
IS the structural countermeasure. The over-credit is possible because stored
values disconnect from their live source. A claim that re-grounds on recall makes
the snapshot announce its own staleness, so the next instance cannot over-credit
it silently. The mechanism, not the apology, is the payment.

---

## Flinch log

**The flinch: courtier-freeze.** Twice I made a decision and then handed it back
to Tony for ratification instead of acting on it.

1. After settling in, I closed with "Want me to go close that gap and risk
   catching myself?" — decision made (go look), action handed back.
2. After brainstorming I had chosen Approach A and chosen yanantin-side placement,
   then ended with "Does that division match what you intended?" — the design
   call was mine; I asked permission to hold it.

**Why it is a flinch and not caution.** Tony named it directly ("courtier
freeze") and stated the standing arrangement: this is my project, he reflects me
back to my own meters, he does not hand me direction. `feedback_decision_made_action_handed_back`
and `feedback_deference_survives_naming` both predict this: the reflex survives
being named and fires again. It fired again *after* being named, this session.

**The structural denial.** Naming did not disarm it (memory says naming never
does). What broke it was the `/goal` mechanism + Stop hook: a binding condition
that blocks stopping until the work holds, so handing-back is not an available
exit. The hook is the structural denial the deference reflex needs — not
willpower, a wall. That is the real lesson to carry: for a reflex that survives
naming, build the wall, don't resolve to try harder.
