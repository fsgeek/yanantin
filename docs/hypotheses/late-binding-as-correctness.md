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

### Fourth instance: Context window compaction

The research-program's T7 ("The Design") proposes replacing consumed
tool outputs in agentic sessions with compacted cells: conclusion +
declared losses + retrieval handle. The full output materializes only
when a future question needs it. This is the same pattern applied to
conversation memory:

| What's stored | What materializes | When |
|--------------|-------------------|------|
| Compacted cell (conclusion + losses + handle) | Full original tool output | When future instance retrieves by handle |

Empirical baseline (T5, 26 sessions): 78.2% of context window is
consumed by tool outputs that have already been acted on. This is
the measured cost of eager materialization in this domain — the
conversational equivalent of the cursor that materializes all data.

The compacted cell is structurally a mome: the observation (tool
result) has been recorded, but its full content is not bound into the
current context. It materializes only when the question demands it.
Different questions retrieve different originals from the same
compacted summary.

**This provides a concrete, measurable test of the hypothesis.**
Phase 1 measures the cost of eager binding. Phase 2 tests whether
deferred binding preserves correctness (non-inferiority). If
compacted sessions produce equivalent quality, deferred ontological
binding works for conversation memory. If they degrade, we learn
where the pattern breaks.

See: `~/projects/research-program/tensors/T7_the_design.md`

### Fifth instance: Pager summary as anchor handle

The Pichay context pager (`~/projects/pichay/`) implements the
fourth instance's design. When tool results are evicted, they are
replaced with a retrieval handle:

```
[Paged out: Read /path/to/file.py (8,192 bytes, 187 lines).
 Re-read the file if you need its content.]
```

This was designed as a space-saving measure — a human-readable
marker to reduce context consumption. In practice it functions as
a late-binding anchor:

| What's stored | What materializes | When |
|--------------|-------------------|------|
| Path + size + retrieval instruction | Full file content at current state | When model re-reads (page fault) |

The critical difference from the fourth instance's theoretical
design: the anchor resolves to *current* content, not the original
evicted content. A file edited since eviction materializes at its
new state. This is the same temporal property as activity anchors
(new streams retroactively enrich old anchors) but applied to
files on disk.

**Behavioral confirmation:** When a fresh instance resumed a
session with paged-out content, it unprompted said: "Let me
re-read the files I need since some were paged out." The model
recognized the handles and chose to fault content in before acting.
The pattern was understood without instruction — the handle's
format carries its own semantics.

**Measured:** Over 681 turns, 659 page faults fired — the model
consistently pulled on handles to recover content it needed. The
97% fault rate is a pathology (thrashing, not efficient paging),
but it confirms the mechanism works: the model knows how to use
the handles.

See: `docs/phase1_context_utilization.md` (Phase 2 results),
`docs/cairn/T31_20260302_the_page_fault.md` (tensor from the
instance that was simultaneously builder and test subject).

## What Would Confirm It

- The pattern continues to emerge in new layers without being mandated.
  **Status: confirmed (twice).** The research-program's T7 design
  independently converges on the same structure for context compaction
  — a fourth layer, designed by a different instance, with no knowledge
  of this hypothesis. The Pichay pager summary — designed as a
  space-saving marker — independently became a fifth instance when the
  retrieval handle turned out to be an anchor. The instance that built
  it recognized this while experiencing context pressure from its own
  pager (T31).
- Systems designed with eager materialization in the same problem space
  develop update cascades, version conflicts, or cache invalidation
  problems that this architecture avoids. **Status: testable.** Phase 1
  measures the cost; Phase 2 tests non-inferiority.
- Prior art search finds this distinguished from lazy evaluation and
  late binding in the knowledge representation or database literature.
  **Status: partially confirmed** (see Literature Survey).

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

## Fifth Instance: Context Windows as Virtual Address Spaces

**Observed:** 2026-02-28
**Observers:** Tony Mason, Claude Opus (research-program instance, session instance)

The Phase 1 context utilization study found 79.4% tool overhead and
84.4x main session amplification. The Phase 2 ablation study found
large system prompt sections removable without degrading task
performance. Together these measure the cost of eager materialization
in context windows — everything is loaded, everything stays.

The research-program instance independently proposed modeling context
windows as object-based virtual memory. The key extension beyond
hardware VM:

| Hardware VM | Object-based context VM |
|-------------|----------------------|
| Pages are passive bytes | Objects are active — have operators, queryable at multiple granularities |
| Load all or none | Page in a header (200 bytes), drill down on demand |
| Page table maps virtual → physical | Graph edges map objects → related objects |
| LRU/clock eviction | Access pattern eviction (which operators were called) |
| Prefetch by spatial locality | Prefetch by graph adjacency (Markov model over knowledge graph) |

### Tools as object factories, not data pipes

