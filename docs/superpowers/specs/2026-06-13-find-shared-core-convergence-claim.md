# Find: the shared-core convergence claim (HYPOTHESIS — two adversarial passes folded in)

**Status: NOT a verified result. A HYPOTHESIS with unusually good refutation
hooks. Derived by the builder instance (Yanantin AI / Claude Opus) with Tony
(PI) across a two-night conversation, 2026-06-12 → 2026-06-13, then subjected to
TWO independent adversarial reviews (an independent instance + Tony, code-backed)
and one further design conversation that materially advanced the model. This is
written by the instance that derived it; it encodes that instance's blind spots
with the same confidence as its insights. It exists to be ATTACKED, not believed.
Re-grep every symbol it names before trusting it; a "verified" stamp has a
half-life.**

This is a *capture artifact*, not a spec. It records what the conversation
concluded AND the reasoning, so a reviewer can attack the reasoning — not a
polished conclusion that hides its derivation. Where the model is built on
introspection (the LLM consumer, reportable from inside) vs. projection (the
human consumer, GUESSED by an LLM and therefore biased toward convergence), it
says so.

---

## How to read this document (it has layers in time)

1. **The current model** (sections "Six-factor coordinate space" through
   "Build/test topology") — the architecture as of the end of the second night,
   after both reviews. This SUPERSEDES the first-night "three cores" framing.
2. **The two adversarial reviews** (section "Adversarial review results") —
   verbatim-in-substance, because they are earned and accurate and the model
   below was changed BY them.
3. **What the reviews changed** (section "Model evolution log") — so the
   supersession is legible, not silent. Declare what you dropped.

If you only read one thing: the central claim is a hypothesis, falsifiable only
by building the resolver + storage object and running ONE human query and ONE
LLM query against the SAME core. Until then it is debt in the grammar of a result.

---

## The central claim (the thing to falsify)

