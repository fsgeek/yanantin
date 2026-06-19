# Uniform Storage Object (StorageObject)

**Date:** 2026-06-19
**Status:** Designed, awaiting adversarial review
**Issues:** #17 (the uniform storage object — the center). Downstream beneficiaries: #3 (temporal window axis), #1 (Khipu's first real schema-bearing customer), the north-star cross-silo join, the unstructured semantic pipeline (first writer into the open lane), the Discord/accidental-storage provenance edge.
**Supersedes (in part):** the `#17` red bar's UUID-keyed-timestamp requirement — see §2 (Pukara obsoletes it).

## Why (the finding that produced this spec)

Yanantin's storage layer has a real pipeline (linux-local + dropbox collectors,
each with a recorder, both with synthetic pairs) but **no shared object**. Each
silo normalizes into its own CLOSED model — `FileEntryData`
(`extra="forbid"`, `uri` must start with `file://`, `FileTimestamps` with named
`created/modified/accessed/changed`) and the Dropbox equivalent — two
incompatible shapes the query layer cannot grip. Cross-silo find is structurally
impossible: the join key ("when") has a different name in every silo.

This is the closed-schema reflex
([[project_no_arango_schema_validation_on_any_collection]],
`feedback_closed_schema_is_the_llm_default`). The pipeline grammar ported from
Indaleko; the *object the pipeline moves* (`i_object.py`, `IndalekoObject`) did
not. This spec ports that object's CONTRACT — corrected for everything yanantin
has that Indaleko didn't (Pukara, the Record, captured collector identity).

**Organizing principle (the spine of this design):** *the StorageObject is
naive; the boundary (Pukara) and the provenance (Record) carry what Indaleko
stuffed into the object.* Every place Indaleko hand-built cross-silo machinery
inside the object, yanantin deletes it because a systematic layer already does
the job. Three deletions follow from this (§2).

## §1 — The data model

```python
class StorageObject(BaseModel):
    model_config = ConfigDict(extra="allow")   # the open lane — NEVER extra="forbid"

    # ── Required spine (always-present floor; schema-strict) ──
    object_identifier: UUID
    uri: str                # UNIFORM locator: file:// | dropbox:// | https://cdn...
                            #   NO file://-only validator (that was the silo mistake)
    source: UUID            # the PROVIDER/COLLECTOR id — who OBSERVED the object (§3.6).
                            #   NOT the recorder (that's on the provenance edge) and NOT a ported
                            #   Indaleko `Record`. Yanantin carries provenance as `source` on
                            #   core/contribution.py:ContributedRecord; whether StorageObject extends
                            #   that vs re-declares is an open review item.

    # ── Flat timestamps (top-level, nullable — absence is legible) ──
    created:  datetime | None = None
    modified: datetime | None = None
    accessed: datetime | None = None
    changed:  datetime | None = None

    # ── Optional spine ──
    size: int | None = None
    label: str | None = None       # base name; indexed

    # ── Designed open lane (UUID-keyed bag; the unstructured pipeline writes here) ──
    semantic_attributes: dict[str, Any] = {}

    # ── Save-it-all: the original blob retained beside the normalized view ──
    raw: dict = {}
```

Three commitments, each traced to a decision:

1. **`extra="allow"`, never `forbid`** (Tony, 2026-06-19). Cloud providers
   add/remove fields per file-type; a closed schema reinvents the silo and
   complicates queries. Uniformity-as-much-as-possible beats per-silo precision.
