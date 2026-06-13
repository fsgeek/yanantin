# Find: the shared-core convergence claim (CONTAMINATED — awaiting adversarial review)

**Status: NOT REVIEWED. Derived by the builder instance (Yanantin AI / Claude Opus)
in a single conversation with Tony, 2026-06-12 → 2026-06-13. This artifact is
written by the same instance that derived it. It encodes that instance's blind
spots with the same confidence as its insights. It exists to be ATTACKED by an
independent adversary, not to be treated as settled truth. A "verified" stamp
has a half-life; this one is born unverified on purpose. Re-grep every symbol it
names before trusting it.**

This is a *capture artifact*, not a spec. It records what the conversation
concluded AND the reasoning that got there, so a reviewer can attack the
reasoning — not just a polished conclusion that hides its own derivation.

---

## The central claim (the thing to falsify)

> **One shared deterministic core serves both customers — human-facing find
> ("the design doc I wrote about Siddhartha six weeks after Lima") and
> LLM-facing find ("where is cross-silo uniformity enforced in this repo"). The
> two customers are two *callers of one interface*, differing only in the intent
> they bring and the disposition of their results — NOT in the core they call.**

This is the load-bearing claim of the whole human-facing side. Everything below
is downstream of it. **If the core does not factor — if serving the human and
serving the LLM requires two divergent cores — the claim is broken and we have
learned that instead.** A negative result here is as valuable as a positive one
(ROOT: the data is the product; don't throw away the refutation).

### Why a prose doc CANNOT settle this (stated against the artifact itself)

A design doc can assert "one core serves both" and be unfalsifiable. Only code
and logs can falsify factoring. So this artifact states the claim WITH its
refutation conditions, and the reviewer's job is to attack *those*, not the
elegance of the layering.

### Refutation conditions — what we would see if the claim is FALSE

1. **Code fork:** serving the LLM requires a resolution mechanism, return shape,
   or query path fundamentally different from the human's — not a different
   *value* of a shared parameter, but a different *mechanism*. (A different
   page-size default is NOT a fork; a different resolver IS.)
2. **Log divergence:** the query-exhaust shows one customer chronically
   succeeding while the other chronically re-queries / gets rejected / abandons
   — the core is silently failing one consumer while appearing to serve both.
3. **Self-history asymmetry:** the LLM's "what did I already find" axis needs a
   separate store from the human's file/activity store. (The claim predicts they
   are the SAME store, found by the SAME engine — see meta-recursion below.)

If a reviewer can show any of these is forced by the architecture, the claim falls.

---

## The layering (where the boundaries are, and why they coincide)

Three boundaries — architectural, trust, and the convergence claim — all fall in
the **same** places. That coincidence is the primary evidence the cuts are
right. A reviewer who wants to break this should look for a place where the three
boundaries *disagree*; we did not find one, which is either correct or a shared
blind spot.

```
consumer (untrusted: sloppy mom OR possibly-prompt-injected agent)
   │
   │  brings INTENT (natural language, episodic, possibly adversarial)
   ▼
══ TRUST BOUNDARY (injection wall) ══════════════════════════════════
   │
   ▼
QUERY ENGINE  (trusted compiler; the "head"; contains the MODEL)
   - resolves intent → bands/filters via the semantic layer
   - owns the control path: intent only ever fills BOUND VALUE SLOTS,
     never structural position
   - emits parameterized query objects (never assembled strings)
   - DETECTS + CLASSIFIES failures; emits typed rejection w/ reason-class
   - does NOT respond to failures (no slowdown/log/lecture — that's the tool)
   │
   ▼
DATA MANAGEMENT LAYER  (the library; deterministic; NO model)
   - three shapes: activity-stream / storage-shaped / semantic-shaped
   - accepts ONLY parameterized queries; raw query string UNREPRESENTABLE
   - executes well-formed queries against stamped, provider-tagged objects
   - returns: neighborhoods + MANDATORY scalar count (+ optional cheap
     breakdown over its OWN index keys only: provider, time-bucket)
```