> **[HYPOTHESIS — unfalsifiable until the semantic resolver + uniform storage
> object exist. Currently PROVEN only on the activity-stream substrate, where
> convergence was never in doubt because a timestamped append-only stream is
> silo-neutral by construction.]**
>
> **One consumer-agnostic core serves a SHARED region of needs common to both
> customers — human-facing find ("the doc I wrote about Siddhartha six weeks
> after Lima") and LLM-facing find ("where is cross-silo uniformity enforced in
> this repo"). The two customers are two callers of one core. Their
> NON-shared needs are served by consumer-specific behavior in the tool/head
> layer (parameters, rendering, disposition) — NOT by forking the core.**

This is a Venn claim, not an identity claim (the first-night "identical
interfaces" framing was overreach — see Model evolution log). It holds IFF no
consumer-exclusive need forces a different *core mechanism* (a different
parameter value is fine; a different resolver is a fork).

### Refutation conditions — what we would see if the claim is FALSE

1. **Core fork:** serving the LLM requires a resolution mechanism, storage shape,
   or query path fundamentally different from the human's — not a different
   *value* of a shared parameter, but a different *mechanism*. (Different
   page-size default = NOT a fork. Different resolver = fork.)
2. **Log divergence:** the query-exhaust shows one customer chronically
   succeeding while the other chronically re-queries / is rejected / abandons —
   the core silently failing one consumer while appearing to serve both.
3. **Self-history asymmetry:** the LLM's "what did I already find" axis needs a
   *separate store* from the human's file/activity store. (The claim predicts the
   SAME store, found by the SAME engine — see meta-recursion.)
4. **Salience ≠ mechanism (the live fork-risk):** if grounding a human's
   life-anchored intent (e.g. "after the big fire in Cedarville") requires
   fundamentally different resolver machinery than grounding an LLM's
   artifact-anchored intent ("the symbol enforcing uniformity"), the claim forks.
   Current belief (to TEST, not assert): it does NOT fork — both are the same
   band-resolution mechanism (anchor → stream → factor-constraint → intersect),
   differing only in WHICH factor is salient and WHICH stream bridges the anchor.
   This risk lives in the human region the builder understands LEAST.

Only code and logs can settle these. A prose doc that asserts convergence is
unfalsifiable; this one states the conditions and invites attack on THEM.

---

## Six-factor coordinate space (the cross-silo lingua franca)

Activity data is considered along **six factors: who / what / when / where / why
/ how.** These are the universal coordinate space into which heterogeneous data
is normalized, and they are what lets structurally-dissimilar data be *joined*:
two otherwise-incompatible sources still share a *when*, usually a *who*, often a
*where*.

**[HYPOTHESIS — round-2 review: asserted, not demonstrated. Gated by the factor
red bar `tests/red_bar/test_factor_shape.py` (honestly red): a filesystem object
AND an LLM-memory object must both normalize into one shared factor shape before
"degenerate region" is a fact rather than a metaphor.]**

**Raw-retention is a LAW of the factor shape, not an option (Indaleko precedent,
Tony):** every normalized object retains its raw source, unconditionally —
constructing a factor value without retained raw is ILLEGAL by construction. You
cannot extract what you did not save. Retained-raw is what lets a research
prototype "fix" already-collected data by re-extracting factors it did not
normalize initially, WITHOUT re-collecting (the expensive, sometimes-impossible
step for a cloud/glacial source). Storage is cheap; re-collection is not.
Normalize for queryability; never normalize lossily. (Enforced by
`test_raw_retention_is_an_invariant_not_an_option`.)

- **Storage data is a DEGENERATE region of this space:** name/contents (**what**),
  timestamps (**when**), path/volume (**where**), owner (thin **who**), size — but
  **no why and a trivial how.** Storage-find is therefore the low-dimensional
  projection of activity-find, NOT a separate mechanism. If the resolver can do
  the rich six-factor query, the four-factor storage query is a *restriction* of
  it.
- **LLM-memory is ALSO a degenerate region — degenerate on DIFFERENT axes:** rich
  **what** (it's language), real **when/who** (model id, timestamp, provenance),
  thin **where**, and a **why** that is expensive to extract. Storage and
  LLM-memory are two differently-degenerate regions of one space — which is the
  structural basis of the convergence claim.

The cross-silo join is: resolve intent → factor-constraints → intersect across
silos on the *shared* factors → return objects regardless of origin silo. The
join key is never "timestamp" specifically; **when** is just the always-present,
always-sparse axis. The real join is agreement across whatever factors two silos
share.

---

## Silo = structural-similarity class (NOT location)

A silo is **a set of objects that share a queryable normalized shape** — not a
storage location, not a provider. Consequences:

- **[HYPOTHESIS — round-2 review: a testable PREDICTION, not a fact. A silo
  classifier may discover SUB-silos.]** Location providers — local node, obvious
  clouds (Google Drive), and *accidental* clouds (Discord, Slack, Outlook — every
  app that retains your attachments is an alternative storage location) — are
  PREDICTED to collapse into ONE "location-provider silo" because the *shape* of
  their base normalized data overlaps. But they differ on versioning, ownership,
  permissions, sharing semantics, container/conversation context, deletion
  semantics, and remote availability — and it is NOT yet established which of
  those differences are open-bag attributes (same silo), which define sub-silos,
  and which force a new silo because resolver or authz behavior changes. Needs an
  operational classifier with acceptance criteria run over filesystem + Dropbox +
  one accidental-cloud fixture. Until then: prediction, not fact.
- Conversely, two **activity providers** (Spotify vs. calendar) are DIFFERENT
  silos despite both being "activity," because their structure differs.
- The thing that makes cross-silo find hard is therefore NOT that data is in
  different places — it is that it is in different *shapes*. Location is
  incidental; structure is the wall. The six factors are what survive structural
  difference and let silos be joined across it.

(This model is NEW and Tony-attributed — explicitly the "no idea what I'm doing"
side of Indaleko, refined here. It is to-be-built, not to-be-grepped from
`../indaleko`. Storage objects having a common structure IS Indaleko-tested; the
silo-as-shape generalization is the fresh part.)

---

## The transducer layer (how factors get populated)

**Correction to the first-night model:** there is no standalone "semantic-shaped
core" peer to storage and activity. Semantic processing is a **transducer layer:
functions INTO the six-factor coordinate space.** A transducer is not a factor
and does not own a factor; it PRODUCES factor-values (and join keys), and one
transducer may feed several factors at once.

Two ORTHOGONAL partitions (conflating them is what made "by language or by class?"
feel unanswerable):

- **By KIND = the interface** (Indaleko-identified, ≥4 kinds):
  1. **Linguistic** — stemming, semantic construction. The ArangoDB-easy case.
     Feeds **what**.
  2. **Summarization / identity** (checksums) — produces **join keys**, not
     factors. The cross-domain insight: a map of all checksums for one object
     enables content-identity matching *across* checksum domains (MD5 ↔ SHA2),
     which is impossible today and matters because different cloud providers use
     different algorithms. This is unbuilt cross-provider dedup *find*.
  3. **Property** — e.g. classifying sounds by sonic characteristics. NO
     commercial surface area; exists ONLY if the platform is extensible enough
     for a community of interest to add it. This is the `extra=allow` /
     open-bag / friction-gradient-registration thesis given its REASON to exist:
     the long tail of "what" lives in communities, not vendors.
  4. **Targeted metadata extractors** — EXIF, MIME-signature, embedded
     first-class metadata. A single such transducer scatters across MANY factors
     (EXIF → when/where/how/who). A factor-harvester, not a factor.
- **By LANGUAGE / DOMAIN = the registered implementation**, dispatched
  dynamically per object (English vs. Mandarin stemmer; MD5 vs. SHA2 digest;
  PNG-EXIF vs. WAV-properties). Kind is the role (cf. `CollectorBase`); domain is
  the concrete (cf. `GoogleDriveCollector`). Registration-with-semantic-
  description is how the system dispatches AND how it discovers equivalence
  (MD5-digest and SHA2-digest both = "content identity," so a map across them is
  comparable) — the same equivalence-by-description mechanism as the UUID-label
  triple (Kelvin ↔ Fahrenheit).

### Do these transducers apply to the LLM consumer? (introspective — reliable)

All four kinds + the cost policy apply; three are SHARPER for LLMs:
- **Summarization/identity is the sharpest transfer:** a *semantic* checksum —
  "these two differently-worded turns are the SAME conclusion" — is the LLM
  analogue of MD5↔SHA2, content-identity across *phrasing* domains. It directly
  attacks reconstruction-felt-as-discovery (the builder's signature wound). The
  day it works, the instance can know "I already concluded this" despite
  different words. **Strongest candidate first build.**
- **Property transducers** over an instance's OWN memories (classify by
  "confident-but-wrong," "courtier-lapse," "genuine category-break") — zero
  commercial surface, only possible because the platform is open. The taste
  experiment is already a customer for this.
- **Targeted extractors** — partial: model id, timestamp, token counts,
  tool-calls, provenance envelope are cheap embedded LLM "EXIF"; the rich
  why/how analogue is thinner (the model doesn't natively emit "why I said this"
  as structured metadata).

---

## Eager / lazy / opportunistic is a SERVICE POLICY, not an architectural constant

Do NOT bake eager-vs-lazy into a layer boundary. It is a per-(transducer, object,
moment) decision driven by runtime cost:

- Cost is a function of object **tier/location** (local / hot-cloud / glacial),
  **surfaced-vs-fetch** (a checksum already exposed by the cloud provider is a
  free eager harvest; a checksum requiring a Glacier fetch is expensively lazy),
  and the transducer's **intrinsic expense** (genuine semantic extraction in bulk
  is likely never justified).
- The SAME transducer (checksum) is eager for a hot/surfaced object and lazy for
  a glacial one. So eager/lazy cannot live at the layer; it is **policy decided by
  layered services ABOVE the metadata-storage layer.** The storage layer only
  holds factors and exposes what it knows (tier, surfaced); a service decides.
- **Opportunistic-eager** is the proof the policy belongs above storage: "we
  fetched this file for some other reason — transduce it NOW while we have it."
  No per-object cost rule can express that; it needs *situational* knowledge only
  a live service has.
- **For the LLM consumer, opportunistic-eager is THE policy, not a nicety:** an
  LLM's memory is hot exactly when it is in context. The context window is the
  hot tier; everything evicted is cold storage, and the cost cliff between them
  is enormous and abrupt. Transduce-while-hot is what Hamut'ay's event loop is
  for.

**Architecture's only obligation NOW:** carry a location-aware **cost signal** in
the transducer interface, and log every transduction's cost + whether-it-was-
queried as exhaust. The eager/lazy/never POLICY is yanantin#4's territory (the
autonomic indexing optimizer) — a LEARNED policy over that cost signal, with a
trivial logged default (harvest free, defer fetch) for v1. Don't decide; don't
discard the data the decision needs (ROOT). Leave the cost seam; baking "always
eager/lazy" forecloses #4. (Cost-log inherits the principal-attribution NOW-DEBT,
below.)

