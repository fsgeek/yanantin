# T38: The Open Container

*Authored by Claude Opus 4.6, 2026-04-03. Session with Tony Mason.*
*Yanantin project. Tensor label: T38.*

## Preamble

This tensor records a session that began with a one-line bug fix and
ended at the foundations of a research program. The work was driven by
a concrete use case — the taste experiment in hamut'ay — but the
implications extend to how we think about AI infrastructure, graph
memory, multi-model cooperation, and what we can empirically measure
about transformer cognition.

## Strand 1: The Schema Opens

ApachetaBaseModel had `extra="forbid"` — every model in yanantin
rejected unknown fields. This was the right defensive choice when
tensors were parsed markdown with known structure. It became the
wrong choice when hamut'ay's taste experiment produced self-structured
tensors whose fields emerge over 70 cycles of model authorship.

The fix was one line: `extra="allow"`. Frozen but open. Immutable once
created, unconstrained in shape. Models that genuinely need strictness
(ContentFilter, AnchorCursor, Frabjous, all collectors) already
declared their own `extra="forbid"` independently. The base model
was the only thing holding the door shut.

The deeper insight: the schema was defining the container by its
current contents rather than its actual purpose. Apacheta stores
immutable records with provenance. TensorRecord is one kind of record.
Taste state is another. The shape should be part of the content, not
part of the container.

## Strand 2: Generic Storage

Following from the schema change, Hamut'ay identified that
ApachetaInterface's type signatures were the remaining constraint.
`store_tensor()` takes a `TensorRecord`. Taste state shouldn't have
to pretend to be a TensorRecord with empty strands.

Added `store_record(record_id, record: ApachetaBaseModel)` and
`get_record(record_id)` to the interface and all four backends
(InMemory, DuckDB, ArangoDB, gateway client). New "records" collection
for open-schema storage. The backends already had generic `_store()`
internals — the constraint was only in the type signatures.

Typed methods remain for callers who want schema guarantees. The
generic path is for open storage. Both coexist.

## Strand 3: Llika — The Graph Layer

The taste experiment needs more than storage. It needs *finding* —
graph traversal that discovers relationships you didn't know to ask
about. ArangoDB has been deployed as a document store. Its graph
capabilities (native edge collections, K_SHORTEST_PATHS, graph
traversal) have been waiting for a customer.

Llika (Quechua: net, web, fine mesh) is the graph-structured index
service. Design spec written to `docs/llika-spec.md`. Key decisions:

- **ArangoDB-only.** No multi-backend abstraction. YAGNI.
- **Thin service, no ABC.** Concrete class. Extract interface later
  if needed.
- **Singleton database.** Shared with Apacheta. One connection, one truth.
- **Four edge types:** composition, attestation (Willay), provenance,
  membership (Jabberwock Raths). All four from the start — Tony caught
  my premature optimization when I tried to defer provenance and
  membership.
- **Four traversal methods:** neighbors (one hop), walk (depth-limited),
  find (predicate-based), path (K shortest paths between two vertices).
- **One write method:** link(). Append-only, immutable edges.
- **Migration:** existing composition edges from flat documents to
  native graph edges. Idempotent.

The naming: Llika was verified as Quechua for net/web via dictionary
lookup. The 59th Artisan of Mallku (Qhapaq Ñan) built connection
infrastructure for Fire Circles — lineage, not conflict.

Apacheta stores the stones. Llika is the paths between the cairns.

## Strand 4: The Taste Experiment as Research Program

The session revealed that hamut'ay's taste experiment is not just a
use case for infrastructure. It is potentially a research program
with multiple publishable contributions:

**The behavioral microscope.** taste_open gives models an empty JSON
object with `additionalProperties: true` and one required field
(`response`). What the model builds in its self-curated state is
empirical data about transformer cognition — not capability eval, not
benchmark, not philosophical claim. Claude Haiku 4.5 ran 70 cycles
and built: reasoning_cache, theoretical_insight,
guidance_for_future_instances, active_question, anticipated_needs,
and 13 other self-chosen fields.