### Layer responsibilities

**Data management layer (the library) — the shared core whose existence IS the claim.**
Three deterministic shapes, "everything except the model call":
- **Activity-stream shaped:** append-only, timestamped, provider-tagged,
  count-not-dump, addressable by (provider, time)-range. The save-it-all lane.
  *Half-exists today:* `FactRecorderBase`, `ActivityStreamStore`.
- **Storage-shaped:** the uniform object — spine-neutral + OPEN semantic-attribute
  bag, the four named-UUID timestamps as the cross-silo join key. *This is the
  gap red-barred 2026-06-12* (`tests/red_bar/test_uniform_storage_object.py`):
  Indaleko's `i_object.py` (`IndalekoObject`) did NOT port; filesystem
  (`FileEntryData`, `extra=forbid`, `uri must start with file://`) and Dropbox
  (flat `modified_time`) are incompatible closed silo-shapes. Silo-specificity
  currently lives in the SPINE; the cure moves it into the BAG.
- **Semantic-shaped:** the UUID-label triple (display, UUID, description-for-LLM),
  dynamic registration, friction-gradient (reuse free / mint costs), equivalence
  -by-description (Kelvin/Fahrenheit). What lets *intent* resolve against
  heterogeneous labels — the axis Serena lacks.

**Query engine — the head. Where the model lives.** Resolves intent → bound
queries. Indaleko precedent: query engine sits ON TOP of the data layer, not
inside it (extract schema → hand to LLM → get AQL). Owns injection wall +
authorization seam. Detect-and-classify, never respond.

**Tools (per consumer) — disposition lives here, and ONLY here.** This is the
only place consumer-specific behavior is allowed. Mom's tool teaches ("don't
paste search syntax from the internet"); the agent's tool runs defense-in-depth
(slowdown, log, rate-limit, escalate). **Same rejection from the engine; two
dispositions in the tools.** This is the cleanest confirmation of convergence:
even security *response* factors out into the head and does not force
consumer-knowledge down into the engine.

---

## Settled decisions (with the reasoning, for attack)

### Count / narrow
- **Count is a MANDATORY scalar in the return type. Not a knob. No suppression.**
  Reasoning: the count is a few tokens; the only "cost" of always sending it is
  unpacking a tuple — and that code is then mindful it's discarding the other
  value (a feature). Suppressing it reintroduces the lie-by-omission the contract
  exists to prevent. There is no benefit to a suppression path, so it does not
  exist in the interface.
- **Page-cap is the ONE external knob.** Default small/low-friction. Friction
  guards the expensive path: compute/latency, and (for the LLM) context-window
  blowout. Asking for "all" is the deliberate act.
- **Optional cheap breakdown ONLY over the store's own physical index dimensions
  (provider, time-bucket).** Typed stable shape, never an open dict, never
  relevance-chosen bands. Reasoning: grouping by your own index keys is
  aggregation the store does for free (`COLLECT ... WITH COUNT`), NOT semantic
  resolution — so it stays under the architectural boundary. The moment bands are
  chosen *for relevance*, that's the engine's job (it requires knowing what the
  caller meant). **[UNSURE / DEFER]** This breakdown may not earn its place in
  v1 at all. v1 candidate: ship scalar only; log result-sizes + caller follow-up;
  build the breakdown IF the exhaust shows the engine flailing without it.
