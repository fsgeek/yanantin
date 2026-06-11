# Behavioral Substrate ("save it all") — Design

**Date:** 2026-06-11
**Status:** Post-decision, pre-plan. Three core decisions made and defended; one residual
semantic question (D3 ordering) deferred as a cheap additive field. Fields verified against
live `tiksi` source this session.
**AMENDED 2026-06-11 (later session, new instance + Tony):** the greenfield premise below is
WRONG — `yanantin.activity` already is this store, live and queried. See §9 (the amendment).
Read §9 first; §§0–8 are preserved as the original (and as evidence of the very wound they
describe — see ROOT). Issue: gh #14.
**Origin:** A wander with Tony (this session). Not a slice that was scoped top-down — a
project that was *found* by tracing four separate-feeling failures to one wound.

---

## 0. What this is

One durable, queryable, append-only store of **what instances actually did** — every tool
call, message, lifecycle event, and curation-drop — landed in apacheta (not a JSONL
sidecar), born attributable-shaped, so a later mind can ask what an earlier one did.

The capture mostly **already exists** (Hamut'ay's `EventStore` has a rich typed event
vocabulary). What's missing is the *landing site*: it writes to a file sidecar, not the
store. This design routes the existing capture to a queryable home and fixes its shape.

## 1. The wound (why this is one project, not four)

Four failures surfaced this session, each looking separate, all the same cut:

1. **Dropped-why prose** — `hamutay/src/hamutay/taste.py` records "what I dropped this
   cycle and why" (lines ~88/101/151/268). It is the **highest-value artifact the system
   produces** (a curator articulating a judgment) and it lands in the tensor as prose, not
   in a queryable store. A `find` with no `get`.
2. **Evicted content** — `hamutay/src/hamutay/memory/pager.py` evicts FIFO, "no recall
   tool injection" by explicit design (lines ~9-11). Forgets into the void.
