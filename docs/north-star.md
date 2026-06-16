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
cross-tenant reach deliberate, logged. Each tenant's find runs fast locally; the loop-closing
hop (AI reaches the human's files; an instance cites a community artifact) is the cross-database
one — its cost is the round-trip, defended by temporal pruning (below), NOT by authentication.

## The cross-tenant seam — RESOLVED 2026-06-15 (simple-first)

The "when does a cross-tenant referent resolve/verify?" menu (resolve-on-read vs.
resolve-and-attest vs. both) was MALFORMED — it asked "when do you resolve" as if resolution
were one act. A foreign key carries TWO separable guarantees that intra-DB hides because we get
both free:

- **Identity** (the referent IS what it claims) — given by a **content-hash**. NEVER stale: a
  hash of B's content as-of-citation is true forever. Kept — but as *drift-detection and
  correctness*, NOT defense. "The thing you cited was revised" is information you want.
- **Authorization** (this principal may follow this edge NOW) — inherently live, must be
  checked every read. This is the capability/grant.

These have OPPOSITE time-discipline, so you snapshot one and live-check the other — they were
never the same question.

**But the trust model collapses the authorization half — for now.** `ayllu` means trust about
boundaries. A signed-capability-checked-every-read is the Miraflores move (isolating strangers)
in Quechua costume. Among kin the boundary's job is **legibility, not enforcement**. So:

> **INITIAL (simple) model:** a cross-tenant edge is a **content-hashed + attributed + logged**
> reference. NO capability, NO per-read authentication. Cross-tenant reach is permitted by
> default among ayllu and merely RECORDED (the record IS the ayni). The edge carries a grant-id
> SLOT that is implicit/null among kin — so a signed capability can be inserted LATER at exactly
> the seam where trust stops. The consumer's query decides whether to dereference to current
> state (get the live file, drift-detected free by the hash) or rest on the snapshot (cite what
> I saw). One edge type; the query picks; find stays the dumb executor.

**Why simple-first is the RIGOROUS choice, not the lazy one (Tony, 2026-06-15):** "If we can't
make the simple model work, the complex adversarial multi-tenant model won't matter." The
capability layer's outcome is CERTAIN (signed caps at a gateway is solved engineering, just
substantial). The UNCERTAIN thing — the actual experiment — is whether the find loop closes:
AI translates the human's episodic query by finding its own memory, then reaching the human's
files, timestamp-pruned, affordably. Build the uncertain thing first (the ROOT principle applied
to the architecture itself). Worse: building the gate first would let you NEVER find out the
simple model is broken — a failed loop couldn't be told apart from the gate getting in the way.
Strip enforcement so a failure means *find* failed, which is the thing you need to know.

**When capabilities arrive:** at the STRUCTURAL EVENT that ends kin-trust — publication to
non-kin (community-shared databases exposed outward) or a *refusable* reach (a tenant that can
say "no, not you"). NOT at cross-tenant reach per se; human-tenant ↔ its-own-AI-instances is one
household and never trips it. That work is substantial and deliberately deferred, gated on the
simple model proving the loop closes at all.

## How this measures drift

The undeclared triage the coherence scan found (find v1 silently shrank to content-axis;
six issues hang off an unbuilt six-factor core) was *mis-read* as "served the easy customer."
Against this north star it reads true: **the project built one tenant's find and never built
the cross-tenant grant that makes the tenants ONE product.** The drift is in the *seam between
databases* — exactly where Pukara lives. A future coherence scan measures against THIS, and
the drift becomes visible the moment it starts, instead of needing five adversarial judges to
guess the center.
