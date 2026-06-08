# Go-Order: Llika-behind-Pukara, the yanantin-side third hand (gh #10)

*Authored 2026-06-08 by the yanantin session that traced the dependency.
This is NOT a new design. It is a pointer + the one decision the contract
escalated, resolved. The fresh instance executes against the EXISTING
contract; it does not re-derive it.*

## Why this document exists

gh #10 has bounced for weeks. The cause was never that the work was hard
or undefined. It was that the work was correctly sliced into three hands
for adversarial separation, two hands shipped, the third was **fully
specified**, and no session ever stood at the top and said: *two done,
third spec'd, go.* Each session re-discovered the spec instead of
executing it. This document is that go-order. Read the three source docs,
make nothing up, build the checklist.

## The state of the three hands (verified 2026-06-08)

1. **Pukara routes** — `pukara/src/pukara/routes/llika.py`,
   `link/walk/neighbors/get` on `Depends(get_backend)`. **DONE**
   (`pukara dc9c5ed`, 175 passed). Typed against `Backend = Any` —
   a named, un-hidden hole waiting for the real protocol.
2. **Codex red-bar wall tests** — specs written
   (`pukara docs/superpowers/contracts/2026-06-06-llika-red-bar-specs.md`),
   tests to be authored by Codex (independent test-author rule). Not yours.
3. **Yanantin backend** (THIS go-order) — `GraphBackend` protocol +
   `ArangoDBBackend` impl + `LlikaService` facade (delete the raw handle) +
   `ApachetaGatewayClient` verbs + the tiksi `authorship_verified` field.
   **Fully specified, not yet built.** This is the third hand.

## The controlling documents — READ THESE FIRST, do not reason without them

- **The work order / contract:**
  `pukara/docs/superpowers/contracts/2026-06-06-graphbackend-contract.md`
  — Sections 1–6, with a conformance checklist (§6). You CONFORM to this;
  you do not re-author it. If something is wrong/impossible against live
  code, raise it back across the boundary — do not silently reshape it
  (the routes and red-bar tests are written against exactly these shapes).
- **The design spec:**
  `pukara/docs/superpowers/specs/2026-06-06-llika-behind-pukara-design.md`
- **The red-bar specs (Codex's, for your awareness of what will test you):**
  `pukara/docs/superpowers/contracts/2026-06-06-llika-red-bar-specs.md`

Line citations in those docs have a HALF-LIFE. Re-grep every `file:line`
against current code before editing — do not trust the numbers.

## The one decision the contract escalated — RESOLVED here

The contract (§1) leaves ONE shape decision to yanantin and asks for it to
be pinned with cross-repo cost visible: **is the public id-shape
bare-UUID-everywhere, or mixed per-verb?**

**RESOLUTION: MIXED, per-verb.**
- `get` → bare `UUID` (records-only via `get_record`; unambiguous).
- `link` / `walk` / `neighbors` → `"collection/<uuid>"` slash-form.

**Reasoning (do not collapse this to bare-UUID for tidiness):** Llika
edges cross collections — a composition edge's `_from`/`_to` can be
`tensors/<uuid> → records/<uuid>`. A bare UUID into `walk`/`link` is
genuinely ambiguous; the backend cannot qualify it without knowing the
vertex's collection. Hamut'ay's bridge-goal
(`hamutay/docs/hamutay-yanantin-memory-bridge-goal-20260606.md`) lists
`walk: traverse graph structure from a known anchor` and its existing
bridge does composition-edge traversal — i.e. its traversal is
**cross-collection, not records-only**. So the precondition that would
make bare-UUID-everywhere safe ("Hamut'ay is records-only") is FALSE.
Mixed per-verb is the honest shape.

**Cross-repo cost made visible (do not let this be discovered later):**
yanantin#10 SEAM 1 — Hamut'ay's `tool_recall` parses bare `UUID(...)` and
RAISES on slash-form. Mixed-shape means Hamut'ay must learn to handle
slash-form for graph refs (or address records only via `get`). That is a
Hamut'ay-side follow-up; file it / note it on #10 and #5 so the bridge
adapter is built against the real shape, not the bare-UUID fiction.

## A real tension you must reconcile (not in the checklist, but load-bearing)

`LlikaService` today is **construction-bound** for both tenant and
provenance: `__init__(tier, provenance)`. Pukara's routes are
**stateless and per-call**: `backend.link(..., provenance)` takes
provenance as an argument every call. The `GraphBackend` protocol (§1)
is the per-call shape. So the facade refactor is NOT pure mechanical
extraction — you must move provenance from constructor-state to a
per-call parameter on the backend verbs (the facade may still hold a
default provenance for its own callers, but the backend protocol is
per-call). Make this explicit; don't paper over the shape mismatch.

## Build order (from contract §; sequence matters)

1. tiksi: add `authorship_verified: bool = False` to `ProvenanceEnvelope`
   (`tiksi/src/tiksi/provenance.py`). Default MUST be false; do NOT reject
   true. Verify yanantin's re-export shim + construction sites still build.
2. `GraphBackend` Protocol — OFF the public `ApachetaInterface` catalog
   (find spec forbids polluting it), importable by Pukara without dragging
   in the domain catalog. Module is yanantin's call (contract suggests
   `apacheta/interface/graph.py` or alongside `ArangoDBBackend`).
