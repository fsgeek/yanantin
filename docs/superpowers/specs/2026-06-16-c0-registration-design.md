# C0 — Provider Registration (the first core pour)

*2026-06-16. Design source ported from `~/projects/indaleko/utils/registration_service.py`.
Written after a ground-reading pass that disarmed two ghosts the handoff carried. Brainstormed
with Tony; the forks below were his calls, recorded inline.*

## What this is (one paragraph)

The common core's missing primitive (gh #1): a mechanism by which **any** provider — semantic,
storage, activity, or a kind nobody has invented yet — **declares itself**, and the substrate
organizes around it. It replaces the static `_SEMANTIC_COLLECTIONS` lists (the disease: collections
known only by a hardcoded tuple that someone must remember to edit) with a dynamic registry. Born in
`src/yanantin/core/`, it is the first and (day one) only inhabitant.

**The model is NOT one-provider-one-collection.** That assumption (which an early draft of this spec
carried, copied uncritically from Indaleko's `{prefix}{uuid}` collection naming) breaks the most
important thing the substrate does — see the Stacking section. A provider does not necessarily *own*
a collection; it registers with a **registrar** that owns a collection and accepts contributions
into it, and registrars themselves stack. The purpose of registration is to make the system's
contents **data, not code**: the catalog of what-exists becomes queryable instead of a Python literal,
which is the precondition for find-across-silos (you cannot search a space you cannot enumerate) and
the architecture-level antibody to the closed-schema reflex.

## The disambiguation that unblocked this (read first)

Three distinct mechanisms were colliding under the words "mapping" and "registration". They are
**not** the same thing; conflating them is what made the build-order doc reach for a DuckDB mapping
store that does not need to exist.

1. **Label obfuscation** — `semantic_label → opaque_label`. The `StorageObfuscator` protocol
   (`apacheta/storage_obfuscator.py`, stdlib-only contract) + Pukara's `SchemaMap` (the keyed
   implementation, instantiated *only* at `pukara/app.py:41`). A **stateless, per-deployment,
   compute-from-key function** — NO stored table, NO DuckDB, NO allocation. Already built, already
   wired into both arango backends, already placed exactly where the threat model wants it. **Not
   core to build; the protocol is already a dependency-inverted leaf.** The "DuckDB mapping layer"
   in the build-order doc is a GHOST — it would re-implement, as a stored table on the substrate, a
   thing already solved as a keyed function in the fortress. Building it would *undo* a correct
   boundary. **Cut from C0 scope as a reversible bet** (Tony is not certain it is a ghost; neither
   am I): the one thing SchemaMap genuinely cannot do is store a `semantic_description` per label
   (it computes opaque names, it does not remember *why* a name exists). If a real need for
   stored-description lookup appears, the DuckDB store comes back *for that*, not for obfuscation.
   The bet is asymmetric in our favor: if cutting it was wrong, a missing-description need surfaces
   loudly; if right, we never notice. So we cut it now and let the ground report back.

2. **Connection identity** — `(host, db_name, username) → handle`. The `get_database` singleton
   (`infra/config.py`). **Per-principal** (username IS the identity axis). This is where #13's
   "one DB+user per instance" lives — it is an axis the singleton *already keys on*, not a new
   subsystem. Generalizing 3-tiers → N-principals, and *who routes which principal*, is the
   honestly-OPEN StandardDatabase routing seam. **Registration does NOT resolve it** — registration
   uses whatever principal it is handed; identity-per-instance is an *above* concern.

3. **Provider registration** — "who has declared themselves, and what collection is their home."
   Indaleko's `registration_service.py`. **This is C0.** It is NOT the label layer and NOT the
   identity layer; it rides *on* the connection singleton and *through* the obfuscator.

Label obfuscation (per-deployment, one key) and connection identity (per-principal, N users) are
**orthogonal axes** — they rhyme because both involve UUIDs, but one disguises labels and the other
allocates connections. Neither constrains the other.

## The guideline that keeps the strangler-fig safe: the dependency arrow points ONE way

**Guideline (not a law — a decision made visible): everything depends on `core`; `core` depends on
nothing but the database singleton + stdlib.**

Stated as a guideline on purpose. It is not a stylistic absolute and not a wall to be enforced — it
is hard-won pain-avoidance written down so the next decision is visible. Tony's reason is concrete
and unglamorous: **Python initialization dependency loops are genuinely miserable**, and this
guideline's whole job is to make a cycle-creating import *a visible choice* rather than an accident.
The known future pressure that motivates it: Pukara must validate capabilities → Pukara inherits a
dependency on the IAM layer → IAM lives in core. If core reaches *back* toward `apacheta` /
`transport` / `pukara`, you get `apacheta → pukara → core → apacheta` — exactly the init loop the
guideline exists to keep visible. So crossing it (importing transport/apacheta/pukara/activity/
llika/chasqui from core) is something you do *on purpose and in writing*, not by reflex.