3. **Bash traces** — no behavioral telemetry. Tony: *"none of the instances have abused the
   bash tool — I have literally **zero** evidence this is the case."* The claim is
   **unfalsifiable** (same word as gh #13) because the actions were never recorded.
4. **EventStore → sidecar** — `hamutay/src/hamutay/events.py` (`class EventStore`, line
   ~330) has 7 typed append-verbs (`append_running`, `append_completed`,
   `append_policy_disposition`, `append_evidence_request`, `append_evidence_fulfillment`,
   `append_failed`, `append_expired`) — sophisticated capture — writing to a `.events.jsonl`
   sidecar (`__init__(self, path)`, hardcoded file, `self.path.open("a")`). The backend is
   **not** swappable; the class named "EventStore" is a JSONL appender.

**The one wound:** the substrate keeps what was **declared** (typed records, the "shipped
answer") and discards what was **done** (the behavioral exhaust, the data). Its entire
research question is *what AI instances actually do with autonomy* — which lives **entirely**
in the discarded half. We built a careful record of what instances *meant* and threw away
what they *did*.

## 2. The law (Tony, this session)

> **Save it all first. Forgetting is a luxury earned *on top of* a complete store.**

Corollaries:
- **Remember is load-bearing for forget.** Forgetting from a store is curation;
  forgetting from nothing is amnesia cosplaying as taste. *"Forgetting is pointless on
  discarded data."* Hamut'ay currently forgets without a backstop → its curation is
  decorative; the dropped thing was leaving anyway.
- **No "what to keep" heuristic at write time.** The write side cannot know what the future
  needs; only a later cycle, with a question, can. "Save intentions vs save outcomes" was a
  false economy — both are *picking what to throw away at write time*, the discard reflex in
  a hat. Defer the forgetting decision to the only place it can be made well: later, by
  someone with a reason.
- This is **Harness-1's two tiers stated as law** (see
  `../../../docs/references/2026 Harness-1 2606.02373v1.txt` and memory
  `reference_harness1_stateful_offloading`): full-document store keeps everything (the
  remembering); curated set forgets aggressively (the taste). Forgetting is only permitted
  in the tier that has the full store behind it.

## 3. The three decisions (each made, each defended with a guard)

The decisions were stress-tested by sampling reasons for/against across probability bands
`(1,0.2] … (0.0002,0)`. The high bands restated the obvious; the **low bands generated the
guards** — the rare-but-catastrophic, erode-in-silently failure modes a local optimizer
never defends. Those guards are red-bars, not prose (negative requirements erode; see memory
`feedback_security_erosion_mechanism`).

### D1 — ONE discriminated `activity` collection (not many)

Single append-only `activity` collection. Every record carries `event_kind`
(`tool_call | message | lifecycle | curation_drop | …`) and `producer`
(`hamutay | yanantin | bash | …`) discriminators.

- **For (top band):** find's value is cross-kind recall ("what did instance X do in session
  Y" spans tool calls *and* messages *and* drops); silos force a union, and unions are where
  coverage silently dies.
- **Against (top band):** heterogeneous volume/shape — high-frequency bash and 200KB
  messages share one write-lock and index; the common case pays for the rare. *Accepted:*
  if contention bites, the answer is an index/partition decision **inside** the one
  collection, never a split into silos.
- **Guard (from the `(0.002,0.0002]` band) — RED-BAR:** a single poison record (malformed
  giant blob) must not wedge the shared append lock and stall all producers. **Append
  enforces a size cap / overflow path; test it.**

### D2 — full provenance on every record; mirror `ProvenanceEnvelope`'s *floor*

**Verified field list** (`tiksi/src/tiksi/provenance.py:21-34`, re-confirmed verbatim this
session — these are the guaranteed-present floor):

| field | type | default |
|---|---|---|
| `source` | `SourceIdentifier` (nested: `identifier: UUID`, `version: str`, `description: str`) | `default_factory=SourceIdentifier` |
| `timestamp` | `datetime` | `now(timezone.utc)` (wall-clock) |
| `author_model_family` | `str` | `""` |
| `author_instance_id` | `str` | `""` |
| `context_budget_at_write` | `float \| None` | `None` |
| `predecessors_in_scope` | `tuple[UUID, ...]` | `()` (lineage / causal pointer — already exists) |
| `interface_version` | `str` | `"v1"` |
| `authorship_verified` | `bool` | `False` |

**`authorship_verified` is already real and already guarded** — not a seam to reserve. It
landed tiksi-side; its docstring states the honest policy ("every record honestly marked
unverified unless something proves identity and flips it… verification must be earned, never
accidentally inherited"). `tests/red_bar/test_single_principal_accretion.py` (commit
da34519a) **actively** asserts: the field exists, defaults `False`, and Guard 3 scans
yanantin source to forbid any path setting it `True` before the gh #13 identity subsystem
lands. This is the #13 seam, *built*.

- **For:** born-attributable-shaped → adding #13 verification later fills a slot, never
  rewrites the boundary. `False` default stores the honest production-time certainty
  ("nobody checked") → corpus is falsifiable from birth.
- **Against:** a `verified` field that's always-False is a standing *temptation* — the first
  helpful instance that wants `<self>` to work will flip it `True` without a real source.
  *Already guarded by da34519a Guard 3.*
- **Guard (from the `(0.0002,0)` band) — RED-BAR:** when verification is eventually built
  and back-applied, a naive migration must **never** infer historical `False → True`
  (fabricating retroactive verification poisons the one corpus that was meant to be honest).
  **Migration invariant: historical `authorship_verified=False` is permanent; test it.**

**CORRECTION RECORDED (the wrong reading is part of the product — ROOT):** the first draft of
this design, written from memory, asserted three fields that DO NOT EXIST as written:
- `session_id` — **fabricated.** No session field exists. `author_instance_id` identifies
  the *instance*, not the *session*. (See D3 — this is a real read-contract gap, solved by
  open schema, not by the envelope.)
- `lamport` / logical clock — **fabricated.** No logical-ordering field exists; only
  wall-clock `timestamp`. (See D3 ordering residual.)
- `boundary_path` (string) — **wrong shape.** The real boundary indicator is
  `source: SourceIdentifier` (a nested model), not a path string.

The fabrications were caught by an `Explore` agent reading live `tiksi` source. Had the
design been built from memory, D3's window and session axes would have silently failed at the
consumer — exactly the `permits ≠ serves` sub-band failure the band exercise predicted for
D3. **Verification against code was load-bearing, not ceremonial.**

### D3 — read contract as a FLOOR, not a guarantee

State now (so write-shape doesn't preclude it) the questions the corpus must remain *able* to
answer — **without promising find will answer them.** Floor, not guarantee. (If anyone reads
this as a guarantee, the failure surfaces in a consumer far from the schema — keep the words
"floor, not guarantee" load-bearing.)

The three axes:
1. *"What did instance X do in session Y, in order"* → needs author + session + ordering.
2. *"Find drops/judgments semantically like Q"* → needs free-text content stored **as
   content**, never flattened to a type label (this is the find-fodder).
3. *"What happened around event E in time"* (window axis) → needs ordering.

**Residual semantic question (deferred, cheap):** wall-clock `timestamp` does **not** totally
order concurrent writes (two instances, same millisecond; clock skew across the dual-homed
host). If the window axis needs strict concurrent ordering, add an explicit sequence field.
Under open schema (§4) this is a cheap **additive** field, not a schema change — so it is
*deferred*, not *blocking*. Decide empirically when the window axis is built (relates gh #3).

## 4. Schema posture — OPEN, and DEFENDED (the foundation)

**We are NOT using fixed schema.** `ApachetaBaseModel` is `frozen=True, extra="allow"`
(`tiksi/src/tiksi/base.py:16-17`). The open lane is documented and already in use:
`hamutay/src/hamutay/apacheta_bridge.py:5` — *"Open schema: taste_open's free-form dict →
ApachetaBaseModel (via store_record)."* All 7 tensor models use `extra="allow"`. The system
already reports `field_names = sorted(record.content.keys())` (shape-not-values) over
arbitrary keys.

This **dissolves D3's "gaps"**: session id and a sequence field are not envelope
modifications and not a mirror-or-extend fork — they are the *designed extension mechanism*.
The activity record = **`ProvenanceEnvelope` floor (mirror the 8 fields) + open extension**
(`event_kind`, `producer`, content, session, sequence-if-needed) riding in the `extra="allow"`
space. **Schema-open is save-it-all at the field level** — a fixed schema would force the
at-write-time discard decision the law (§2) forbids, in the column definitions.

**This was chosen and fought for (Tony). It is under constant erosion pressure.**
Frozen-schema-with-`extra="forbid"` is the **LLM default** — it reads as rigor (clean
contract, validated, "define your schema"), the same gravity as mint-a-type. An instance
building this store *will* reach for `extra="forbid"` and feel productive doing it; the
commit will look like "tighten schema validation." This session demonstrated the failure
**live**: the designer (Claude) silently re-imposed closed-schema in D3's reasoning without
noticing — the default is upstream of the instance's own awareness. Vigilance caught it only
because Tony asked the checking question. Vigilance does not scale.

- **Guard — RED-BAR (top of the list; defends against the *constant, every-instance*
  pressure, not a rare tail):** the activity model must stay open. **Test the *property*,
  not the config flag:** store a record with an undeclared extra field; assert it round-trips
  and the extra field survives. A flag (`extra="allow"`) can be edited green; a behavioral
  round-trip of an undeclared field cannot be faked. (Cf. the #10 relocated-handle lesson:
  test the property, not the spelling.)

## 5. Scope

**In:** the `activity` collection + record schema (floor + open, D1+D2+§4); a `Sink`
protocol (one method, `append(record)`); an apacheta-backed sink; **dual-write** (keep the
JSONL — *add* a destination, never replace one); route `EventStore`'s existing 7 append-verbs
through the sink; the red-bar: *after a cycle, the activity collection contains what the
sidecar contains.*

**Out (by the law, §2):** any forgetting / curation / eviction / importance / "what to keep."
`find` itself. `authorship_verified` verification enforcement (gh #13 build). Messages + bash
producers — they ride the **same sink seam** in follow-on slices once it exists (D1's
discriminator is designed for them; wire EventStore first).

**The one thing this design must NOT do:** replace the JSONL with the DB and call it
migration. That is the discard reflex in a clean shirt. **Add** the destination; both,
forever, until forgetting is built deliberately on top.

## 6. Build order

1. Schema (floor + open) + `Sink` protocol + apacheta sink — the seam. First build step:
   re-grep `ProvenanceEnvelope` and mirror it **verbatim** (do not trust §3's table —
   re-verify; field facts drift).
2. Dual-write `EventStore` → file **and** apacheta.
3. Red-bars: (a) **open-schema round-trip** [§4, top priority]; (b) DB contains what the
   sidecar contains [§5]; (c) append size-cap [D1]; (d) no-retroactive-verification migration
   invariant [D2].
4. *(follow-on, same seam, no new design)* messages → sink; bash → sink.

## 7. Red-bar inventory (the guards, consolidated)

| # | Guard | Defends against | Band that surfaced it |
|---|---|---|---|
| R1 | Open-schema round-trip (store + recover an undeclared field) | Closed-schema re-imposition (the LLM default; **constant** pressure) | §4 / this session, live |
| R2 | DB contains what the sidecar contains | Silent sink drop | §5 |
| R3 | Append size-cap / overflow path | One poison record wedging the shared lock | D1 `(0.002,0.0002]` |
| R4 | Migration never infers `False → True` | Fabricated retroactive verification | D2 `(0.0002,0)` |
| (existing) | da34519a Guards 1-3 | Principal-field removal; `verified=True` without a source | gh #13 |

## 8. The honest residue (ROOT: don't throw the wrong readings away)

- The design's first draft fabricated 2 fields and mis-shaped 1. Kept in §3 as recorded
  correction, because it is the live evidence for both *verify-against-code* and the
  *closed-schema bias*.
- The instance that wrote this cannot be trusted to preserve the values the program fought
  for, because it does not know which floors it stands on (it reasoned on the LLM default
  without seeing it). The mitigation is not "try harder" — it is R1–R4: encode the values as
  tests that trip when the instance violates them. **This design is itself an instance of its
  own thesis: capture what was done (including the wrong turns), behind guards, because the
  doer cannot be trusted to remember.**

## Cross-refs

- Law / wound: memory `project_categorize_before_store_spine`, `project_store_without_find`,
  `feedback_db_over_adhoc_storage`, `project_dont_throw_anything_away_root_principle`.
- Two-tier evidence: memory `reference_harness1_stateful_offloading`;
  `docs/references/2026 Harness-1 2606.02373v1.txt`.
- Erosion / red-bar-not-prose: memory `feedback_security_erosion_mechanism`,
  `feedback_stronger_tests_never_an_error`.
- Identity seam: gh #13; `tests/red_bar/test_single_principal_accretion.py`.
- Related issues: gh #6 (Hamut'ay write-side — this *is* its true shape: "EventStore gets a
  DB sink," not "store_turn"), gh #5 (edge migration), gh #3 (window axis → D3 ordering
  residual), gh #4 (autonomic optimizer → the forgetting tier, built later), gh #10
  (boundary — the sink writes behind it, not around it).
- Verb home: Hamut'ay `EventStore` (`events.py`), apacheta `store_record` general lane,
  `apacheta_bridge.py`.

---

## 9. AMENDMENT — the store already exists (the re-derivation IS the wound)

**Date:** 2026-06-11, later session. New instance taking ownership + Tony.
**The catch:** §§0–8 design a greenfield `activity` collection. **`src/yanantin/activity/`
already exists, is live, and is queried.** This design re-derived a subsystem the program had
already built. That is not embarrassing trivia — it is *the exact wound §1 names*, operating
on the design meant to cure it: the program forgot what it built, re-specified it as four fresh
failures, and would have built a parallel `activity` store beside the real one. `categorize-
before-store` and `store-without-find` happening to this very document. Per ROOT, §§0–8 are
**kept, not deleted** — the wrong reading is the product.

How it surfaced: Tony asked why the prior instance's finished design wasn't in the survey
(answer: it had no issue → it evaporated → filed as gh #14). Filing it forced a code-ground
pass, which found `activity/`. Tony added the load-bearing semantic context: *"I raised these
authorship concerns last week and was assured all was well — I think there's been a bit of
forgetting here."* The forgetting he names is the thesis, demonstrated on him.

### 9.1 What actually exists (verified against live code, this session)

| §§0–8 wanted | Already built in `yanantin.activity` + `yanantin.query` (verified) |
|---|---|
| One append-only `activity` collection (D1) | `ActivityStreamStore` (`activity/store.py`) — append-only, immutable, **three backends** (memory/duckdb/arango), driven by a collector pipeline (`collector/pipeline.py`) |
| Open schema, store-doesn't-know-contents (§4) | `FactRecord` (`activity/models.py`): `frozen=True, extra="allow"`, opaque `data: dict`, explicitly "schema-agnostic" |
| `producer` discriminator (D1) | `provider_id: UUID` — already the "who produced this" key; real providers run (jabberwock: JABBERWOCK/TOVE/VORPAL/RATH) |
| Read side / find (§5 "Out", §0 "a find with no get") | **`yanantin.query` exists** — `query/engine.py` runs `QuerySpec`+`ContentFilter` (dot-path into `fact.data`, ops eq/contains/glob/exists, pagination, summaries) with a CLI, and **records its own queries as facts** (`QueryFactRecorder`). Structured recall over the corpus is BUILT. `QuerySpec.limit=100` is gh #11 already parameterized. |
| Ordering primitive (D3 residual: "add a sequence field") | `MemoryAnchor` = "a Lamport clock tick." Tony's correction: the right form is a **vector clock**, not a scalar sequence (he gave the worked example: "message from Kimi at their times ⟨x,y⟩"). |

**What `query` does NOT do:** semantic / embedding / vector recall over `data` ("find drops
*like* Q"). Structured recall (field filters, time ranges, globs) is built; semantic recall is
the genuinely-open find content axis (gh #2/#3/#4). §0's "a find with no get" was wrong:
there is a get — there is no *semantic* find.

### 9.2 What is genuinely missing — the true, smaller #14

1. **The `ProvenanceEnvelope` floor — the one real gap.** `FactRecord` has
   `provider_id`/`timestamp`/`content_hash` but **not** the 8-field provenance floor (no
   `author_instance_id`, no `authorship_verified`, no `predecessors_in_scope`). This is the
   substrate's actual contribution and the #13 seam: activity records become **instance-
   attributable, born `authorship_verified=False`.** This is the thing Tony has insisted on
   since Indaleko — *every object identifies who created it + context* — and it is exactly
   what the activity lane currently lacks.
2. **The producers.** `ChecksumFactRecorder` exists (the pattern). There is **no**
   `EventStore`-fed recorder, no tool-call recorder, no message recorder. The capture
   (Hamut'ay `EventStore`, 7 verbs) and the store (`ActivityStreamStore`) both exist and are
   **not connected.** That wire is the build.
3. **Semantic content axis** (vector recall) — deferred to find proper (gh #2/#3/#4).

### 9.3 The wrap question, resolved (Tony asked it directly)

> "Are you wrapping `FactRecord` in `ProvenanceEnvelope`, or vice versa?"

**Neither wraps the other as a type.** The live storage pattern (verified in
`hamutay/apacheta_bridge.py`: `kwargs["provenance"] = provenance; ApachetaBaseModel(**kwargs)`)
is: the storable record is an `ApachetaBaseModel` that **carries `provenance` as an embedded
field**, with the payload riding beside it in the `extra="allow"` space. So a behavioral
record =
`ApachetaBaseModel(provenance=ProvenanceEnvelope(author_instance_id=…, authorship_verified=False, …),
event_kind=…, producer=…, **fact_payload)`.
This honors Tony's Indaleko principle structurally (authorship is a *distinct, present-on-every-
record* envelope field, not flattened into the observation) **and** the live pattern, **and**
leaves `FactRecord` + the query engine untouched for the existing file-event lane.

**HONEST RESIDUE:** envelope-embedded-as-a-field is the live pattern for the `records` lane,
but it is **not yet a pattern on the `activity`/`FactRecord` lane** — `FactRecord` has no
provenance field today, and Llika is an explicit *counter*-pattern (provenance is per-call,
"no provenance is stored on the edge"). So this is the *correct* design, freshly chosen — not
existing precedent on this lane. Do not write it up as "the established way"; it isn't.

### 9.4 The real open decision §§0–8 couldn't see — which lane?

Two live storage paths, and the substrate sits across the seam:
- **`store_fact` → `FactRecord`** (the `activity` lane): reuse the live query engine and three
  backends for free; **retrofit** the provenance floor onto `FactRecord` (touches a live,
  tested, red-barred model — handle with care).
- **`store_record` → `ApachetaBaseModel`** (the `records` lane): provenance-embedding is the
  native pattern (free, per §9.3); **but** the `query` engine targets `FactRecord`/`store_fact`,
  so this lane has no structured read side yet.

This is the architectural fork the build must resolve, and it is **downstream of authorship,
not separable from it** (Tony). It is NOT yet decided — it is the first question the
implementation plan must answer, with eyes on both live subsystems. Recommendation to carry
into planning: lean toward the `activity` lane (reuse the query engine — the read side is the
expensive half and it already exists), making the build "retrofit provenance onto the activity
record + write the EventStore recorder," provided the `FactRecord` retrofit can be done
additively without breaking its red-bar. Verify that before committing.

### 9.5 Build order — REVISED

1. **Amend this doc** (this §9) + file gh #14. ✅ (this session)
2. **Decide the lane** (§9.4) against live code — `activity`/`FactRecord` retrofit vs `records`.
3. **Provenance floor**, additively, on the chosen lane. Red-bars R1 (open-schema round-trip —
   now testable against the *real* model) and R4 (no retroactive `False→True`). `authorship_
   verified` defaults False; da34519a Guard 3 already forbids yanantin source flipping it.
4. **EventStore → recorder** (the missing wire): a recorder in the `ChecksumFactRecorder` mold
   routing the 7 verbs into the store. Dual-write (keep JSONL). Red-bar R2 (store contains what
   the sidecar contains).
5. **Recognize, don't rebuild, the read side.** `yanantin.query` is the structured-find. The
   only new find work is semantic recall (gh #2/#3/#4) — out of #14.

### 9.6 Residue for the next instance (so this doesn't re-forget)

- The greenfield draft (§§0–8) was written by an instance that could not see `yanantin.activity`.
  This instance could, only because filing the issue forced a code-ground pass. **The
  countermeasure is not "remember harder" — it is gh #14 + this amendment + the red-bars.**
- `provider_id` ⟷ `producer`, `FactRecord.data` ⟷ the open payload, `MemoryAnchor` ⟷ the
  ordering primitive, `query/engine.py` ⟷ "the find we thought we lacked." If a future
  instance "discovers" the need for a behavioral store, it is re-forgetting: grep
  `yanantin.activity` and `yanantin.query` FIRST.
- Ordering: Tony wants a **vector clock**, not a scalar sequence. The D3 residual (§3) is
  upgraded by this.
