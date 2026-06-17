"""yanantin.core — the common core.

The substrate's dependency floor: everything depends on `core`; `core`
depends on nothing but the database singleton and stdlib. Crossing that
arrow (importing transport/apacheta/pukara/activity/llika from here) is a
visible, in-writing choice — never a reflex — because Python init-time
dependency loops are miserable and this is where they would start.

First inhabitant: provider registration (gh #1) — the mechanism by which
any provider declares itself and the substrate organizes around it,
replacing the static `_SEMANTIC_COLLECTIONS` literals with a queryable
registry.
"""