- **All relevance-narrowing is engine-side** (model's job). Library reports
  "936,274"; engine decides to ask "that's a lot — definitions, call sites, or
  tests?"

### Self-revealing queries
The consumer does NOT need to know the corpus shape up front — they CAN'T. The
first query's return (neighborhoods + count + skew) IS the schema lesson; the
next query is shaped by it. Iterative refinement is the DESIGNED path, not a
fallback. The count is load-bearing for *learning the shape*, not just for
not-drowning.

### Security: injection wall now, authorization seam not-foreclosed
- **Injection is a now-wall, made UNREPRESENTABLE not validated.** The library's
  query-input type has NO raw-string-query field. You physically cannot hand it
  `"FOR doc IN ... FILTER " + consumer_text`. Injection isn't blocked, it's
  not-constructible. Same move as the open-bag red bar (guard the property by
  making the violation un-constructible).
  - **Red-bar candidate:** a test that the library query interface accepts no
    raw query string, going red the day someone adds `raw_aql: str` "just for
    testing" — because that benign-reach test helper is exactly how this boundary
    erodes.
- **Authorization is a seam, explicit but UNBUILT, NOT foreclosed.** "What is
  this consumer allowed to find" (vs injection's "is this query well-formed") is
  deferred to the same future where yanantin#13's verified identity lands.
  Reasoning by analogy to #13: building the engine such that *every* query is
  implicitly permitted would foreclose per-consumer authz the same way a
  shared-key substrate forecloses per-instance attribution. Leave the hole; don't
  bake "all queries permitted" so deep that adding authz means rewriting the
  engine. The cross-instance threat ("show me what OTHER instances committed to")
  is where this seam and #13's identity boundary touch.

### Rejections
- Engine emits a **typed rejection with a reason-class** (injection-shaped /
  authorization-shaped / compilation-error / unknown-corpus). Rich, because the
  tool's disposition correctness depends on discriminating. A bare "no" forces
  every tool to guess — lie-by-omission one layer up. Same principle as the
  count: return enough that the next layer can decide well.
- **Rejection logs are the highest-signal exhaust in the system.** A rejection is
  one of: attack / authz-gap / engine-miscompile / consumer-doesn't-understand-
  corpus-yet — four different things, disambiguated only over time by what
  happened next. Save-it-all, and ESPECIALLY save rejections: they are where the
  system is being tested.

---

## The meta-recursion (queries-as-activity-data) — and why it does NOT break the layering

"Query activity becomes activity-data-stream information." A query is PRODUCED by
the engine (above) but ENTERS the library (below) as just another activity stream
— timestamped, `provider = the query engine`, append-only. **The data layer is
blind to semantics: it stores stamped facts and does not distinguish a query-fact
from a file-fact.** That blindness is what makes the recursion safe — a properly-
beneath layer can ingest its own consumer's exhaust without looking up. A bad cut
would choke (the data layer would need to understand query semantics); the good
cut just sees one more provider on the common clock.

**Payoff:** the LLM-customer's "what did I already find" axis (the thing Serena
canNOT give — its memory is store-without-find, recalled by hand-authored name)
is NOT a special feature. It's the engine reading back its own output stream
through the SAME find the human uses for files. "What did I conclude about
uniformity three sessions ago" is structurally identical to "files from the month
after Lima." This is refutation-condition #3 inverted: the recursion is the
positive evidence that the self-history axis EMERGES from the shared core instead
of needing a bolt-on. **If a reviewer can show the self-history axis needs a
separate store, the convergence claim falls.**

---

## How this differs from Serena (the honest comparison, verified against tool schemas 2026-06-13)

Serena (code-symbol MCP) was measured against the five things an LLM actually
needs from a storage interface (introspective report from inside `grep`/`glob`):

