# Recorder → Collection Mapping (the association layer)

*2026-06-17. Brainstormed with Tony. Forks below are his calls, recorded inline.
Sequel to `2026-06-16-c0-registration-design.md` (the registrar primitive, built)
and its OPEN ITEM 3 (convergence of static collection lists onto registration).*

## What this is (one paragraph)

Registration (gh #1, built) answers **who has declared themselves**. It does NOT
answer **where a registered thing's data is stored** — and conflating the two is a
mistake made three times (Indaleko fused collection-creation into service
registration; the prior yanantin session reached for a static `_SEMANTIC_COLLECTIONS`
list and balked; this author posited a redundant "parallel registration stack").
This spec designs the **association layer**: given a registered service, how is its
data location chosen. It is deliberately small — a declared property in the
registration record's open tail plus the coding-level branch that honours it — not a
new subsystem.

## The disentanglement (read first)

**Registration ≠ collection-mapping.** They rhyme (both keyed by provider identity,
both init-time) but are orthogonal:

- **Registration** — `core.Registrar` (built). Catalog of who-exists, obfuscated,
  fail-stop, two-DB-isolation red bar green.
- **Collection-mapping** — THIS. The association from a registered *recorder* to the
  collection(s) its output lands in.

Indaleko dynamically created the collection *as part of* registering the service,
which entangled them in the author's mind. Pulling them apart is the whole insight:
a service can register without owning a collection (a collector), own several (a
storage recorder), or own one dynamically-named (a semantic transducer). The
cardinality is a property of the **registrant's role**, not of registration.

## Who registers, and why it's the recorder (not the collector)

**Recorders register — themselves AND the collector they record for (by proxy).**
The load-bearing reason: a collector may live on a device with **no live database
access**. It gathers data and hands it off through a wrangler — batch file, queue,
email attachment, FTP blind-drop, REST API, etc. — to a recorder that *does* have DB
access. The recorder is the side of the wrangler that touches the substrate, so the
recorder is what registers. `CollectorBase` already self-describes
(`get_provider_id()`, `get_description()`) precisely so the recorder can register it
*on its behalf*; the collector supplies, the recorder declares.

This also explains a fact found in the codebase: nothing in `src/` imports
`core.registration` yet (the seam is absent), and `CollectorBase` self-describes but
never registers. The collector was never *supposed* to register itself.

## The Record envelope (Indaleko fidelity — ported in spirit)

A recorder takes a collector's data and pickles it into a common provenance-bearing
form. In Indaleko (`data_models/record.py`, `i_object.py`) this is the **`Record`**:
an *embedded distinguished field*, NOT a top-level envelope. A `StorageObject`
(`IndalekoObjectDataModel`) *begins with* a `Record`. The `Record` carries:

- `SourceIdentifier` — provenance: which collector produced this (→ the registered
  provider_id).
- `Data` — the raw, uninterpreted source data, opaque blob, explicitly
  "do not index/parse sub-fields." This is **"save everything"** at the row level.
- `Timestamp`.

The recorder understands the collector's data via a **shared data model**. Because
every collector is paired — one captures *real* data, one generates *same-shape
synthetic* data, both using the **identical** data model (gh #27, dual-collector) —
the recorder always has two interchangeable sources for one shape. The data model,
not the collector instance, is the contract.

**Yanantin port:** we port the *idea* (uniform provenance-bearing embedded record +
opaque save-everything payload), re-expressed in yanantin terms, the way
`RegistrantRecord` was ported in spirit from Indaleko's registration service. This
spec does NOT freeze the yanantin `Record`'s field names — that is an
implementation-plan decision. It freezes that recorder output **embeds a
provenance-bearing record whose source resolves to a registered provider**.

## The three mapping cardinalities (by registrant role)

| Case | Registrant | Targets | Example |
|---|---|---|---|
| 1 | **collector** | **zero** — data never lands in the DB directly; it flows to a recorder | any collector |
| 2 | **recorder** | **N** — different kinds | linux-local-storage recorder → `Objects` (doc) **AND** `Relationships` (edge) |
| 3 | **semantic / activity** | **one, dynamically named** | a transducer → `{prefix}{uuid}` own-collection |

Case 2 is concrete and not arbitrary: a storage recorder emits into the **Objects /
StorageObjects** document collection *and* the **Relationships** edge collection.
One recorder, two associations, **of different kinds** (document vs edge). This is
why the registrar-tree model alone (the C0 spec's stacking) is insufficient for the
mapping: the tree expresses *collapse* (many leaves → one shared collection)
elegantly, but mangles "one recorder → one doc-collection + one edge-collection,"
which is not a collapse. The mapping is per-recorder data.

## The collapse axis: how established is the commonality (Tony's framing)

The real axis is NOT "declared vs structural." It is **how established is the
commonality of this registrant's output** — because **the collection is the unit of
schema the find pipeline passes to an LLM.** Find ("sloppy human episodic memory →
AQL") works by: identify query domains → pull schema for the relevant collections →
hand the schema package to the LLM. So **every distinct collection schema is a
recurring inference cost at read time, paid forever.** Eight playlist providers with
eight schemas = eight fragments the LLM reconciles to answer "what was I listening
to."

Two collapse states:

- **`shared(well_known)` — the EARNED commitment.** Land in a shared, well-known
  collection. Correct when commonality is *already known at write-time*:
  **linux-local storage** — decades-settled structure, the storage-silo problem is a
  *known* failure, reproducing per-source silos is the *known* mistake. Born
  collapsed. Bounded technical debt that is unlikely to shift.
- **`own(dynamic)` — the honest default for unestablished commonality.** Land in a
  dynamically-named own-collection. Correct when you have NOT seen enough providers
  to know they share structure: **spotify playlists** (is there a common "playlist
  provider" shape? unknown — possibly no common structure across playlist types),
  **EXIF** (and EXIF *inside* a JPG is useless for indexing — the transducer may even
  decide what is worth landing at all). Born split.

The write-side default is **un-collapsed**: do not assert commonality you have not
observed (the ROOT applied to schema — don't discard the joints before you know which
are load-bearing). `extra="allow"` makes a wrong collapse *non-destructive* anyway:
a shared collection validates the spine and KEEPS divergent fields in the open tail.

### The read-side cost, and why we accept it as debt now (Tony's call)

Split-by-default pays a schema-sprawl tax at find time. **We accept this as debt.**
Tony: eight playlist providers is a sign of *success*; the resolution belongs to the
success path, and we cannot pay down debt on a problem space we cannot yet see —
trying to is premature collapse. Two success-path levers are NAMED here so a future
ghola finds them, and NOT built:

1. **Read-side schema-collapse demon** — when a query domain has N similar
   own-collections, synthesize a unified schema-view for the LLM (the cold→warm
   promotion demon, applied to schema: write-side stays honest/un-collapsed; a
   read-side demon collapses *for presentation* once a domain is hot enough). See
   `project_effective_action_space_carnot_cycle`.
2. **View-as-schema-source** — an ArangoSearch view could *define what schema is
   available* to find, presenting N own-collections under one synthesized schema, so
   split-by-default costs nothing at read time once the view exists. Never used
   before; a tool for the success path.

**Decision: start with collection-shaped schema as the unit.** When that becomes
computationally expensive, re-explore the levers above. Capturing the collapse-state
shape now (below) IS the escape hatch for that future.

## The mechanism (small, no new subsystem)

The collection mapping is a **declared property carried in the registration record's
open tail** — `extra="allow"` is already there for exactly this. No parallel
registration stack (the author's posited stack was the registration/mapping
conflation again); no separate mapping service (a redundant second lookup); **no
registrar change** (it already stores and returns open-tail extra; it never reads
`contributes_to`).

A recorder registers with a `contributes_to` property: a list of targets, each
shaped roughly:

```
contributes_to: [
  { name, kind: "doc" | "edge", naming: "well_known" | "dynamic" }
]
```

- **Collector** registers with `contributes_to: []` (Case 1).
- **Linux-local-storage recorder** registers with two `well_known` targets:
  `{Objects, doc}` and `{Relationships, edge}` (Case 2).
- **Semantic transducer** registers with one `dynamic` target (Case 3).

### The registrar treats `contributes_to` as OPAQUE (Tony's correction)

Critical decomposition, and a place this author re-made the very conflation the spec
disentangles — one layer down. **The registrar does NOT parse, interpret, or act on
`contributes_to`.** It is open-tail extra: `extra="allow"` stores it and returns the
same-shaped object on lookup, knowing nothing about what it means. `contributes_to`
is a **self-description the recorder authors about itself and later reads back** — the
catalog (and the CLI, and find) can *see* the mapping, but the *acting* on it belongs
entirely to the recorder. The registrar is a dumb, faithful store of a fact the
recorder authored. This is what "registration ≠ mapping" actually demands; giving the
registrar a `well_known`/`dynamic` branch would hand the mapping *behavior* back to
registration, undoing the separation. (No registrar change is needed at all — it
already stores extra and returns it.)

The CLI inspector already reads the open tail, so the mapping is **visible through
`python -m yanantin.core` immediately**, no new read path.

### The coding-level branch lives in the RECORDER: well_known attaches, dynamic mints

`naming` selects the **recorder's** coding-level behaviour — ONE mechanism, two
branches, not two architectures, and NOT the registrar's job:

- **`well_known`** → the recorder **writes through the collection owned by a
  storage-object registrar.** `Objects` is created ONCE (the registrar that owns it
  created it via its existing `_ensure_collection` + obfuscator); linux-local and
  windows-local recorders both write through that same owned collection (the C0
  stacking diagram: `storage-object registrar owns Objects; platform recorders write
  into it`). "Owning" here means "created the collection and holds the handle the
  recorders write through" — coordination by shared collection ownership, NOT the
  registrar interpreting anything. The recorder is handed / looks up the owning
  registrar's handle; resolving that handle is an implementation-plan detail.
- **`dynamic`** → the recorder **mints its own** collection (`{prefix}{uuid}`), the
  own-a-collection degenerate case the C0 spec already names.

Capturing `kind` and `naming` in the stored shape is the escape hatch: a future change
(e.g. promoting `own → shared`, or view-as-schema) has a joint to grab without us
building that future now. Same move as `extra="allow"` — keep the shape, defer the
policy. The shape is stored opaquely by the registrar; only the recorder reads it as
behaviour.

## Scope of THIS pour

The canonical first vertical, end-to-end, against live `apacheta_test`:

**linux-local-storage `{collector, recorder}` → local-storage `{collector, recorder}`
→ storage `{collector, recorder}`**, where the storage-object registrar owns `Objects`
(doc) and `Relationships` (edge), and the linux-local recorder:

1. registers itself and its collector (by proxy) through `core.Registrar`, declaring
   `contributes_to: [{Objects, doc, well_known}, {Relationships, edge, well_known}]`;
2. takes the linux-local collector's data (real OR its synthetic twin — identical data
   model), pickles each item into the provenance-bearing record embedded in a
   StorageObject, and **contributes** it into the owned `Objects` collection (and the
   relationship into `Relationships`);
3. is visible end-to-end through `python -m yanantin.core` (the registrant appears, its
   `contributes_to` is readable, contribution counts are non-zero).

This makes the C0 spec's stacking test #7 LIVE with a real recorder + real (or
synthetic) collector data, and is the wake-note's stated next pour
(`project_c0_next_pour_linux_fs_registrar`).

## Out of scope (named, not built)

- The read-side schema-collapse demon and view-as-schema (success-path levers above).
- Migrating the OTHER collectors/recorders (filesystem, checksum, fs_events, dropbox,
  openrouter, machine_config) onto registration — one tested-green step at a time
  later; C0's OPEN ITEM 3.
- spotify / activity-stream Case-3 transducers — designed-by-example here, built when
  a real one is on the table.
- The StandardDatabase routing seam (C0 OPEN ITEM 1) — this pour runs on one DB.
- Freezing the yanantin `Record` field names — implementation-plan decision.

## Error handling

Fail-stop, inherited from `core.Registrar`: no storage ⇒ raise, never a false-empty.
**The recorder** (not the registrar) enforces the mapping: a `well_known` target whose
owning registrar/collection does not exist is an error the recorder raises (you cannot
write through a collection nobody owns), not a silent mint — the mint path is `dynamic`
only, chosen explicitly. The registrar stays opaque to all of this.

## Testing (green vs live `apacheta_test`, no mocks; dual-DB where the registrar is)

1. **Collector mapping is empty (Case 1):** a registered collector has
   `contributes_to == []`; it owns no collection.
2. **Recorder declares N targets (Case 2):** the linux-local-storage recorder
   registers with `{Objects, doc, well_known}` + `{Relationships, edge, well_known}`;
   assert both collections exist (under obfuscated names), one is a document collection
   and one is an edge collection.
3. **well_known attaches, does not duplicate:** register linux-local AND windows-local
   storage recorders, both declaring `well_known Objects`; assert `Objects` exists
   **once** and both recorders' contributions land in it, sliceable by provider
   (re-uses C0 stacking test #7's assertions, now driven by the mapping declaration).
4. **dynamic mints:** a recorder with one `dynamic` target gets a freshly-named
   own-collection; two such recorders do NOT collide.
5. **Record provenance round-trips:** a contributed StorageObject's embedded record
   resolves its source to the registered provider_id (provenance is real, not
   asserted) — the integrity threat model
   (`project_threat_model_integrity_not_confidentiality`) made concrete at the row.
6. **Real vs synthetic interchangeability:** the same recorder records from the real
   linux-local collector and from its synthetic twin (identical data model) — both
   produce schema-valid StorageObjects in `Objects` (gh #27 honoured).
7. **End-to-end visibility:** after recording, `python -m yanantin.core` lists the
   registrant, shows its `contributes_to`, and reports a non-zero contribution count.
8. **Fail-stop:** the recorder raises on a `well_known` target with no owning
   collection (no silent mint); unreachable store raises (no false-empty). The
   registrar itself never inspects `contributes_to` — a test asserts it round-trips
   `contributes_to` unchanged as opaque extra (proves the separation: the registrar
   stores the mapping without interpreting it).

Test/builder separation enforced by CI; red-bar floor must actually RUN. Stronger
tests are never an error.

## Lineage / why this is not over-built

The mechanism is one field (`contributes_to`) in an open tail that already exists, plus
one coding branch (`well_known` attach vs `dynamic` mint). Everything heavier — the
schema-collapse demon, view-as-schema, cross-DB routing, migrating the other providers
— is named and deferred. We capture the *shape* (kind/naming) so a future with more
information has a joint to grab, and build only the linux-local-storage vertical that
the domain is settled enough to commit to today.