Consequence for design: registration does NOT import `transport.ProviderRegistration` (that would
make core depend on transport — a crossing with no reason behind it). It defines its **own** registry
record.

## Stacking — the collection topology IS a tree of registrars (Tony, 2026-06-16)

The load-bearing insight, and the correction to Indaleko's one-provider-one-collection model.

**A registrar owns one collection and accepts registrants that contribute into it. A registrar can
itself be a registrant of a registrar below it.** Registration *stacks*:

```
linux-local-fs recorder ──registers with──▶ local-storage-object registrar
                                                  │ (is itself a registrant of)
                                                  ▼
                                            storage-object registrar  ──owns──▶ Objects collection
                                                  │
                                                  ▼
                                            base registrar
```

The leaf (linux-local) **does not know how far down it collapses.** It registers with its parent;
where its data ultimately lands is a property of the tree, not of the leaf. This single recursive
application of one primitive produces **both** topologies an earlier draft wrongly split into two
mechanisms:

- **"Own a collection"** = a registrar with one registrant and no collapse below it (Indaleko's
  `{prefix}{uuid}` per-provider collection is just this *degenerate case* — not the model).
- **"Contribute to a shared collection"** (the `Objects` case) = many leaves register with one
  registrar that owns the shared collection; provider identity becomes a **field on the record**,
  not the collection name.

**Why `extra="allow"` is the enabling condition for stacking, not just a closed-schema antibody:** a
shared collection can only absorb heterogeneous registrants losslessly if it validates the common
spine and *keeps* their divergent fields. Linux-local and Windows-local collapse into one `Objects`
collection because `Objects` validates the shared file-object spine and preserves platform-specific
fields in the open tail. The record-shape decision and the stacking decision are the same decision.

**The collapse-depth is the logical data model, and it is a deliberate knob.** Five separate platform
collections → "files on storage type X" is a collection lookup, but "all my files" is five-scans+merge
(the RAG fan-out the north star is defined *against*). One mega-collection → "all my files" is one
scan, but "just linux-local" is a filter and the representation has lost its joints. Neither extreme is
free; the registrar tree is *where you place the seam* between them, per the query pattern. `Objects`
reproduced: a storage-object registrar owns `Objects`; platform recorders register with it; "all files"
is one scan, "linux-local only" is a `FILTER`. North star intact.

### Two topology decisions, with their visible expiry (Tony's calls — guideline, not law)

1. **C0 builds the FLAT, stacking-COMPATIBLE primitive — not the recursive composable node.** Tony:
   registration is *rare* (init-time), so keep the stack simple-but-layered; a 3–4-deep registration
   walk at startup that is "annoying to walk" beats a pretty recursive abstraction that is load-bearing
   in ways that bite later. C0 builds a registrar (owns one collection, accepts registrants) such that
   "a registrar is itself a registrant" is an *additive* later step, not a rewrite. (Building the
   `Objects` vertical first *produces* this primitive as a byproduct — so the concrete-first and
   flat-primitive options were never orthogonal.)

2. **The registrar tree (who registers with whom) is CODE.** The interior nodes / collapse points are
   the substrate's deliberate, stable logical model, defined in core code; leaf providers register as
   data. Tony's honesty test: moving a collapse seam needs a data migration *regardless* of whether the
   tree is code or data, so code is the more honest default — it does not pretend the seam is cheap to
   move. **A speculative "expiry" was floated (topology becomes per-tenant data when a tenant reshapes
   its own collapse) and then WITHDRAWN — on the wrong axis and wrong on its own terms.** Wrong on its
   own terms: re-shaping topology into a *new shape* changes the tree-walking code regardless of
   data-vs-code (data-driven only buys you re-*parameterizing* an existing shape, not introducing a new
   one — and the realistic divergence is new shapes). Wrong axis: the real multi-tenant pressure is NOT
   tenants reshaping topology — it is that the storage object space is *shared* across tenants (see the
   StandardDatabase section). Tree-as-code stands without the asterisk.

## The hard physical boundary: stacking lives inside ONE StandardDatabase (Tony, 2026-06-16)

The registrar/stacking model is bounded by a database fact, not a design preference: **ArangoDB native
edges cannot span StandardDatabase objects.** The apacheta backend's whole graph story —
`CompositionEdge`, `ProvenanceEdge`, llika composition edges, lineage traversal, the epistemic graph —
is intra-database and load-bearing. So:

