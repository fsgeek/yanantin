# Hypothesis: Late Binding as a Correctness Strategy

**Status:** Unresolved observation
**Observed:** 2026-02-27
**Observers:** Tony Mason, Claude Opus (session instance)

## The Observation

Three independently designed layers of Yanantin converge on the same
structural pattern: defer materialization until a question is asked.

| Layer | What's stored | What materializes | When |
|-------|--------------|-------------------|------|
| **Activity Anchor** | Timestamp + UUID | Facts across all streams at that moment | Query time |
| **Jabberwock** | UUID (near-empty entity) | Frabjous (resolved view with proof envelope) | `galumph()` or `uffish()` call |
| **Mome Vorpal** | Observation without entity binding | Claim event linking to an entity | When relationship is identified |

In each case, the stored artifact is deliberately minimal. Meaning
emerges at query time from whatever information exists *at that moment*,
including information that didn't exist when the artifact was created.

## The Claim

This is not lazy evaluation and not traditional late binding.

- **Lazy evaluation** defers computation. The shape of the result is
  fixed at definition time. A Haskell thunk knows what it will compute.
- **Traditional late binding** defers implementation choice. Virtual
  dispatch, dependency injection. The interface is fixed; the concrete
  fulfillment is deferred.
- **This pattern** defers the ontology of the result. The anchor doesn't
  know what streams will exist. The Jabberwock doesn't know what
  observations will arrive. The mome doesn't know what entity it belongs
  to. The *shape* of what materializes is unknown at write time.

The distinction: "I haven't computed the answer yet" vs "I don't yet
know what the question will be."

## Where It Appears to Work

- Adding a new activity stream retroactively enriches every past anchor
  without modifying any of them.
- Adding a new Vorpal retroactively enriches an entity without mutation.
  Frabjous (the materialized view) exists only for the duration of the
  query.
- Mome observations sit unresolved indefinitely. They are valuable
  pending, not erroneous unresolved.
- `extra="allow"` on stored records is structurally necessary: the event
  stream will contain facts recorded before the current schema knew what
  questions to ask.

## What Would Confirm It

- The pattern continues to emerge in new layers without being mandated.
- Systems designed with eager materialization in the same problem space
  develop update cascades, version conflicts, or cache invalidation
  problems that this architecture avoids.
- Prior art search finds this distinguished from lazy evaluation and
  late binding in the knowledge representation or database literature.

## What Would Refute It

- The pattern is simply the open-world assumption from knowledge
  representation, already well-characterized. (This would not refute
  the utility — only the novelty.)
- At scale, the deferred materialization cost becomes prohibitive and
  eager pre-computation is required for acceptable performance. (This
  would indicate the pattern is correct but impractical.)
- New layers require eager binding for correctness, revealing the
  pattern as accidental rather than structural.

## Literature Survey (2026-02-27)

Perplexity analysis (anti-biased prompt) found the components exist
in separate literatures but the specific combination is not named:

**Nearest relatives:**

| Concept | What it covers | Where it stops |
|---------|---------------|----------------|
| Event sourcing + CQRS | Append-only log, derived projections | Assumes fixed projection schema |
| Open-world assumption (KR) | Missing facts are unknown, not false; new predicates enrich old individuals | Logic/entailment context, not operational systems |
| Materialized vs virtual views | On-demand computation of derived state | View schema is fixed at definition time |
| Intensional vs extensional queries | Storing abstract handles, computing concrete answers on demand | Academic query processing, not architectural pattern |
| Log-centric architectures (Kleppmann) | Log is primary, views are derived; new views from historical log | New *projections*, not new *ontologies* |

**What appears distinctive in Yanantin (per Perplexity):**

- Deferred *ontology*, not just deferred state. The type-structure of
  what an anchor or mome participates in is open.
- Anchor as pure coordination key — stricter than most event-sourced
  identifiers, which are tied to an aggregate type.
- Observations intentionally unbound — mome as first-class citizen,
  not incomplete data to be cleaned.
- `extra="allow"` as a correctness condition, not just a convenience.

**Assessment:** "Plausible and nontrivial." The hypothesis is a unified,
systems-level articulation of a pattern that has mostly lived in
separate silos (DB design, KR, log-based architectures) and hasn't
been cleanly named in the form used here.

**Refutation criteria status:**

- "Just OWA" — *partially triggered*. OWA covers the semantics but
  not the systems architecture or the correctness framing.
- "Performance kills it" — *open*. Event sourcing literature
  acknowledges replay cost; materialized read models are the standard
  optimization. Whether this preserves the correctness properties is
  the real question.
- "Accidental pattern" — *weakened*. Independent emergence across
  three layers with different purposes is suggestive of invariant,
  not aesthetic quirk.

**Suggested framing for a paper:** "Ontology-Late Binding over Event
Logs" — contrasting static schema/state materialization with anchors +
open-ended streams + query-time ontology resolution. Indaleko-scale
workloads as empirical testbed.

## Related Concepts

- Open-world assumption (OWA) vs closed-world assumption (CWA)
- Event sourcing and CQRS (command-query responsibility segregation)
- Intensional vs extensional query answering (Jha, Olteanu, Suciu 2010)
- Log-centric architectures (Kleppmann, "Turning the Database Inside Out")
- Quantum measurement problem (analogy, not claim)
- Tony's observation: "a traditional cursor would materialize all the
  data — I looked at that and realized it becomes noisy and brittle"

## What We Don't Know

- Whether the unified framing adds explanatory power beyond the sum
  of its known components
- Whether it scales (Indaleko's 28.5M files would test this)
- Whether the consistency across layers reflects a deep principle or
  a single designer's aesthetic preference applied three times
- Whether the Jabberwocky naming strategy caused this pattern to
  emerge (by preventing pattern-matching to eager-binding frameworks)
  or merely didn't prevent it
- What the performance boundary looks like — where deferred ontology
  binding requires partial pre-materialization, and whether the
  correctness properties survive that optimization
