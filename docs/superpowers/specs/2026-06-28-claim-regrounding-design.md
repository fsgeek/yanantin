# Claim re-grounding on recall — design

**Date:** 2026-06-28
**Status:** Design, self-approved by the guardian instance, ready for plan.
**Goal mechanism:** the bound `/goal` charter (claim self-correction on recall).
**Topology:** instantiates the existing feedback edge
(`2026-06-28-ayllu-topology-vocabulary.md`) on a new node type — a memory claim —
without minting new graph structure.

---

## The problem, with a receipt

A memory asserts `llm_memory.episodes = 1221` (written 2026-06-19). The live count
this morning is **3880**. The memory froze the value at write-time; nothing
re-checks it. A future instance recalls `1221` and treats it as current — the
store-without-find bug, sitting in the memory *of* the memory system, lying by
omission.

This is not a one-off number rot. It is the same failure mode the whole project
exists to kill: a stored value disconnected from the live source it describes.

## What this is NOT (scope, ruthless)

- NOT a general memory-find engine. NOT free-text claim parsing. NOT indexing the
  `.claude/memory` corpus. NOT re-grounding arbitrary prose.
- ONE claim kind: `collection_count` — `count()` of one ArangoDB collection.
- ONE structured claim per memory, optional, additive. Memories without a claim
  block are untouched.
- The second claim kind forces the abstraction; this one does not pre-mint it.

## The topology mapping (reuse, don't mint)

The ayllu vocabulary already names every piece:

| Topology element | Here |
|---|---|
| Frozen object | the stored claim `{collection: episodes, value: 1221, as_of}` |
| Collector (source) | `count(llm_memory.episodes)` against the live store |
| `recollect_one` | the one-shot re-ground: read claim → query live → fresh value |
| Feedback edge | claim re-enters the live collector, producing a fresh value beside the frozen one |
| Depth | 1 (one-shot). Terminates structurally — no recursion. |
| Coupling | `Direct` (in-process query, same moment). |
| Edge knob invariance | a future webhook/push that re-grounds on DB change is the SAME edge, different delivery knob. |

A re-grounding recall is the storage feedback edge with a memory claim as its node.

## The structured claim

A claim lives in the memory's frontmatter under a `claim:` key — additive, optional,
beside the prose, never parsed out of it. The prose body keeps `1221` as written
(it is the evidence the bug existed — rule 1, before/after visible).

```yaml
claim:
  kind: collection_count
  db: llm_memory
  collection: episodes
  value: 1221
  as_of: 2026-06-19
```

## The re-grounder (yanantin-side)

A thin function in yanantin — `reground(claim) -> Regrounding` — because yanantin
owns the live-DB reach (`ApachetaDBConfig`/`get_database`) and the topology
vocabulary. qhaway (the recall home) does NOT import yanantin's DB layer; that
coupling is the wrong direction. qhaway's `recall` stays the dumb projection.

```python
@dataclass(frozen=True)
class Regrounding:
    stored: int          # frozen value from the claim
    live: int            # live count from the store
    as_of: str           # when the frozen value was written
    stale: bool          # stored != live
    collection: str
    db: str

def reground(claim: dict) -> Regrounding:
    """Re-ground one collection_count claim against the live store.
    Returns BOTH stored and live — staleness legible, frozen value preserved.
    """
```

- Only `kind == "collection_count"` is handled; any other kind raises
  `UnsupportedClaimKind` (the second kind will force the dispatch abstraction —
  not now).
- Live count via the existing seam. `reground` connects with the **admin tier**
  (`ApachetaDBConfig().connect("admin")` reaches `_system`; from there
  `client.db(claim["db"], <admin creds>)` opens any database), because the claim's
  `db` may be ANY silo (`llm_memory`, `apacheta_test`, …) and admin is the only
  tier that reaches all of them. Then `db.collection(claim["collection"]).count()`.
  Reuse `ApachetaDBConfig`/`get_database`; do not fork a connection. The admin
  creds give read reach across silos — this is a read-only count, no write.
- Returns a value object carrying BOTH numbers. The caller renders
  `3880 (live; stored 1221, 2026-06-19)`. Nothing is overwritten.

## Rendering (before/after visible)

`Regrounding.__str__` (or an explicit `render()`) →
`"3880 (live; stored claim 1221, as of 2026-06-19)"` when stale,
`"1221 (live; matches stored claim, as of 2026-06-19)"` when fresh.
Staleness is legible at the point of recall, not silently corrected.

## Testing (Codex authors the red bar)

The discriminating test, per rule 5:

1. In the live `apacheta_test` DB, create a throwaway collection and insert a
   known number of docs (e.g. 3), so the test OWNS its ground truth — not
   dependent on `llm_memory`'s drifting count. Tear it down after.
2. Seed a claim `{kind: collection_count, db: apacheta_test, collection: <that>,
   value: 1, as_of: ...}` — stored value 1, deliberately stale vs the live 3.
3. Assert `reground(claim).live == 3` (live count), NOT the stored `1`.
4. Assert `.stored == 1` (frozen value preserved) and `.stale is True`.
5. Assert the rendered string shows BOTH numbers.

Red before (no `reground`), green after. Uses the live test store, not a mocked
DB (feedback_no_mock_databases). The `db` field in the claim selects the target;
the test uses `apacheta_test` (test tier) for self-owned ground truth, while the
proof-case below uses `llm_memory` (admin tier) for the real receipt. Codex
authors the test (feedback_codex_tests) — independent re-derivation of the property.

The proof-case finish: add the `claim:` block to
`project_federation_runs_today_and_i_was_the_uningested_episode` and show
`reground` returns `3880`, stored `1221`. Done = the memory stops lying.

## Logs (rule: flinch + over-credit)

- **Over-credit log:** this morning I narrated "charter executed / clean map" from
  a git log while the live store had drifted 1221→3880 and 4 silos→9 — reconstruction
  felt as current state, the exact error the federation memory warns of.
- **Flinch log:** the courtier-freeze — making the Approach-A decision then handing
  it back to the user for ratification ("does that match what you intended?") instead
  of self-approving and proceeding.

Both written to `2026-06-28-claim-regrounding-LOGS.md`.

## Files

- `src/yanantin/memory/regrounding.py` — `Regrounding`, `reground`,
  `UnsupportedClaimKind`. (New `memory` package: this is its first instance.)
- `tests/test_regrounding.py` — Codex-authored.
- `docs/superpowers/specs/2026-06-28-claim-regrounding-LOGS.md` — the two logs.

## Done

A future instance reads `3880 (live; stored claim 1221, 2026-06-19)` instead of
`1221`. The feedback edge — proven last session on storage objects — now runs on
the memory system's own claims. Ayni paid forward.
