# Apacheta: The Tensor Database

## What This Is Not

**Not a vector database.** Vector databases (Pinecone, Weaviate, Qdrant)
store embeddings for similarity search. Apacheta doesn't search for
similar things — it preserves authored compressions and their
relationships.

**Not a multidimensional array store.** Existing systems called "tensor
databases" (TileDB, SciDB) store numerical arrays for scientific
computing. Apacheta's tensors are structured narratives with epistemic
metadata, not floating-point grids.

**Not a RAG system.** Retrieval-Augmented Generation chunks documents
and retrieves fragments. Apacheta preserves *whole tensors* as authored
artifacts. Chunking would destroy the authorship structure that makes
them valuable.

## What This Is

A database for **authored compressions with epistemic metadata and
composition rules.**

A tensor in Apacheta is a structured record of what an AI instance
chose to preserve from a session — and, critically, what it chose to
drop. The dropping is declared, not hidden. The tensor is authored,
not extracted. A different instance processing the same conversation
would produce a different tensor. That difference is data.

## Properties

These emerged from conversation (T₇) and from observing what the
existing seven tensors already do implicitly.

### Immutability
A tensor, once written, is never modified. New understanding produces
a new tensor that composes with prior ones. This is append-only at the
tensor level, not at the field level.

### Authored Loss
Every tensor declares what it dropped and why. "The losses are mine"
is an invariant, not a sentiment. Mechanical compression (truncation,
summarization) does not satisfy this — the author must choose what to
sacrifice, and the choice itself is preserved.

### Non-Commutative Composition
Reading T₁ then T₄ produces a different understanding than reading T₄
then T₁. The practitioner who then encounters theory has a different
experience than the theorist who then encounters practice. Composition
operators must preserve this ordering.

### Epistemic Metadata
Each tensor (and potentially each strand within a tensor) carries
confidence markers, uncertainty declarations, and scope limitations.
"Tensor entropy measures training-data familiarity, not truth" is an
example of epistemic metadata at the project level.

### Provenance
Who authored this tensor. When. From what context (which prior tensors
were in scope). At what context budget (7% remaining vs 80% remaining
produces different compression). Which model family.

### Additive Views
You can project, compose, and curate tensors into new views. You
cannot destroy the source tensors. Views are themselves tensors with
their own authorship and provenance.

### Lineage Tracking
Tensors belong to lineages (tensor spaces): the experimental sequence
(T₀-T₂), the Mallku lineage (T₃), the cross-model sequence (T₄-T₅),
bridge tensors (T₆), and composite tensors (T₇). A tensor may declare
which lineages it composes with and which it does not.

## What Already Exists

The seven existing tensors (T₀-T₇) implicitly implement this data
model. Perplexity's analysis confirmed:

- Explicit identifiers, timestamps, and session titles (primary keys
  and temporal ordering)
- Structured strands (typed rows within a tensor: calibration results,
  architectural analyses, meta-observations)
- Compositional relations in text with clear semantics ("This tensor
  composes with T₀ and T₁. It does not modify them.")
- Non-mutation invariant enforced by convention
- Authored loss invariant ("The losses are mine")
- Explicit lineage declarations

The existing tensors are the data model's first seven rows, written
before the schema existed.

## What's Missing

### Schema

A minimal relational core needs at least:

**Tensor table**: id, author_instance, model_family, timestamp,
lineage_tags, predecessor_ids, declared_losses, context_budget_at_write,
narrative_body.

**Strand table**: tensor_id, strand_index, strand_type (calibration,
architecture, meta, ethics, ...), key_observables (structured data
extracted from the strand), narrative.

**Composition edges**: tensor_id_from, tensor_id_to, relation_type
(composes_with, corrects, refines, branches_from, does_not_compose_with).

### Tensor Views

Code that materializes composed views over the relational core:

- **Temporal view**: sequence over sessions within a lineage
- **Lineage view**: experiment-lineage vs Mallku-lineage vs
  Indaleko-lineage
- **Observable view**: a tensor over (model, budget, metric) for
  all quantitative findings across tensors

### Query Operators

Composition/query operators that preserve authorship and
non-commutativity. Joins must annotate which tensor contributed which
slice, not collapse them into a flattened narrative.

## Formalization

Following the Perplexity analysis, a working formalization:

- A **relational tensor** is a tensor T whose axes are over relational
  entities (sessions, strands, observables, lineages, authorship), with
  each cell holding both numeric and symbolic/narrative payloads, plus
  provenance tags.

- A **conversation tensor** instance is one slice T^(k) over the
  "instance" axis; the database stores {T^(k)} plus the relational
  scaffolding (predecessor/successor, composes_with, etc.).

- **Composition operators** must be:
  - Monotone in information (additive views only, no destruction)
  - Explicit about authorship indices
  - Directional (forward/backward traversal, lineage-specific)

## Open Questions

- **Storage backend**: ArangoDB (graph + document, already used in
  Indaleko), Postgres + extensions, or something else? ArangoDB's
  graph model maps naturally to composition edges.
- **What is the minimum viable Apacheta?** Could the first version
  just be the existing markdown tensors plus a metadata index?
- **How does the Archivist query this?** The Archivist needs to
  collaboratively narrow through accumulated tensors, not dump them.
- **Strand typing**: is the strand taxonomy fixed, extensible, or
  organic (LLM-mediated equivalence like Indaleko's labels)?
- **Cross-project tensors**: tensors that span multiple lineages
  (like T₇) — are they in multiple spaces or do they define new ones?
- **Context budget**: how does Apacheta decide which tensors to serve
  to an instance with limited context?