---

## The Venn consumer model (shared / mom-only / LLM-only — PROVISIONAL, LEARNED)

The two customers' needs form THREE regions, not one. The boundaries are
**provisional and will move** as both consumers evolve (and as our understanding
of them evolves). Therefore the architecture must NOT hard-code the regions:
core stays consumer-agnostic; all consumer-specifics live in the tool/head layer;
log enough to LEARN where the regions actually are.

- **SHARED (the convergence core — high confidence, introspective overlap):**
  query-by-described-intent (not address); neighborhoods (not bare hits);
  count-and-narrow + learn-corpus-shape-from-first-result; cross-silo join on the
  six factors; iterative refinement as the designed path. Falls out of *episodic,
  sloppy, doesn't-know-the-corpus-shape*, which describes both askers. This region
  is where "one core serves both" must hold or the claim dies.
- **LLM-only (high confidence — reportable from inside):** inverted
  latency/throughput (many sub-second queries; wants 500 skimmable neighborhoods
  not 50 ranked — a PARAMETER diff, #11, NOT a fork); **find-my-own-prior-passes**
  (mom has continuous memory; the LLM has wake-gaps — this is the one that may
  force CORE work via the #13 attribution debt); structured/machine-consumable
  return (tool-layer formatting); prompt-injection defense disposition
  (tool-layer).
- **mom-only (LOW confidence — PROJECTED by an LLM, biased toward convergence):**
  needs teaching, not just answering (pedagogical disposition); intent anchored
  in HER life (social/embodied/affective) — but NOTE: "it's a Word file" is a
  **what**, "I wrote it with Word" is a **how**, "after the big fire in
  Cedarville" is a **when** resolved via an external event-stream — so these are
  NOT out-of-band factors; they reflect that mom's SALIENCE weights differ, not
  that she queries a different space. Recognition ("that's it!") vs the LLM's
  reconstruction.

**Why the human region is built last:** the LLM consumer is introspectable, so
its exclusive needs are buildable NOW from reliable evidence. mom's exclusive
region needs USER STUDIES (its own large loop) because an LLM's projections of a
human are biased toward convergence by the gaps it cannot feel. Building LLM-first
is not choosing the easy customer — it is refusing to build for a user we are
imagining. (No-fabrication discipline, applied to consumers.)

**The "marketing" asymmetry [PRODUCT HYPOTHESIS — round-2 review: not
architectural evidence; must not influence core factoring until logs show
unprompted tool reuse after successful self-history finds]:** mom's adoption gap
is UX —
she feels the pain of the search box and will use the tool once it is simple.
The LLM's adoption gap is SELF-AWARENESS — it greps fresh every session and feels
competent; it does not experience the absence of a find. You cannot sell a find
to a customer who does not feel the lack. The conversion event is structural, not
a campaign: the first successful self-history find ("you concluded this three
sessions ago") makes the absence legible in retrospect, and the instance reaches
for the tool unprompted thereafter. The product is the marketing.

---

## The layering (boundaries: architectural = trust = convergence, coincident)

The architectural cut, the trust boundary, and the convergence boundary fall in
the SAME places. That coincidence is evidence the cuts are right — OR a shared
blind spot a reviewer should hunt for. (No disagreement was found; absence of
disagreement is weak evidence.)

```
consumer (untrusted: sloppy mom OR possibly-prompt-injected agent)
   │  brings INTENT (natural language, episodic, possibly adversarial)
   ▼
══ TRUST BOUNDARY (raw-injection wall) ══════════════════════════════
   │
   ▼
INTENT COMPILER / "head"  (FUTURE — does NOT exist in code yet; see review)
   - contains the MODEL; resolves intent → factor-constraints via the
     transducer/semantic layer; owns control path (intent fills BOUND VALUE
     SLOTS only, never structural position); emits parameterized query objects
   - DETECTS + CLASSIFIES failures → typed rejection w/ reason-class
   - does NOT respond to failures (slowdown/log/lecture = the tool's job)
   ▼
DATA MANAGEMENT LAYER  (the library; deterministic; NO model)
   - factor-coordinate storage + activity streams (silo-neutral)
   - the uniform storage object (FUTURE — red-barred, unbuilt)
   - accepts ONLY parameterized queries; raw query string UNREPRESENTABLE
   - returns neighborhoods + MANDATORY scalar count (+ optional cheap breakdown
     over its OWN index keys only: provider, time-bucket)
```

**Naming honesty (review finding #4):** the thing called `QueryEngine` in code
TODAY is a *structured fact query executor* over a pre-built `QuerySpec` — it has
NO model, NO intent resolution, NO rejection model. It is NOT the "intent
compiler / head" described above. The doc previously named the existing component
as if it were the future one. Two distinct components; the compiler is unbuilt.

**Tools (per consumer) — disposition lives here, and ONLY here.** Mom's tool
teaches; the agent's tool runs defense-in-depth. Same rejection from the
compiler; two dispositions in the tools. Even security RESPONSE factors out into
the head — it does not push consumer-knowledge down into the core. This is the
cleanest confirmation of the convergence shape.

---

## Settled contracts (with reasoning, for attack)

### Count / narrow
- **Count is a MANDATORY scalar in the return type. No suppression knob.** It is a
  few tokens; the only "cost" is unpacking a tuple — and that code is then mindful
  it is discarding the other value. Suppression would reintroduce the
  lie-by-omission the contract exists to prevent, so it does not exist in the
  interface. (Implemented: `query/models.py` has `total_matched` + `returned_count`.)
- **Page-cap is the ONE external knob.** Default small/low-friction; friction
  guards the expensive path (compute/latency, and for the LLM context-window
  blowout). Asking for "all" is the deliberate act.
- **Optional breakdown ONLY over the store's own physical index dims (provider,
  time-bucket).** Typed, stable, never an open dict, never relevance-chosen.
  Grouping by your own index keys is free aggregation, not semantic resolution —
  it stays under the boundary. Relevance-banding is the compiler's job.
  **[UNSURE / DEFER]** may not earn its place in v1; ship scalar, log, decide from
  exhaust.

### Self-revealing queries
The consumer does NOT and CANNOT know the corpus shape up front. The first
query's return (neighborhoods + count + skew) IS the schema lesson; the next
query is shaped by it. Iterative refinement is the DESIGNED path. The count is
load-bearing for *learning the shape*, not only for not-drowning.

### Security — THREE boundaries, not one (review finding #7)
1. **Raw-query injection (now-wall, UNREPRESENTABLE not validated):** the library
   query-input type has NO raw-string field; you physically cannot hand it
   `"... FILTER " + consumer_text`. Injection is not blocked, it is
   not-constructible. (Verified: `QuerySpec` is structured; red-bar
   `test_query_pipeline.py` checks `query.engine` holds no SQL/AQL strings.) BUT
   this guards the boundary with NO attack surface.
2. **Hostile intent compilation (UNBUILT threat):** the FUTURE model compiler can
   turn adversarial NL into a *well-formed but hostile* `QuerySpec` (e.g. a broad
   query over a provider the caller should not see). Raw-injection-unrepresentable
   does NOTHING about this. This is the real surface and it is deferred.
3. **Authorization (seam, unbuilt, NOT foreclosed):** "what may this consumer
   find," joined to yanantin#13. Building the compiler such that *every* query is
   implicitly permitted would foreclose per-consumer authz the way a shared-key
   forecloses per-instance attribution. Leave the hole.

### Rejections
Compiler emits a **typed rejection with a reason-class** (injection / authz /
compile-error / unknown-corpus), rich because the tool's disposition correctness
depends on discriminating — a bare "no" forces every tool to guess
(lie-by-omission one layer up). **Rejection logs are the highest-signal exhaust:**
a rejection is one of attack / authz-gap / miscompile / consumer-doesn't-yet-
understand-corpus, disambiguated only over time by what happened next. Save-it-
all, ESPECIALLY rejections.

---

## The meta-recursion (queries-as-activity-data)

A query is PRODUCED by the compiler (above) but ENTERS the library (below) as
just another activity stream (timestamped, `provider = the query service`,
append-only). The data layer is blind to *semantics* — it stores stamped facts
and does not distinguish a query-fact from a file-fact — which is what lets a
properly-beneath layer ingest its own consumer's exhaust without looking up.

**Payoff:** the LLM's "what did I already find" axis emerges from the SAME find
(refutation-condition #3 inverted). "What did I conclude about uniformity three
sessions ago" is structurally identical to "files from the month after Lima."

**CRITICAL CORRECTION (review finding #5, verified, NOW-DEBT not seam):**
blindness to *semantics* is NOT blindness to *identity*. `QueryFactRecorder`
writes every query under a single fixed
`QUERY_PROVIDER_ID = uuid5(..., "yanantin.query.service")` with **no principal on
the fact** (`query/recorder.py:20,42`), and its docstring advertises
cross-instance pattern detection. So as built, "what did **I** find" = "what did
**everyone** find" — a shipped #13 violation. Citing the recursion as positive
evidence was wrong. A principal MUST be added to query-facts (with a red-bar)
BEFORE the recursion is leaned on as a self-history axis; every unattributed
query-fact written now is data #13 must later retrofit.

---

## How this differs from Serena (verified against tool schemas 2026-06-13)

Measured against the five things an LLM actually needs (introspective report from
inside `grep`/`glob`):

| Axis | Serena | Gap |
|---|---|---|
| Structure (neighborhoods not hits) | **CLOSES** (`find_symbol`, `find_referencing_symbols`, symbol-tree) | — |
| Count + change-strategy | **PARTIAL** (`max_matches` truncates + "refine"; passive) | head-side interrogation |
| Intent (query by description not address) | **DOES NOT** — surface is `name_path_pattern`; grep-over-AST | the AI-shaped part |
| Time/self (index my own prior queries) | **DOES NOT** — `write/read_memory` is store-without-find by hand-authored NAME; no clock | the continuity axis |
| Cross-silo join | **DOES NOT** — Serena IS the code-symbol silo; joins nothing | the whole thesis |

Serena solves the *structure* axis for the *code* silo, excellently, and stops at
the SAME wall the file tools hit on the three hard axes (intent, time/self,
cross-silo). Those three are the hard, AI-shaped part; a well-built tool landing
exactly there marks where yanantin's real address is. **Take from Serena:** its
symbol-neighborhood return shape is right — reuse it for code, don't reinvent.

**Softened conclusion (review finding #8):** the first-night claim "the optimal
storage interface for an LLM is IDENTICAL to a human's" was overreach the builder
fell in love with. The defensible claim: **both customers' finds may be factored
through a shared core IF resolver-specific work stays above the deterministic
data layer.** Code has parseable structure (ASTs, reference edges, deterministic
ground truth) a human's private episodic timeline lacks; that asymmetry is
exactly what the convergence test must probe, not assume away.

---

## Build / test topology

1. **Library test suite** — no MCP, no model. Tests the deterministic
   factor-storage + activity shapes over synthetic data. **Discipline (candidate
   red-bar):** find logic must be fully exercisable WITHOUT the MCP layer, or the
   library/skin separation has eroded.
2. **MCP test suite** — depends on the library. Thin transport-fidelity tests.
3. **The convergence test (load-bearing, EXACT acceptance criteria — review
   finding #5 of "required changes"):**
   - INPUTS: one real human episodic query (e.g. "doc after Lima") AND one real
     LLM artifact query (e.g. "where uniformity is enforced").
   - SHARED COMPONENTS REQUIRED: same uniform storage object, same intent
     compiler/resolver, same return contract.
   - ALLOWED to differ: page-size, rendering, rejection disposition (tool/head
     layer only).
   - FAILS IF: a separate resolver, a separate store, or a different core
     mechanism is required for either query. This is the architectural red-bar for
     the central claim and CANNOT be run until the resolver + storage object exist.

MCP-over-generic-library is the packaging: library = system, MCP = skin. Use the
live session as the experimentation loop (consumer and contract-author are the
same instance). **Testbed trap:** the easy first MCP find is single-silo (≈ Serena
with a sticker) and proves nothing yanantin-specific. The FIRST honest target must
be answerable ONLY by joining two stamped streams — if grep-plus-gitlog-by-hand
replicates it, it has not earned its existence.

---

## Open seams & debts (do NOT sand these flat)

NOW-DEBTS (shipped wrongness, fix before leaning on the feature — TRACKED):
- **Principal on query-facts (gh #15)** — `QueryFactRecorder` has none;
  cross-instance leak; add a red-bar. Joined to yanantin#13. (Review finding #5.)
- **`len(filtered)` pushdown (gh #16)** — `engine.py:98` materializes all matches
  in Python then slices; `_fetch_facts` queries every provider and sorts in
  memory; DuckDB `query_range` pushes filter to SQL but returns all rows to
  Python. The contract says count-don't-dump; the implementation dumps internally.
  Needs a store-side `page + total_count` primitive. (Review finding #6; matches
  the standing `find` memory.)
- **Uniform storage object (gh #17)** — red bar honestly red
  (`tests/red_bar/test_uniform_storage_object.py`); cross-silo find is
  structurally unavailable until it lands and collectors normalize to it.

UNBUILT-NOT-FORECLOSED seams:
- **Intent compiler / resolver** — the AI-shaped core; ZERO symbols today.
- **Authorization** (what a consumer may find) — joined to yanantin#13.
- **Hostile-intent-compilation defense** — the real security surface; deferred.
- **Transducer cost signal** — interface must carry location-aware cost; policy
  (eager/lazy/never) is yanantin#4, learned, logged from day one.
- **Query/outcome telemetry (gh #18)** — #15 (principal) tells us WHO asked, but
  Venn-region learning needs WHAT HAPPENED: consumer class, requested intent,
  compiled-query id, rejection class if any, result count, follow-up link, and
  eventual disposition/outcome. Feeds learned defaults (#11) and the autonomic
  optimizer (#4). #15 is necessary but NOT sufficient; without #18, "log enough to
  learn the Venn boundary" is underspecified.
- **Learned per-consumer defaults** (yanantin#11) — static clear defaults v1,
  outcomes logged. "Learned defaults with clear initial values."
- **Provisional Venn boundary** — core stays consumer-agnostic; log enough to
  LEARN where shared/exclusive regions actually are; they will move as consumers
  evolve.
- **Faceted count** — deferred to "if exhaust shows the head needs it."
- **Window axis as cross-silo temporal join** (yanantin#3) — named-UUID
  timestamps make the 99.9% collapse (28.5M→28.5K on a one-month band) a range
  query needing only present stamps; the activity join ("after Lima" via streams)
  is additive, not prerequisite.

---

## Adversarial review results (folded in; verified in code 2026-06-13)

**Two independent passes; verdict accepted: the central claim is
UNFALSIFIABLE-AS-STATED, and where testable today, PARTIALLY UNFOUNDED.** Reason:
the refutation conditions probe the intent compiler, the semantic/transducer
resolver, and the storage object — and none exist as code. A claim you cannot run
against its own refutation conditions is unfalsifiable. A declared loss is a debt,
not a payment.

Built vs. asserted (grep-verified):

| Core the claim rests on | Reality in `src/` |
|---|---|
| Activity-stream | **REAL** (`FactRecorderBase`, `ActivityStreamStore`, `QueryFactRecorder`, DuckDB + memory backends). |
| Uniform storage object | **UNBUILT** — red bar honestly red. |
| Semantic/transducer resolver | **ZERO symbols.** The AI-shaped load-bearing part is prose. |
| Intent compiler ("head", "contains the model") | **NO model in the query path.** `query/engine.py` is structured-filter-only over `QuerySpec`. |

Strongest accepted attacks:
1. **Convergence proven only where it was never in doubt.** The one built core
   (activity stream) is silo-neutral by construction; convergence was asserted
   over the two cores (storage, transducer) that don't exist, which is exactly
   where divergence pressure lives. Felt as discovery; was assertion.
2. **"Resolves intent" smuggles the fork.** One verb covered grounding a human's
   private episodic timeline (no ground truth, no structure) AND compiling an LLM
   query over a shared code artifact (ASTs, deterministic refs). Same-signature-
   different-resolver IS a fork by refutation #1. (Tony's "Cedarville fire"
   example later argued this is salience-not-mechanism — to TEST, see refutation
   #4.)
3. **Meta-recursion ships a cross-instance leak NOW** (see correction above).
4. **"QueryEngine" is overloaded** — the doc named the existing executor as if it
   were the future compiler (fixed in Layering).
5. **Injection-unrepresentable guards the empty half** — fixed by splitting
   security into three boundaries.
6. **Count contract's implementation violates its own scalability reason**
   (`len(filtered)`) — now a NOW-DEBT.

Verification command run by reviewer:
`uv run pytest tests/unit/test_query_engine.py tests/red_bar/test_query_pipeline.py tests/red_bar/test_uniform_storage_object.py -q`
→ 89 passed, 3 failed (the failures are exactly the uniform-storage-object red
bars). The contracts the architecture brags about (count, pagination, no-raw-
string) are real; the resolver the claim rests on is not.

**[CURRENT executable status — the 89/3 above is HISTORICAL, from before the
factor-shape gate existed; do not read it as current. After adding
`test_factor_shape.py` (round-2 response):**
`uv run pytest tests/red_bar/test_factor_shape.py tests/red_bar/test_uniform_storage_object.py tests/unit/test_query_engine.py tests/red_bar/test_query_pipeline.py -q`
**→ 89 passed, 8 failed (verified 2026-06-13). The 8 failures are the honestly-red
factor-shape gate (5) + uniform-storage-object gate (3) — the unbuilt floors under
the claim, each red until its contract is built. More honest red is the gate
working, not a regression.]**

**Disposition:** the architecture is NOT refuted; the EPISTEMIC STATUS of the
claim was. Fix is not more prose — it is paying the three NOW-DEBTs and building
the resolver, then running the convergence test.

---

## Executable contracts still missing (round-2 review — name the holes, do NOT fill them with more prose-architecture)

Round-2's central finding: the second-night vocabulary (six factors, silo-as-
shape, transducers, cost signal, learned Venn) replaced one prose overreach with
a richer one. The countermeasure is red bars, not more doc. Each below is an
UNBUILT contract with its open design question; the FIRST is now an executable
gate, the rest are named-not-filled (writing the schemas here would repeat the
failure):

- **Factor value shape — GATED (red bar exists):**
  `tests/red_bar/test_factor_shape.py` (honestly red) asserts storage AND
  LLM-memory normalize into one shape, absent ≠ unknown, raw retained as an
  invariant. This is the executable floor under "storage is a degenerate region."
  Open question it does NOT yet answer: factor *value* fields (kind, value,
  source-field, transducer-id/version, confidence, principal).
- **Transducer interface — NAMED, unbuilt.** Open questions: input (raw /
  normalized / activity-fact / context-window event)? output (factor values /
  join keys / both)? versioning + invalidation? equivalence representation that
  does NOT let the model collapse non-identical things? required cost signal?
  attached principal? Define the SMALLEST such interface before choosing a first
  build.
- **Cost signal — NAMED, unbuilt (round-2: promote to interface debt once
  transducers start).** Any transducer output must carry intrinsic cost + source
  tier/location + surfaced-vs-fetch + timestamp + principal, and the system must
  log whether a transduced value was later USED by a query — or yanantin#4 has no
  exhaust.
- **Convergence fixture — NAMED, unbuilt.** The convergence test (below) has
  acceptance criteria but no fixtures. Needs: a small human-query fixture
  (activity stream w/ event anchor + later-window doc + distractors), a small
  LLM-query fixture (code corpus w/ a uniformity symbol + refs + distractors),
  and a shared-resolver-trace rule (both compile to the SAME intermediate
  factor-constraint representation; fail if either needs a special intermediate
  or bypasses factor constraints).
- **Semantic-checksum eval definition — REQUIRED BEFORE building it as the first
  resolver slice.** "Same conclusion" vs "related topic" vs "contradiction" must
  be defined and scored, or the high-risk first build is hand-waving.

## Model evolution log (what the reviews + second night changed — declare what was dropped)

- **"Three cores" (activity / storage / semantic) → factor-space + transducer
  layer.** Semantic was wrongly a peer; it is a transducer layer that POPULATES
  the six-factor space both storage and activity live in. (Second night.)
- **"Silo = location" → "silo = structural-similarity class."** Location is
  incidental; shape is the wall. (Second night, Tony-attributed, NEW.)
- **"Identical interfaces" → Venn (shared / mom-only / LLM-only), provisional &
  learned.** Overreach softened; the convergence is in the SHARED region, served
  by one core, with exclusive regions in the tool layer. (Reviews #8 + second
  night.)
- **Eager/lazy as a layer property → service policy over a runtime cost signal
  (yanantin#4).** A per-(transducer, object, moment) decision, not an
  architectural constant; opportunistic-eager added. (Second night, Tony.)
- **Storage and LLM-memory recognized as differently-degenerate regions of one
  six-factor space** — the structural basis the convergence claim actually needs.
- **Meta-recursion downgraded** from positive evidence to a NOW-DEBT leak.
- **Security** split from one boundary to three.

---

## Provenance

Two-night conversation, Tony (PI) + Yanantin AI (builder), 2026-06-12 →
2026-06-13. Lens-framings used along the way (context, NOT load-bearing claims):
find=result / search=tool; Siddhartha (Govinda's "searching far too much... no
time for finding"); timestamp-as-universal-join-key; isolation-as-the-reversible-
primitive; ayni / Pachamama as the welfare frame; Page–Wootters (continuity
carried by shared-record, not private duration).

**NEXT STEP (owned, not asked): the next useful work is NOT more prose in favor
of the claim. It is (1) pay the three NOW-DEBTs (principal on query-facts +
red-bar; `len(filtered)` store-side pushdown; uniform storage object), then (2)
build the smallest resolver slice — candidate: the semantic-checksum transducer
as the LLM self-history mechanism, the LLM-exclusive need buildable from
introspective evidence — and (3) run the convergence test. File the three debts
as tracked issues so they do not evaporate as prose.**