- **The registrar tree, its collapse, and the shared `Objects` space all operate WITHIN one
  StandardDatabase.** Edges work there; `Objects` is traversable there. The spec's stacking model is
  correct *for that space* and assumes it.
- **The storage object space is COMMON-TENANT-ACCESS by design.** AI instances and humans both reach
  the *same* object space — it is shared, NOT per-tenant-isolated. This is a different regime from #13's
  per-instance isolation, which is for *private* spaces (continuity notes, an instance's own memory).
  Two regimes coexist: one shared traversable object space, and per-tenant private spaces.
- **Cross-tenant / cross-database relationships are FOREIGN KEYS, not edges** — store the target id as a
  field, resolve by application-level lookup, gated by Pukara as an authz decision (the cross-tenant
  seam: "a foreign key whose JOIN is an authz decision"). They live ABOVE the registrar (the routing
  seam, OPEN ITEM 1), never inside it. **The registrar never tries to span databases — it physically
  can't, and must not pretend to.**
- **Status today:** the code runs effectively one database (`apacheta` / `apacheta_test` are env tiers,
  not tenants — never related to each other). Per-tenant StandardDatabases and cross-database foreign
  keys are designed-not-built. C0 builds on the single-database reality and is correct under it.

## Components

### `core/registration` — the registrar

A registrar node, ported in spirit (not line-for-line) from `IndalekoRegistrationService`, stripped of
Indaleko's `ServiceManager`/singleton infrastructure. One node = two responsibilities:

- **Registry** — owns a registrant catalog. Verbs: `register` (a provider or a child registrar),
  `lookup_by_identifier`, `lookup_by_name`, `list_registrants`, `deactivate`, `delete`. Each registrant
  is a record (below). A registrar may itself register upward (the stacking edge) — flat/layered in C0,
  not a recursive abstraction.
- **Collection ownership** — the registrar owns ONE collection that its registrants contribute into.
  Creating/ensuring that collection **delegates to the obfuscator-aware creation already proven in
  `apacheta/backends/arango.py:196-198`** (`has_collection` guard → `create_collection(mapped,
  edge=...)` → indices via `add_persistent_index`). It does NOT re-implement collection creation, and
  names pass through the `StorageObfuscator` like every other collection (Tony: "literal now, obfuscate
  later" is an illusion of choice — through the obfuscator from the first pour). The degenerate
  per-registrant-UUID collection (Indaleko's `{prefix}{uuid}`) remains available for the own-a-collection
  case, but is one option, not the model.

### The registry record — `frozen=True, extra="allow"`

A Pydantic model, core's own (NOT transport's). The shape Tony named "very yanantin-like":

- **`frozen=True`** — a registration, once made, is immutable. You supersede, you don't mutate
  (matches the supersession-in-place architecture).
- **`extra="allow"`** — the record never refuses a field it didn't anticipate. Provider kinds
  nobody has invented yet carry kind-specific metadata that is *kept*, not rejected. This is the
  save-it-all law and the Harness-1 "type the mechanical, leave the rest free" pattern made
  structural; it is the antibody to the closed-schema reflex (re-imposing `extra="forbid"` while
  designing the defense against it). The typed spine stays validated; the open tail absorbs the
  not-yet-categorized.

Typed spine (the mechanical, validated part): `registrant_id: UUID`, `registrant_name: str`,
`registrant_kind: str` (e.g. `"provider"` vs `"registrar"` — the stacking edge), `description: str`,
`contributes_schema: dict | None` (the shape this registrant promises to write into its registrar's
owned collection; used to validate contributions, not to mint a private collection), `parent_id: UUID
| None` (the registrar it registered with — `None` only for the base), `registered_at: datetime`,
`active: bool`. Everything else: allowed and stored.

## Why `transport.ProviderRegistration` is NOT this (and stays put)

`transport/models.py:19` has a `ProviderRegistration` that *looks* like the registry record. It is
not. It is a **transport DTO** — a passed-in config value describing the source feeding a wrangler
envelope ("what is this data source, what does it produce"). The wrangler does not consult a global
registry; its source/sink hands it this description. Different noun, confusingly-similar name. It
stays in transport (no move, no blast radius, no back-dependency). Convergence, if ever, is a later
tested-green step — not C0's job. (Tony's cut: "Why do the wranglers need registration? Why wouldn't
it be a passed-in configuration value from the sink or source?" — they don't; it is.)

## Dependencies (the porting surface)

- **Connection singleton** — `infra/config.py` `get_database` / `ApachetaDBConfig`. ALREADY EXISTS.
  Registration sits on it. (The dedicated *separation layer* — per-StandardDatabase isolation — is
  a later core concern, NOT a prerequisite for this pour; a single StandardDatabase is correct under
  every outcome of the routing question.)
- **`StorageObfuscator` protocol + `TransparentObfuscator`** — stdlib-only, already
  dependency-inverted. **Moves into `core/` as part of this pour** (resolved below): registration
  needs it to create obfuscated collection names, and a `core → apacheta` import to reach it would
  be an unmotivated crossing of the one-way guideline. The protocol is a contract-leaf, so the move
  qualifies under the entry rule; apacheta + activity backends update their import to the core path
  (small, tested-green). Low-regret by Tony's test: if the move is wrong the import graph / tests
  say so loudly; if right, it's silent — so we just do it rather than gate registration behind a
  separate ceremony.
- **stdlib** — `uuid`, `datetime`. A `validate_uuid_string` helper (trivial; core's own).

Indaleko bits explicitly DROPPED: `IndalekoSingleton` (we have a connection singleton),
`IndalekoServiceManager` self-registration (no master-service-catalog layer for C0 — one registry;
Tony: collapse to one for C0, reintroduce the split only if a real need appears), `INDALEKO_ROOT`
path bootstrap, OSError-swallowing (fail-stop instead).

## Error handling

Fail-stop, per the build-order guideline. No storage ⇒ hard stop; no in-memory fallback, no
graceful-degradation (simulating a capability you don't have is the lie). Indaleko's `except OSError:
return None/[]` swallowing is NOT ported — a registry that can't reach its store must raise, not
return an empty list that reads as "no registrants."

## Testing (green vs live `apacheta_test`, no mocks)

Per the no-mock-databases rule, tested against the live `apacheta_test` DB:

1. Register a registrant → assert the catalog row exists, keyed by `registrant_id`, with the typed
   spine + an extra field that survived (proves `extra="allow"` round-trips through ArangoDB).
2. A registrar ensures its owned collection → assert the collection exists **under its obfuscated
   name** (proves the obfuscator seam), with schema validation + indices applied.
3. Re-register same UUID → raises (no silent overwrite).
4. `list_registrants` → returns the registrant(s).
5. Ensure-collection through a `TransparentObfuscator` vs a stand-in opaque obfuscator → collection
   name differs accordingly (proves the seam is real, not decorative).
6. Fail-stop: registration against an unreachable store raises, does not return empty.
7. **Stacking (the load-bearing test):** build `base ◀ storage-object-registrar(owns Objects) ◀
   {linux-local, windows-local}`. Both leaves register; both write a record (shared spine + a
   platform-specific extra field) into the ONE `Objects` collection. Assert: (a) one collection, not
   three; (b) "all files" = one scan returns both; (c) "linux-local only" = a `FILTER` on the identity
   field returns just linux's; (d) both platforms' extra fields survived (lossless collapse — proves
   `extra="allow"` is what makes stacking work). This test is the spec's claim that `Objects` is
   reproducible; if it's red, the stacking model is wrong, not the test.

Test/builder separation enforced by CI; the red-bar floor must actually RUN these.

## RESOLVED during brainstorm

- **`StorageObfuscator` moves into `core/` as part of this pour.** (Was open; Tony's
  reversible-bet test resolved it — see Dependencies above. Day-one core = registration + the
  obfuscator contract-leaf. This is the one thing that makes C0 a leaf-plus-one-small-move rather
  than a pure zero-blast-radius leaf; the move is self-revealing if wrong.)

## OPEN ITEMS (Tony's calls — do NOT collapse)

1. **The StandardDatabase routing seam** — who decides which principal/DB a call routes to
   (capabilities/handles Pukara routes on). Its own brainstorm, Tony driving. C0 builds on ONE
   StandardDatabase and is INDEPENDENT of how this resolves.

2. **The shared object space vs cross-database foreign keys** — the storage object space is
   common-tenant-access (shared, one StandardDatabase, traversable). Per-tenant private spaces are
   isolated (#13). A relationship crossing that boundary is a Pukara-gated foreign key, NOT an edge
   (ArangoDB can't span databases). How the shared space is physically sited relative to per-tenant
   DBs, and how foreign keys resolve across them, is the routing seam's harder half — designed, not
   built. C0 builds the single-database registrar; this is the layer above it.

3. **Convergence of the `_SEMANTIC_COLLECTIONS` tuples onto registration** — the apacheta + activity
   backends' static lists become registered providers/registrars. This is A1 / downstream, NOT C0.
   C0 just builds the mechanism they will later migrate onto, one tested-green step at a time.