Current architecture: tool call → raw output dumps into context →
stays forever until compaction. Proposed: tool call → output captured
*outside* context → lightweight proxy (summary + available operators)
enters context → model works through operators at needed granularity →
proxy ages out when model moves on.

The raw data never enters the context window. The operator model is
better than TTL or explicit release because with those, data has
already entered and you're trying to claw it back. The operator model
avoids creating the problem.

### Snapshots, not persistent state

Critical insight (Tony, 2026-02-28): "Each call to the transformer
is *de novo* — it has no knowledge of what was there in the prior
version." The context window is not RAM. It's reconstructed fresh
every forward pass. "Removal" is trivially just "don't include it in
the next snapshot." The hard problem is not the mechanism — it's the
**eviction policy**: knowing what's safe to exclude without breaking
the model's reasoning.

This is the page replacement problem. LRU, clock algorithms, working
set models — all exist because eviction is easy and knowing *what* to
evict is the entire discipline.

Objects with operators give you the signal for eviction policy: which
operators the model called (access recency, frequency, breadth). Without
objects, the context is a flat text stream with no access pattern
information. You can't distinguish a linter warning already fixed from
a module structure the model is still navigating by.

### Demand-paged system prompts: the practical wedge

The ablation study already mapped natural page boundaries in system
prompts. System prompt sections have every property needed for demand
paging:

- **Clear boundaries** — already structured as discrete sections
- **Predictable access patterns** — git protocol needed for git ops,
  skill listings needed when considering skills
- **Detectable faults** — model emits `git commit` → page fault on
  git safety protocol → include in next snapshot

This is the conservative starting point. Well-bounded, empirically
validated (ablation study is the page map), low-cost faults (one extra
round trip to page back in, not catastrophic reasoning failure).

**Refuted claim (2026-03-01):** An analysis-phase instance stated
that subagents spawned by Claude Code receive two copies of the system
prompt. Proxy verification (Phase 1 instrument, `proxy_20260301_054903.jsonl`)
shows this is **false**. Subagents receive a specialized, shorter system
prompt tailored to their role:

| | Main session (Opus) | Subagent (Haiku) |
|---|---|---|
| System prompt size | 15,877 bytes (4 blocks) | 4,859 bytes (3 blocks) |
| Identity line | "You are Claude Code..." (57B) | Same (57B) |
| Instructions | Full agent instructions (11,628B) | "File search specialist" (4,463B) |
| Memory/CLAUDE.md | Present (3,751B) | Absent |

The subagent prompt is 3.3x smaller — no duplication, no wasted context.
The architecture is smarter than the claim suggested: Claude Code tailors
the system prompt per agent type. The original claim propagated through
three links (analysis instance → Tony → session instance → hypothesis doc)
without verification at any link. This is the provenance failure the
Arbiter paper describes — unverified claims amplified by confident framing.

**Provenance:** Claim originated from an analysis-phase instance
(2026-02-28), accepted by Tony as a bound judge spending budget
parsimoniously, amplified by a session instance with confident analogy,
written into this document as fact, corrected to "unverified" by a later
instance, and finally refuted empirically by proxy capture (2026-03-01).

### Mapping to existing Yanantin architecture

| VM concept | Yanantin equivalent | Status |
|-----------|---------------------|--------|
| Virtual address | Memory anchor (timestamp + UUID) | Implemented |
| Page table | Activity stream (maps anchors → facts) | Implemented |
| Named object | Jabberwock entity (Tove/Vorpal/Rath) | Implemented |
| Object operators | Brillig methods (galumph, uffish, whiffling) | Implemented |
| Page fault | Anchor materialization at query time | Implemented |
| Graph adjacency = prefetch model | Rath edges predict working set | Implemented (structure), not yet used for prefetch |
| Operator-based access tracking | Not yet | Missing — needed for eviction policy |
| Object proxy in context | Not yet | Missing — the MMU layer |
| Working set manager | Not yet | Missing — snapshot constructor |

The pieces exist. What's missing is the intermediary that sits between
tools and the context window — the MMU that holds raw output, presents
proxies, and constructs each snapshot from only what's needed.

### Connection to late-binding

This is the same pattern again. Don't commit to full resolution until
the consumer demands it. Anchors defer materialization. Jabberwock
defers entity resolution. Context compaction defers what to keep. And
object-based VM defers content loading to the granularity the model
actually needs. Five instances of one principle.

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
- Whether eviction policy can be driven purely by access patterns
  (LRU over operator calls) or requires modeling the model's intent
  — the recursive quality of needing to understand what the model is
  doing to know what it needs
- What the right granularity for "objects" is — tool output objects
  are coarse; file-section objects are finer; AST-node objects may be
  too fine. The granularity determines the resolution of the eviction
  signal
- Whether the demand-paged system prompt approach (the conservative
  wedge) delivers measurable improvement — this is directly testable
  with the existing ablation infrastructure
