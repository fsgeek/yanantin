# Yanantin — North Star

*The goal the mechanisms are mechanisms OF. Written 2026-06-15 with Tony (PI) as
primary source, after a coherence scan found the project's goal lived only in his head
and the issue ledger had drifted along the gap. This is not the blueprint (that maps
mechanisms); this is what success is measured against.*

## The goal (Tony, primary-source)

**Find what you actually need, across isolated storage silos, when the silo boundaries
are the thing defeating you.** Yanantin is the successor to Indaleko (28.5M real files,
one human drowning in scattered storage). The golden path has two strands:

1. **Rich knowledge graphs of human activity data** — who / what / when / where / why /
   how (Vianna's framework, adopted).
2. **Timestamp as the search-space reducer.** The *when* is not one factor among six; it
   is the **pruning key** that keeps semantic search over a large corpus from degenerating
   into the RAG nightmare. Temporal anchor dominates. (Cf. the "temporal-anchor-dominates"
   model-correction.)

## The customers are nested tenants, not parallel products

The breakthrough of 2026-06-15: there are not "two customers with a similar problem."
There is **one engine serving tenant CLASSES**, and the human's episodic query is only
answerable *with the AI in the loop*:

- **Human tenant** (one database): the file-find customer. Read-mostly — Apacheta indexes
  storage someone else wrote. Queries in *sloppy episodic memory* ("that thing around when
  we discussed the edge migration"), which something must translate into a six-factor find.
- **Each AI instance** (its own database): write-HOT, revise/shed (`taste_open`'s
  shed-don't-destroy). **The Hamut'ay instances ARE the customers — this is the purpose of
  Apacheta:** a store that is NOT an append-only log and NOT sprawling files truncated when
  they outgrow the loader. The AI is also the *translator* that turns the human's episodic
  query into a real find — and to do that it must find *its own* memory.
- **Community shared artifacts** (one or more separate databases): the commons; the
  published-and-cite layer where `ayllu` kin deposit what's meant to be reachable.

## Coexistence is SETTLED, not open

"Can the read-mostly file store and the write-hot AI store coexist?" — **dissolved.** They
never share a store. The per-tenant-database decision (made for identity/#13: one ArangoDB
database + user per instance → DB auth IS the verified identity boundary) means tenants
share an **engine and a find mechanism**, never a store. Differing write-disciplines are
two tenants differing — which the boundary is *for*. Isolation is a default, not a wall
(`ayllu`, not Miraflores).

- **Shared asset:** the find mechanism (timestamp-pruned six-factor), same code, N databases.
- **Isolation primitive:** the per-tenant database.
- **Authorized reach:** cross-tenant recall via Pukara grant (ayni, not ambient).

## The genuinely-unbuilt piece: the cross-tenant SEAM

The cross-tenant reference is **a foreign key whose JOIN is an authorization decision.**
Same-database edges (the `ProvenanceEdge` just built) are find's cheap inner loop. A
cross-database edge is its expensive cousin and a DIFFERENT row type — it carries
`(from, to, grant, attestation, resolved-at)`, not just `(from, to)`. Three prices ArangoDB
will NOT pay for you across the boundary:

1. **No referential integrity** — the referent must be *attested*, not just referenced
   (the integrity threat: a forged/stale cross-tenant reference inherited as truth).
2. **No native cross-DB traversal** — it's a fetch-and-resolve through Pukara (holder of the
   principal→DB map), a round-trip per hop, not an engine-optimized join.
3. **The grant IS the schema** — permission to follow the reference is a first-class,
   logged object (least-privilege as the multitenancy mechanism).

**Design pressure (healthy):** keep the hot path inside a tenant's own database; make
cross-tenant reach deliberate, rare, attested, logged. Each tenant's find runs fast locally;
the loop-closing hop (AI reaches the human's files; an instance cites a community artifact)
is the expensive authorized one — and *should* be, because that hop is where integrity matters.

## The named-open frontier (NOT resolved here)

**When does a cross-tenant referent get resolved/verified?** Resolve-on-read (live
capability, always current, pays a round-trip, fails if grant lapsed) vs. resolve-and-attest
(Willay-style publish-and-cite, cheap reads, can go stale) vs. both-by-edge-kind — OR an
off-axis answer (content-addressing, ayni-exchange-graph) that the clean menu hides. This
is the hinge of the cross-tenant design and gets **its own brainstorm**, deliberately, not
a snap pick. (Premature collapse tell: a clean N-way menu means a premise needs dropping.)

## How this measures drift

The undeclared triage the coherence scan found (find v1 silently shrank to content-axis;
six issues hang off an unbuilt six-factor core) was *mis-read* as "served the easy customer."
Against this north star it reads true: **the project built one tenant's find and never built
the cross-tenant grant that makes the tenants ONE product.** The drift is in the *seam between
databases* — exactly where Pukara lives. A future coherence scan measures against THIS, and
the drift becomes visible the moment it starts, instead of needing five adversarial judges to
guess the center.