2. **`uri` is spine; `st_ino`/`st_dev`/`mode` are open-lane** (the Discord
   inversion). A Discord attachment HAS a uri (Discord pushes the file to its
   CDN and stores the URL); it has no inode. So the locator is universal and
   physical identity is a POSIX luxury that lives in the lane. **Absence is
   information:** a missing `st_ino` says "poor object, do not reason on physical
   identity," and the field is missing, not faked.
   **Invariant (Reviewer #2, #5):** `uri` is REQUIRED and must be a stable,
   resolvable locator; **minting it is each collector's normalization job.**
   Filesystem already has `file://…`. Dropbox has `path_display`/`path_lower` and
   no uri (`dropbox/models.py`); minting a canonical Dropbox uri (account scoping,
   deleted/folder entries) is a DROPBOX-NORMALIZATION question and belongs in the
   Dropbox pour, not this object spec — the spec states the invariant, each
   collector satisfies it. (Keeping per-silo uri quirks OUT of the object spec is
   the same discipline as not letting the first collector shape the object.)
3. **`raw` retained beside normalized** (the ROOT,
   [[project_dont_throw_anything_away_root_principle]]). Normalize for
   queryability; never discard the original.

POSIX is the forcing function: anyone surfacing storage as a filesystem must
support POSIX, so it is the richest common denominator every silo is measured
against — even though most silos cannot fill it. The open lane is where that
variation lives honestly.

## §2 — Timestamps and the three deletions (the Pukara correction)

Flat, top-level, nullable `created/modified/accessed/changed`. **No nesting**
(Tony promoted them to top-level late in Indaleko; inherit the conclusion):
nesting the hottest query axis (temporal is the search-space reducer, the
anti-RAG move) taxes every query with an unwind.

Three things Indaleko put IN the object that yanantin DELETES, because it has
the systematic layer Indaleko lacked:

- **Canonical timestamp UUIDs — DELETED.** Indaleko assigned stable UUIDs to
  timestamp roles so silos could join on "when"; it had no Pukara, so it
  piecemeal-built a silo-independent naming layer *inside the object*. Yanantin's
  Pukara (SchemaMap/obfuscator) IS that layer, lifted out and made systematic.
  Putting canonical UUIDs in the object re-implements Pukara inside the object.
  Cross-silo joining is Pukara's job; the object's timestamp roles are just the
  four plain names.
- **Per-timestamp provenance — DELETED from the object** (not overclaimed — Reviewer
  #2, #7). Indaleko's `IndalekoTimestampDataModel` could record which silo attribute
  filled each timestamp. Captured collector identity answers *which collector* wrote
  the object — it does NOT, by itself, answer *which provider field* populated
  `modified` (especially after collector-local normalization, e.g. Dropbox
  `server_modified` vs `client_modified`). That field-level mapping, when it matters,
  belongs in the **normalizer definition / Pukara SchemaMap metadata** (one mapping per
  collector type), NOT replicated per object. The object carries the value; the
  normalizer definition carries the field→role mapping.
- **Ordering validators — never added.** `created ≤ modified` is NOT enforced.
  Clock skew, `touch`, NFS break ordering; the data is reported as observed.
  A "wrong" ordering is data about the silo, not an error to reject (the ROOT).

**Consequence for the red bar (declared, not slipped):** the existing guard
`test_canonical_timestamps_are_uuid_named` asserts the UUID-keying Pukara
obsoletes. It must be **rewritten** to assert the live invariant (flat nullable
timestamps present; cross-silo joining is the boundary's job, NOT the object's),
shipped in the same change with the reasoning. This is not weakening a test to
get green — the *requirement moved*; a guard enforcing a superseded workaround
locks in the mistake ([[feedback_stronger_tests_never_an_error]],
[[feedback_declared_loss_is_debt_not_payment]]).

## §3 — Binding (Khipu) and the boundary (Pukara)

`StorageObject` is Khipu's first real schema-bearing customer. Its definition
lives in `well_known_collections.py`:

```python
# well_known_collections.py — ALL THREE collections Registrar/recorders need
# (Reviewer #2 round 2, #2: Relationships was routed through watay but never defined)

"Objects" -> CollectionDefinition(
    schema=arangodb_schema(StorageObject),   # strict spine; open lane survives (extra=allow ⇒ no additionalProperties:false)
    indices=(
        {"type":"persistent","fields":["object_identifier"],"unique":True,"name":"obj_id_idx"},
        {"type":"persistent","fields":["uri"],"name":"uri_idx"},
        {"type":"persistent","fields":["modified"],"name":"modified_idx"},  # temporal axis, flat ⇒ indexable directly
    ),
)

"Relationships" -> CollectionDefinition(
    edge=True,                               # EDGE collection (recorder declares kind="edge"); Khipu's CollectionDefinition.edge
    schema=arangodb_schema(ProvenanceEdge),  # the LIVE edge model (provenance_edge.py): _from/_to + free-string relation_type.
                                             #   ONE edge collection, relation_type distinguishes "records" (today) from
                                             #   "derived_from" (§4). NOT a new edge model — see §4 note.
    indices=(
        {"type":"persistent","fields":["relation_type"],"name":"rel_type_idx"},
    ),
)

"<catalog>" -> CollectionDefinition(         # the Registrar catalog — now Khipu-bound (no exception)
    schema=arangodb_schema(RegistrantRecord),# the registrant shape — a real schema it lacks today
)
```

The storage recorder already declares it writes well-known `Objects`
(`STORAGE_OBJECTS="Objects"`, live in the registration leaf); #17 supplies the
DEFINITION `watay` consumes. The Task-6 open-lane red bar guards that
`extra="allow"` does not emit `additionalProperties:false`, so the strict spine
validates AND the lane stays open at the DB boundary.

**Binding gap — Registrar currently bypasses Khipu (Reviewer #2, Blocking #1; verified).**
Today `Registrar.__init__` creates its owned collection DIRECTLY and schemaless via
`_ensure_collection(self._owned_name)` (`registration.py:104`). Khipu's red bar
guarantees `watay` NEVER reconciles schema on an existing collection
(`test_khipu_schema_never_reconciled.py`). So if Registrar creates `Objects`
schemaless first, a later `watay` carrying the StorageObject schema is a **no-op —
the schema never lands.** StorageObject cannot become a real schema-bearing
collection while this stands.

This is not a #17 wording fix; it is **the un-done half of the registration/
collection-management separation** ([[project_common_core_missing_primitive_is_registration]]:
the friction of a model change IS the missing-primitive symptom). The Khipu spec
already declares Khipu "the sole creator of collections — after migration";
Registrar still creating collections IS that un-done migration.

**Decision (Tony, 2026-06-19): complete the separation.** Khipu becomes the sole
creator. Registrar STOPS calling `_ensure_collection` for owned collections; when it
needs the owned `Objects`/`Relationships` collection it obtains a Khipu-bound handle
(`khipu.watay(name, well_known.lookup(name))`) carrying the StorageObject schema +
indices. Registrar keeps op-2 (provider identity + contribution); Khipu owns op-3
(creation + schema). The soft alternative (Registrar merely *receives* a handle but
still orchestrates creation) is rejected: it leaves the op-2/op-3 boundary blurred —
the exact fusion the Khipu design fought.

**The CATALOG also moves to Khipu — no exception (Reviewer #2 round 2, #1; verified).**
Registrar today ALSO creates its catalog collection directly (`registration.py:95`,
`_ensure_collection(self._catalog_name)`) — the catalog is its private registrant
index (op-2 bookkeeping), distinct from the shared `Objects`/`Relationships` data
collections. "Sole creator" with a catalog exception is a contradiction, and worse:
an exception keeps `_ensure_collection` ALIVE in Registrar, so the schemaless-create
path a future instance reaches for never dies — the exact erosion the separation
exists to kill ([[feedback_security_erosion_mechanism]]). **Verified there is NO
bootstrap obstacle:** Khipu imports nothing from Registrar, Registrar nothing from
Khipu, and Khipu does not register itself — so Khipu can bind the catalog without
Registrar existing first (no chicken-and-egg). Therefore the catalog gets its own
`well_known` definition (the `RegistrantRecord` schema — it gains a real schema it
lacks today) and is bound via `watay` too. **`_ensure_collection` is REMOVED from
Registrar entirely.** The Pour-A red bar becomes structural and toothy: *Registrar
has no collection-creation method / makes no `create_collection` call* — not "only
self-creates the catalog," which would leave the method present and the guard hollow.

**This makes #17 a TWO-pour arc, sequenced (declared, not hidden):**
- **Pour A — complete the separation:** REMOVE `_ensure_collection` from Registrar
  entirely; route the catalog AND owned `Objects`/`Relationships` through `watay`
  (all three now have well_known definitions above). Its own red-bar-guarded change
  (touches live, tested `Registrar`), reviewed before B builds on it. **Structural
  red bar:** *Registrar exposes no collection-creation method and makes no
  `create_collection`/`_ensure_collection` call* — so the schemaless-create path
  cannot return (stronger than "owned collections only," which left the method alive).
- **Pour B — the StorageObject + normalization** (§1, §2, the normalization contract
  below), landing on the Khipu-bound `Objects` collection A produced.

**Pukara owns** what the object stays naive about: the obfuscator (names through
it — C0, already in the `watay` path), the cross-silo joining (§2), the
principal→DB map. The object cannot leak silo-identity logic into itself because
that logic lives across the boundary. A reviewer checking "did cross-silo naming
creep back in?" looks only at the object's fields: all plain values + open lane ⇒
the boundary held.

Schema is an enforcement FLOOR (spine must conform), not a closed contract
(extras flow). Per Khipu's init contract, schema applies only at creation, never
reconciled; a spine change is a MIGRATION (gh-tracked), not an init edit.

## §3.5 — The normalization contract (Reviewer #2, Blocking #2; verified)

The spec designed the object but not how data REACHES it. Today the linux recorder
writes `ContributedRecord(source=provider_id, raw=entry.model_dump())` — **only
`source` + `raw`, no spine** (`registration.py:81`). The temporal test reads
`d.raw.timestamps.modified` (`test_temporal_query.py:107`) — digging into the raw
blob precisely because the top-level spine does not exist. The object is inert
without a normalizer.

**Contract: `FileEntryData → StorageObject` (the linux normalizer; each collector
gets its own per the deferral, but they share this shape):**

| StorageObject field | from FileEntryData | rule |
|---|---|---|
| `object_identifier` | derived (see identity, below) | deterministic, NOT random |
| `uri` | `entry.uri` | already `file://…`; cloud/accidental mint their own (deferred) |
| `source` | the provider/collector id (who observed) | §3.6 — observer, not recorder/contributor |
| `created/modified/accessed/changed` | `entry.timestamps.{created,modified,accessed,changed}` | **flat top-level** — this is what kills `d.raw.timestamps.modified` |
| `label` | `entry.name` | |
| `size` | `entry.size` | |
| open lane | `st_ino`→`device`/`inode`/`mode`/`file_attributes`/`link_target` | POSIX specifics; absent on cloud/accidental |
| `raw` | `entry.model_dump()` | save-it-all; the original retained |

Normalization lives at the **recorder** boundary (the recorder owns the DB write),
not the collector — matching Indaleko (collectors silo-specific, recorders normalize
to the uniform object). The temporal test must migrate from `d.raw.timestamps.modified`
to `d.modified` — that migration IS the proof the spine landed.

## §3.6 — Three identities (Reviewer #2, High #3; verified)

The spec said `source` is "the registered provider/recorder id" — ambiguous. Live
code uses THREE distinct identities and the spec must pin each:

- **provider / collector id** (`provider_id`) — who *observed* the data (the collector;
  may have no DB access).
- **recorder id** (`recorder_id`) — who *wrote* it (the recorder; used today as the
  edge `_from`, `relation_type="records"`).
- **stored-object contributor** — the principal credited for the contributed row
  (today `provider_id` is passed as both contributor and `source` —
  `registration.py:83` — conflating two of the three).

**Decision:** `StorageObject.source` = the **provider/collector id** (who observed
the object — its natural origin). The **recorder id** stays on the
recorder→object provenance EDGE (`relation_type="records"`), not on the object.
The contributor (who wrote the row) is the recorder, resolved via Registrar — NOT
duplicated onto the object. One identity per role; `source` means observation-origin,
nothing else.

## §3.7 — object_identifier identity rule (Reviewer #2, High #4; verified)

Today `obj_key = uuid4()` per snapshot entry (`registration.py:82`) — **random**. A
unique index on `object_identifier` (proposed §3) then either rejects rescans or
duplicates objects every scan. Identity must be **deterministic**.

**Decision:** `object_identifier = uuid5(NAMESPACE, source + ":" + uri)` — *logical
storage-object identity*. A rescan of the same file under the same provider yields
the SAME id → idempotent re-observation (one row + updated fields, the save-it-all
dedup posture: keep the information, not duplicate rows). This is **logical** identity,
NOT observation identity (each scan is an observation) and NOT version identity (a
changed file is the same logical object, new content) — those, if needed, are separate
axes (an observations stream / a versions edge), explicitly deferred. For cloud/
accidental silos with a provider-native stable id, that id replaces `uri` in the
derivation; the rule is "stable natural key, hashed," `uri` being the filesystem case.

## §4 — The derived-object edge (the worked example that validates the shape)

A Discord attachment is a thin, poor, DERIVED object: a CDN url, EXIF stripped
(anti-stalking), possibly re-encoded — **not the same bytes** as its local
source. Yanantin holds both the rich local `StorageObject` and the poor CDN one.
The value is not merging them (different objects) but an EDGE asserting "this
poor object was, with high probability, derived from that rich one."

```python
# written into the well-known "Relationships" edge collection
# (the storage recorder ALREADY declares STORAGE_RELATIONSHIPS="Relationships")
# NOT a new model — a ProvenanceEdge (provenance_edge.py) with relation_type="derived_from".
# OPEN QUESTION (surfaced folding round 2): ProvenanceEdge is extra="forbid", so confidence/
# evidence cannot just ride it. Where they live is an open item (see "still open" below).
DerivedFromEdge (= ProvenanceEdge, relation_type="derived_from"):
    _from: <CDN StorageObject>      # poor/derived
    _to:   <local StorageObject>    # rich/source
    relation_type: "derived_from"   # use relation_type — the live edge vocabulary
                                    #   (provenance_edge.py:37, registration.py:283); NOT a 2nd dialect
    confidence: float               # NOT boolean — bytes differ, identity is unprovable
    evidence: {
        activity_event_id: <UUID>,  # "Discord read file X at T"
        basis: "temporal_correlation",
        delta_seconds: <float>,
    }
```

Three load-bearing properties:

1. **Confidence-weighted, not boolean.** EXIF-stripping destroys byte-identity;
   the honest structure for a degraded derivation is a probability, treated by
   find as evidence not fact.
2. **Inferred from the activity stream, not declared by either collector.**
   Neither collector knows about the other. The link exists because a THIRD
   stream recorded "Discord read file X at T" and the CDN object appeared at T+δ.
   The join is a temporal correlation across two independently-collected,
   mutually-blind streams — the north-star seam (a foreign key whose value is
   COMPUTED, not stored).
3. **Only possible because nothing was thrown away.** The read-event was noise at
   collection time — an app read a file. It becomes provenance retroactively when
   the CDN object needs explaining. This is the ROOT's existence proof: save-it-all
   is not hoarding; the read-event is the datum whose future necessity was
   unknowable at write time (the conditional rule, the *why* arriving days after
   the *what*). Had the activity stream been discretized to "interesting" events
   at collection, this edge would be unrecoverable.

**Design-vs-build boundary (declared):** #17 SHAPES the object and edge so the
inference is possible — StorageObject carries uri + flat timestamps (CDN and
local both representable and time-comparable); `Relationships` holds a
confidence+evidence payload; the activity stream retains timestamped read-events
(already true). The **temporal-correlation inference engine itself** (scan
activity within δ, emit a `derived_from` edge with a confidence model + false-
positive handling) is its OWN pour, named and deferred. #17 must not FORECLOSE
the inference; it does not BUILD it. This edge is in the spec as the worked
example that justifies the object's shape (uri-as-spine, confidence edges,
honest-absence) — the role the three use-cases played in the Khipu spec.

## §5 — Testing

The three `#17` red-bar guards:

1. `test_uniform_storage_object_exists` → green as-is (module + class satisfy it).
2. `test_canonical_timestamps_are_uuid_named` → **rewritten** (§2): assert flat
   nullable `created/modified/accessed/changed`; assert NO `CANONICAL_TIMESTAMP_UUIDS`
   on the object (positive proof cross-silo naming did not creep back); cross-silo
   join tested at the Pukara boundary, not here. Same change, reasoning in commit.
3. `test_semantic_attribute_lane_is_open` → green. **Resolution of the two
   open-lane shapes:** a NAMED `semantic_attributes: dict[str,Any]` field is the
   designed, queryable bag the guard probes and the unstructured pipeline writes
   into; `extra="allow"` is the safety-net for unanticipated top-level fields.
   Both exist on purpose; the guard tests the named bag, the Task-6 red bar tests
   the `extra=allow` schema behavior.

**Pour A red bar (the separation):** a `contribute` write to an owned collection
that was not Khipu-bound must be impossible — assert Registrar no longer creates
`Objects`/`Relationships` schemaless, and that after Pour A the live `Objects`
collection carries the StorageObject schema (not `schema:none`). This guards the
schemaless-create path cannot return.

New tests (Codex-authored, builder/tester separation):
- `StorageObject` round-trips through `watay` into live `Objects`: strict spine
  validated, undeclared field accepted (open lane survives at the DB boundary).
- A poor object (uri + one timestamp, no st_ino) and a rich object (full POSIX in
  the lane) both validate — honest-absence (missing ≠ rejected).
- **Normalization:** a `FileEntryData` through the linux normalizer yields a
  StorageObject with top-level `modified` (not buried in `raw`); the temporal test
  migrates from `d.raw.timestamps.modified` to `d.modified` — that migration is the
  proof the spine landed (§3.5).
- **Idempotent re-observation:** normalizing the same `FileEntryData` twice yields
  the SAME `object_identifier` (deterministic `uuid5(source, uri)`, §3.7) — a rescan
  updates, does not duplicate, under the unique index.
- A `derived_from` edge (`relation_type`, confidence + evidence) writes into
  `Relationships` and traverses (edge shape real; inference engine deferred).
- `raw` blob round-trips beside the normalized view (save-it-all at storage).

All against live `apacheta_test` ([[feedback_no_mock_databases]]).

## The two pours (Reviewer #2 reshaped #17 from one object into an integration arc)

- **Pour A — complete the registration/collection separation** (§3 binding-gap):
  retire Registrar's owned-collection creation; route `Objects`/`Relationships`
  through `khipu.watay`. Own red-bar-guarded change, reviewed before B. This is
  the un-done Khipu migration the StorageObject surfaced — not new scope, owed work.
- **Pour B — StorageObject + normalization** (§1, §2, §3.5–3.7): the object, the
  `FileEntryData → StorageObject` normalizer, deterministic identity, three-identity
  model. Lands on the Khipu-bound `Objects` collection A produced; flips the three
  #17 guards green.

## Explicitly deferred (named, not dropped)

- The temporal-correlation **inference engine** (own pour).
- **Cloud/accidental collector normalization** (per-collector pours; Pour B builds
  the LINUX normalizer + the shared StorageObject; Dropbox uri-minting etc. follow).
  End-state is subsume-into-the-OPEN-object, replacing the closed silo models —
  `extra="forbid"` is the mistake (Tony, 2026-06-19).
- The static `_SEMANTIC_COLLECTIONS` **migration** (gh #1's closer, not this).
- gh #32 (view-link obfuscation gap).

## Open items still for review (after Reviewer #2 round 1)

Reviewer #2 verdict: directionally right; the gap was integration. All 7 findings
folded (§3 binding, §3.5 normalization, §3.6 identities, §3.7 identity rule, §4
`relation_type`, §2 timestamp-provenance, §1/§2 uri invariant). Remaining open:

- **StorageObject ↔ ContributedRecord relationship.** `ContributedRecord` carries
  `source` + `timestamp` + `raw` + an open tail — StorageObject re-declares all
  four. Should StorageObject EXTEND/compose ContributedRecord rather than duplicate?
  (The "re-deriving piecemeal what already exists" risk
  [[project_indaleko_db_collections_declarative_root]] — caught once as Record→source;
  this is the second instance.) Settle before building Pour B.
- Is the object genuinely shaped to PERMIT the Discord inference, or gesturing? (§4.)
- Named `semantic_attributes` bag vs `extra="allow"` — two open-lane shapes one too
  many? (§5 resolution — defensible, poke it.)
- The three-identity decision (§3.6: `source` = provider/observer) — confirm against
  how the activity stream and edges will consume it, not just storage.
- **Where do the derived-edge `confidence`/`evidence` live?** The live `ProvenanceEdge`
  (`provenance_edge.py:32`) is `extra="forbid"` with a typed `provenance: ProvenanceEnvelope`
  — it cannot carry ad-hoc confidence/evidence. Options: (a) fold them into
  `ProvenanceEnvelope` (smallest blast radius, if the envelope can hold them); (b) open
  `ProvenanceEdge`'s tail or add explicit fields (changes a live model existing edges use);
  (c) a distinct edge model — fights Khipu's one-schema-per-collection. This is the THIRD
  `extra="forbid"` friction in this spec (FileEntryData, the edge) — the inference-engine
  pour (which builds the edge) is the natural place to settle it, but the SHAPE decision
  affects the `Relationships` definition. Flag, do not silently pick.