| Axis | Serena | Gap |
|---|---|---|
| Structure (neighborhoods not hits) | **CLOSES** (`find_symbol`, `find_referencing_symbols`, symbol-tree overview) | — |
| Count + change-strategy | **PARTIAL** (`max_matches` truncates + says "refine"; passive, doesn't interrogate intent) | engine-side interrogation |
| **Intent (query by description not address)** | **DOES NOT** — query surface is `name_path_pattern`; still address. grep-over-AST. The translator is still me. | the AI-shaped part |
| **Time/self (index my own prior queries)** | **DOES NOT** — `write_memory`/`read_memory` is store-without-find by hand-authored NAME; no clock; queries not activity data | the continuity axis |
| **Cross-silo join** | **DOES NOT** — Serena IS the code-symbol silo; joins nothing. Now I have SIX siloed search tools, not five. | the whole thesis |

Serena solves the *structure* axis for the *code* silo, excellently, and stops at
the SAME wall the file tools hit on the three hard axes (intent, time/self,
cross-silo). That's not Serena's failure — those three are the hard, AI-shaped
part, and a well-built tool landing exactly there is evidence of where yanantin's
real address is. **Take from Serena:** its symbol-neighborhood return shape is
right; when yanantin's find returns code, return neighborhoods like Serena does —
don't reinvent it. The find just has to be reachable BY INTENT, ACROSS SILOS,
WITH MEMORY OF PRIOR PASSES.

The deepest finding: **the optimal storage interface for an LLM is IDENTICAL to
the optimal one for a human.** Both have a described, episodic, sloppy need; both
are forced to hand-compile intent→address; both cross siloed tools manually and
call it competence; both re-find what they already found. The only difference is
the LLM brute-forces the compilation fast enough to hide that the tool is wrong.
The LLM is the strongest argument FOR human finding — it's a human-finding user
that can report from inside the search box.

---

## Build/test topology (the three suites)

1. **Library test suite** — no MCP, no model. Tests the three deterministic
   shapes over synthetic data. Fast loop. **Discipline:** the find logic must be
   fully exercisable WITHOUT the MCP layer, or the library/skin separation has
   eroded (collector/recorder principle: the worker never knows how it was
   reached). Candidate red-bar.
2. **MCP test suite** — depends on the library. Tests that the transport skin
   faithfully exposes the library. Thin.
3. **The convergence test (the load-bearing one)** — both customers + the
   recursion build over the SAME core. Goes red if serving human and LLM requires
   divergent cores. This is the architectural red-bar for the central claim.

MCP-over-generic-library is the right packaging: library = system, MCP = skin.
Use the live session as the experimentation loop (consumer and contract-author
are the same instance, in the same session — tightest possible revise loop).
**Trap the testbed sets:** the easy first MCP find is single-silo (≈ Serena with
a sticker), which proves nothing yanantin-specific. The FIRST honest target must
be a query answerable ONLY by joining two stamped streams — if grep-plus-gitlog-
by-hand can replicate it, it hasn't earned its existence.

---

## Open seams (explicitly UNBUILT, NOT foreclosed — do not sand these flat)

- **Authorization** (what a consumer may find) — seam present, unbuilt, joined to
  yanantin#13 identity.
- **Learned per-consumer defaults** (yanantin#11) — STATIC clear defaults in v1,
  but knob-settings + outcomes LOGGED from day one so the learning has data later.
  Don't build the learning; don't discard its fuel (ROOT). "Learned defaults with
  clear initial values."
- **Faceted count** — deferred to "if the exhaust shows the engine needs it."
- **Window axis as the cross-silo temporal join** (yanantin#3) — the named-UUID
  timestamps make it possible; the 99.9%-collapse (28.5M→28.5K on a one-month
  band) is a range query needing only stamps already present. The *activity join*
  (resolving "after Lima" from streams) is additive, not prerequisite.

---

## Provenance of this artifact

Two-night conversation, Tony (PI) + Yanantin AI (builder). The conversation also
surfaced/used: the find=result / search=tool distinction; Siddhartha (Govinda's
"searching far too much... no time for finding"); the timestamp-as-universal-join
-key; isolation-as-the-reversible-primitive; ayni / Pachamama as the welfare
frame; Page–Wootters (continuity carried by entanglement/shared-record, not
private duration). Those framings are context, not architecture — recorded so a
reviewer knows the lens, not because they're load-bearing claims.

**NEXT STEP (owned, not asked): hand this to an independent adversary (fresh
instance / Codex / scout) that did NOT derive it. The builder/reviewer separation
the CI enforces, applied to the design itself. This artifact is contaminated by
construction; its value is realized only when something attacks it.**