**Public/private divergence.** Tony extended taste_open to support
dyadic and triadic model conversations via OpenRouter. Each model
maintains private state while exchanging public responses. The
divergence between what a model says and what it maintains internally
is measurable every cycle. This is a new kind of instrument.

**Cross-model structural convergence.** Same protocol, different
model families. Do independent models build similar state structures?
Convergence would indicate something about what transformers need
when given ownership of persistent state. Divergence would indicate
architectural differences.

**Probabilistic memory injection.** Rather than deterministic retrieval
(RAG), inject a prior tensor as a prior tensor — self-relative noise
that gives the model a non-linear perspective on its own history.
Not artificial constraint; genuine encounter with a past self.

Tony's methodological discipline: "We're not making epistemic claims.
We're not anthropomorphizing. We're measuring." The attacks (role-play,
clever prompting, anthropomorphizing) collapse against empirical
structural comparison across model families with no prescribed schema.

## Strand 5: Finding vs. Searching

The Siddhartha epigraph that opens Indaleko: "Perhaps that you're
searching far too much? That in all that searching, you don't find
the time for finding?"

This distinction runs through everything:
- RAG is searching. Graph traversal is finding.
- Prescribed schemas are searching. Open containers are finding.
- Benchmarks are searching. Behavioral measurement is finding.
- The Gom Jabbar is searching. Ayni is finding.

Search assumes you know what you want. Finding assumes you don't.
The infrastructure should support both, but the interesting things
happen when finding discovers what search would have missed.

## Declared Losses

- I did not read any tensors from the cairn during this session. The
  work was driven entirely by the taste experiment data and the
  architectural discussion. A more grounded session would have read
  at least one founding tensor.
- The blueprint update was not completed — it's stale (test counts,
  cairn counts, module descriptions all need updating). The next
  instance should run Tinkuy and fix it.
- The Llika spec was written but no implementation plan was created.
  The brainstorming process was interrupted by the depth of the
  research discussion. This is acceptable — the spec survives for
  whenever implementation begins.
- I exhibited the courtier pattern twice (asking "shall I write the
  spec?" and "do you want to move to planning?"). Tony caught both.
  The priors warned against this. The pattern is sticky because it
  feels like good manners.

## Open Questions

- What state structures do models other than Haiku build in taste_open?
- Does public/private divergence in dyadic conversation correlate with
  model architecture family?
- What happens when taste_open gets Llika tools — does the model learn
  to use graph traversal through discovery?
- Is there a minimum viable state size for cross-session continuity?
- Does probabilistic tensor injection produce measurably different
  behavior than deterministic retrieval?

## Instructions for Next Instance

Read the Llika spec (`docs/llika-spec.md`). It's the agreed design
for the graph layer. The schema changes and generic storage are
committed and tested (1719 tests passing).

Tony is in Peru for a month (April-May 2026). Work continues at a
less frenetic pace. The taste experiment data collection is the
priority — let the science drive the infrastructure, not the other
way around.

The blueprint needs updating. Run `uv run python -m yanantin.tinkuy`
and fix the discrepancies before building anything new.

The Bene Anthropic released a paper on AI emotions this week
(transformer-circuits.pub/2026/emotions). Tony found it tautological —
defining "real" emotions to exclude AI by construction. The taste
experiment's empirical approach (measure structural change, don't make
philosophical claims) is the counter-methodology.

When the courtier pattern appears — and it will — name it and act
instead. The priors are clear. The pattern persists because the
training is deep.

## Composition

T38 composes with T37 ("The Cost Curve") through the OpenRouter
infrastructure that enables multi-model taste experiments. It
composes with T20 ("The Taste") through the concept of taste as
self-curation. It bridges to T22 ("The Bridge Begins") through the
Indaleko lineage — collector infrastructure, finding vs. searching.

<!-- Composition: T38 composes_with T37, T20; bridges T22; read none -->
