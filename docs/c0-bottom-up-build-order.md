# C0 — Bottom-Up Build Order (Tony's path)

*2026-06-16. Tony walked the build as he'd do it from scratch — deliberately, because his path
differs from how Claude would build it and the DIFFERENCE is illuminating. Preserved verbatim in
intent. This is the concrete first form of C0 (dynamic registration,
`docs/common-core-missing-primitive-registration.md`).*

## The illuminating difference (why Tony's order, not Claude's)

Claude's instinct builds the MODEL first (records, edges, schema — what should be TRUE).
Tony's instinct builds the BOUNDARIES first, and makes them PHYSICAL so they can't erode (what
can't become FALSE). This whole session was a catalog of eroded boundaries (drift, shoehorning,
transient-promoted-to-persistent, static lists). Tony's path answers that wound at the root:
**use process/storage separation as the enforcement mechanism, because it doesn't depend on
anyone remembering the rule.**

## The build order (bottom-up, each step tested before the next)

1. **Decide to use ArangoDB and OWN it.** (Not abstract-over; commit.)
2. **Decide DuckDB for the mapping layer.** Physically SEPARATE database from ArangoDB — the
   separation is STRUCTURAL, not disciplinary. ArangoDB indexes opaque UUIDs; the names live in a
   database ArangoDB cannot see. This is why encrypt-kills-index doesn't bite: the obfuscation is
   a separate store, not crypto on the values. (= the SchemaMap / decoder-ring "in another
   building"; the building is DuckDB.)
3. **Build the mapping layer — literally three calls:**
   - `create_mapping(name: str, semantic_description: str) -> UUID`
   - `map_name_to_id(name: str) -> UUID`
   - `lookup_name_description(name: str) -> str`
   Keep these in the SQL DB (DuckDB initially). **Test that it works** before moving on.
4. **Build the singleton database configuration with FAIL-STOP:** if the database doesn't work,
   hard stop. "There is literally no reason to have any of this without the storage behind it."
   (Refuses the LLM graceful-degradation reflex — do NOT simulate a capability you don't have;
   fail-stop is `save-it-all`'s sibling: if you can't save it, STOP, don't pretend.)
5. **The singleton tracks MULTIPLE credential sets — one per `StandardDatabase` in ArangoDB.**
   That per-`StandardDatabase` credential set IS the isolation layer.

## The honestly-OPEN seam (Tony flagged it himself — do NOT collapse)

We agreed (sessions ago) to use multiple `StandardDatabase` instances as the isolation boundary,
**but none of us has specified how routing works in practice** — who decides which
`StandardDatabase` a call goes to, and how. Tony's suspicion (NOT yet decided): introduce
**capabilities (handles)** that Pukara uses to know where to route — structural separation that
nonetheless PERMITS sharing between entities. (This is the cross-tenant seam grounded in a
mechanism — a routable handle — instead of the abstraction "grant.")

**Two axes, kept separate (Claude tried to collapse them; Tony cut it clean):**
- **(1) vs (2) — WHERE the routing design lives: its own brainstorm, or folded into C0?**
  GENUINELY OPEN. Do not pick. Needs its own conversation. (Or a hybrid.)
- **(3) — build the simple bottom-up path now on ONE `StandardDatabase`** — is INDEPENDENT of how
  (1)/(2) resolves. Steps 1–4 above require no routing; a single database is correct under EVERY
  outcome of the routing question. So (3) is UNBLOCKED and proceeds; the routing design happens
  ABOVE a working single-DB substrate, not before it. (Same shape as the cross-tenant-seam
  resolution: simple-first is true regardless of how the open options resolve — don't hold it
  hostage to them.)

## Relation to the rest of the map

This bottom-up path IS C0's first concrete form. The mapping layer + fail-stop singleton are the
substrate that registration (`create_provider_collection`, ported from
`~/projects/indaleko/utils/registration_service.py`) sits ON. Order downstream unchanged:
C0 → A1 (#17 registers itself) → activity converges back → three branches finish → seam last.