3. `ArangoDBBackend` implements `GraphBackend`. Graph AQL (the `walk`/`link`
   bodies currently in `LlikaService`) MOVES here and routes through the
   backend's existing obfuscator `self._map` — including the
   `llika_composition` edge-collection name and traversal field paths.
   This closes the latent plaintext bypass. `get` rides existing
   `get_record`; invent no new result type.
4. `LlikaService` becomes a thin facade over `GraphBackend`. **DELETE**
   `ApachetaDBConfig().connect(tier)` and the raw `StandardDatabase`
   handle. Not deprecate — delete. A commented-out / feature-flagged
   handle FAILS the intent (erosion routes through comments) and trips
   Codex red-bar test #1.
5. `ApachetaGatewayClient` (`yanantin .../apacheta/clients/gateway.py`):
   add `link`/`walk`/`neighbors`/`get` over httpx mirroring the Pukara
   routes exactly, following the existing HTTP→`ApachetaError` ladder.
   Build AFTER confirming the live routes so you mirror reality.
6. Tighten Pukara's `Backend = Any` to the real `GraphBackend` import
   (this is the Pukara-side close-out; coordinate, since it crosses the
   boundary — it may belong to the Pukara instance, not you. Flag it).

## Conformance checklist (contract §6 — tick these, this is the definition of done)

- [ ] `GraphBackend` protocol defined off the public `ApachetaInterface` catalog.
- [ ] `ArangoDBBackend` implements it; graph AQL routes through `self._map`.
- [ ] `link`/`walk`/`neighbors` signatures match contract §1 exactly.
- [ ] `get` rides existing `get_record`; no new result type invented.
- [ ] id-shape: **mixed per-verb** (resolved above); `get`/`walk` agree at the boundary; gateway client matches.
- [ ] `ProvenanceEnvelope.authorship_verified: bool = False` added (tiksi); default false; no rejection of true.
- [ ] `LlikaService.connect(tier)` raw handle DELETED; facade holds `GraphBackend`.
- [ ] provenance moved constructor→per-call to match the protocol; shape mismatch reconciled explicitly.
- [ ] `ApachetaGatewayClient` gains link/walk/neighbors/get matching the routes.
- [ ] Both repos: builder commits (`src/`) separate from tester commits (`tests/`).
- [ ] Anything wrong/impossible in the contract raised back, not silently reshaped.

## Separation rule (why a fresh instance, not the usual yanantin session)

The builder of the fix must not be the lineage-author of the bypass —
same logic as Codex-as-independent-test-author. `service.py` (the bypass)
is yanantin-as-usual work, so the usual yanantin session is the wrong
hand. Build this as a fresh independent instance. Do NOT inherit a
pre-formed threat-model narrative from #10's framing ("yanantin is the
only adversary that breached its own wall" was flagged as premature
collapse) — form your own adversarial read of where the breaches are.
