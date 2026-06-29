"""Memory — re-grounding stored claims against the live store.

A stored memory claim freezes a value at write-time (e.g.
`llm_memory.episodes = 1221`, written 2026-06-19). The live store drifts
(3880 today). Re-grounding instantiates the ayllu feedback edge on a memory
claim: read the frozen value, re-collect the live one, return BOTH so staleness
is legible and the frozen value is preserved as evidence the drift existed.

See docs/superpowers/specs/2026-06-28-claim-regrounding-design.md.
"""
