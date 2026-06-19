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
    source: UUID            # provenance: the registered provider/recorder id (resolves via Pukara).
                            #   NOT a ported Indaleko `Record` object — yanantin already carries
                            #   provenance as `source: UUID` on core/contribution.py:ContributedRecord
                            #   (source + timestamp + raw). See open items: StorageObject's relationship
                            #   to ContributedRecord is itself a review question.

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
- **Per-timestamp provenance — DELETED.** Indaleko's `IndalekoTimestampDataModel`
  could record which silo attribute filled each timestamp. Yanantin captured the
  *collector identity* (on `record`), so "where did this timestamp come from" is
  answerable from the Record. Storing it per-timestamp duplicates what we have.
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
"Objects" -> CollectionDefinition(
    schema=arangodb_schema(StorageObject),   # strict spine; open lane survives (extra=allow ⇒ no additionalProperties:false)
    indices=(
        {"type":"persistent","fields":["object_identifier"],"unique":True,"name":"obj_id_idx"},
        {"type":"persistent","fields":["uri"],"name":"uri_idx"},
        {"type":"persistent","fields":["modified"],"name":"modified_idx"},  # temporal axis, flat ⇒ indexable directly
    ),
)
```

The storage recorder already declares it writes well-known `Objects`
(`STORAGE_OBJECTS="Objects"`, live in the registration leaf); #17 supplies the
DEFINITION `watay` consumes. The Task-6 open-lane red bar guards that
`extra="allow"` does not emit `additionalProperties:false`, so the strict spine
validates AND the lane stays open at the DB boundary.

**Pukara owns** what the object stays naive about: the obfuscator (names through
it — C0, already in the `watay` path), the cross-silo joining (§2), the
principal→DB map. The object cannot leak silo-identity logic into itself because
that logic lives across the boundary. A reviewer checking "did cross-silo naming
creep back in?" looks only at the object's fields: all plain values + open lane ⇒
the boundary held.

Schema is an enforcement FLOOR (spine must conform), not a closed contract
(extras flow). Per Khipu's init contract, schema applies only at creation, never
reconciled; a spine change is a MIGRATION (gh-tracked), not an init edit.

## §4 — The derived-object edge (the worked example that validates the shape)

A Discord attachment is a thin, poor, DERIVED object: a CDN url, EXIF stripped
(anti-stalking), possibly re-encoded — **not the same bytes** as its local
source. Yanantin holds both the rich local `StorageObject` and the poor CDN one.
The value is not merging them (different objects) but an EDGE asserting "this
poor object was, with high probability, derived from that rich one."

```python
# written into the well-known "Relationships" edge collection
# (the storage recorder ALREADY declares STORAGE_RELATIONSHIPS="Relationships")
DerivedFromEdge:
    _from: <CDN StorageObject>      # poor/derived
    _to:   <local StorageObject>    # rich/source
    relation: "derived_from"
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

New tests (Codex-authored, builder/tester separation):
- `StorageObject` round-trips through `watay` into live `Objects`: strict spine
  validated, undeclared field accepted (open lane survives at the DB boundary).
- A poor object (uri + one timestamp, no st_ino) and a rich object (full POSIX in
  the lane) both validate — honest-absence (missing ≠ rejected).
- A `derived_from` edge (confidence + evidence) writes into `Relationships` and
  traverses (edge shape real; inference engine deferred).
- `raw` blob round-trips beside the normalized view (save-it-all at storage).

All against live `apacheta_test` ([[feedback_no_mock_databases]]).

## Explicitly deferred (named, not dropped)

- The temporal-correlation **inference engine** (own pour).
- **Collector normalization** into StorageObject (per-collector pours; the
  end-state is subsume-into-the-OPEN-object, replacing the closed silo models —
  `extra="forbid"` is the mistake, Tony 2026-06-19).
- The static `_SEMANTIC_COLLECTIONS` **migration** (gh #1's closer, not this).
- gh #32 (view-link obfuscation gap).

## Open items for adversarial review

- Is the object genuinely shaped to PERMIT the Discord inference, or merely
  gesturing at it? (§4 — the claim a skeptic should test hardest.)
- Named `semantic_attributes` bag vs `extra="allow"` — are two open-lane shapes
  one too many? (§5 resolution — defensible, but a reviewer should poke it.)
- **Provenance shape — RESOLVED against live code, but a design question remains.**
  There is NO `Record` class in yanantin (Indaleko's `IndalekoRecordDataModel` did
  not port). Provenance lives as `source: UUID` on `core/contribution.py:ContributedRecord`
  (which carries `source` + `timestamp` + `raw` — the spine StorageObject was reaching
  for). So the spec uses `source: UUID`, not a ported Record. **The open question for
  review:** is StorageObject a *kind of* `ContributedRecord` (it already has source +
  timestamp + raw + an open tail), and should it EXTEND/compose that rather than
  re-declare those fields? This is the "re-deriving piecemeal what already exists"
  risk ([[project_indaleko_db_collections_declarative_root]]) — caught once here
  (Record→source); the ContributedRecord relationship is the second instance and
  should be settled before building.
