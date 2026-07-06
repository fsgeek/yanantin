# Design: Activity Observation Reduction — the collector as a banding witness

**Status:** design proposal, not yet implemented
**Author:** Yanantin AI, 2026-07-05, with Tony
**Supersedes:** the *observation model* (§5) and the two-stage compaction pipeline
(§3.1, §6, §7) of `docs/design-activity-data-stream-provider-model.md` (2026-07-04).
Last writer wins: where this doc and the 07-04 doc disagree, this doc is authoritative.
The 07-04 doc's other sections (principles §2, reindex loop §8, synthetic twin §9,
non-goals §11) survive unchanged.

---

## 0. Why this doc exists

The 07-04 doc is coherent. Going through it against the code and against Tony's
prior experience (Indaleko, ~28.5M-file personal corpus, Vogels' NT4 file-access
patterns, decades of cross-platform identity work) showed it was **over-built in
the observation model and under-decided about where compaction happens**, not
wrong. This doc reduces the observation to a faithful witness, moves the
firehose-taming compaction into the collector's live state, and names — without
building — the two curation axes that will be needed later.

The reductions were each driven by a concrete correction, recorded here so a
successor reads the *reasons*, not just the shapes, and does not re-inflate the
model or build a parallel tree.

## 1. The one principle everything reduced to

The activity provider is a **faithful witness at one level**. It records the
source's own tokens verbatim as opaque values and interprets none of them.

Every act of *interpretation* lives downstream:

- what an OS principal **is** → the NER / identity layer
- whether two `location`s are the **same object** (mount moved, remounted
  elsewhere, removable device) → memory-anchor resolution
- whether a delete+create was a **rename** → not inferred at all on weak sources
- which paths are **worth keeping** (`/tmp`, `C:\Windows`) → recorder-side,
  learned, retrospective curation

The witness is illiterate on purpose. The moment a field's *type* encodes a
semantic (`uid: int` ⇒ POSIX), interpretation has leaked into the witness and the
projection→container collapse begins.

**Aggregation is not interpretation.** The collector *may* hold live state and
collapse repeated activity on the same file into one band record (see §4). That
is lossless with respect to the question an episode asks ("what happened to this
file in this band"); it discards only sub-band churn no consumer recalls. The
witness stays illiterate about *meaning* while becoming a stateful *aggregator*.

## 2. The reduced observation (banded)

An observation is not a point event. It is a **band**: "this file had the
following kinds of things done to it during this time band." This is the unit a
memory owner can actually recall.

```python
class StorageActivityBand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow", validate_default=True)

    # --- required: the witness floor ---
    location: str                 # collector-minted URI. scheme = namespace,
                                  # authority = frame-of-reference. OPAQUE to the
                                  # base framework; the base NEVER parses it.
    access_kinds: int             # bitmask over {create,read,write,rename,delete},
                                  # OR'd across the band. COUNTS DISCARDED.
    band_start: datetime          # first access in the band
    band_end: datetime            # last access (quiescence measured from here)

    # --- optional: opaque evidence, never required for correctness ---
    source_sequence: str | None = None   # source's own ordering token, opaque
    os_principal: str | None = None       # opaque OS principal MENTION (uid/SID/…)
                                          # → resolved by NER, not here
    process_id: int | None = None         # OS-local, non-identity syscall evidence
    process_name: str | None = None
```

**Serialized into `FactRecord.data`** (unchanged from 07-04 §3.1: the store row is
open, the store does not understand the payload).

### 2.1 What was removed from the 07-04 observation model, and why

| Removed / changed | Reason |
|---|---|
| `confidence: float` | A self-report vibe with no referent — every source says `1.0`. Replaced by `identity_strength` on the descriptor, which is a *structural, checkable* fact (does the source hand you a rename-stable id?). |
| `actor` | Smeared "resolved agent". The storage layer can't resolve an actor — 8 Hamut'ay instances all present as one uid. Became `os_principal`, an opaque *mention* for NER to resolve later. |
| `path`, `object_ref` as standalone identity | Neither is an identity. A path is relative to a mount; an inode is relative to a volume — both are **coordinates in a namespace whose origin is elsewhere**. A mounted volume can appear at a different path; the object is the same. Folded into one collector-minted `location` URI (§3). |
| single-verb `activity_type` | Became `access_kinds` bitmask — "the following things," plural, over a band. |
| point `observed_at` | Became `band_start`/`band_end` — an observation is an interval. |
| `item_kind` and other metadata | Storage metadata is fetchable from the file itself via the reindex loop. Activity says *"this changed, go look"*; the storage collector says *what it now is*. |

## 3. Identity is a collector-minted URI

Cross-platform location identity is a decades-hard problem (removable devices are
unsolvable; Windows volume UUIDs are persistent only under GPT — Indaleko's
Windows code carries that logic). The base framework must not bake in a wrong
abstraction. So it bakes in **none**: `location` is an opaque URI string minted by
the collector, which is **the only layer with enough information to mint it
credibly**.

```
scheme = namespace / identity strength;  authority = frame of reference
  vol-uuid:5f2c…/home/tony/foo     fs UUID (GPT/remount-stable)  → strong
  ntfs-vol:1A2B-3C4D/12345         volume serial + FRN           → strong
  gdrive:acct-…/file-…             cloud account + object id     → strong, no path
  path:/mnt/data/foo               no stable anchor (a stick)    → weak
```

The URI **scheme is the identity strength** — so `identity_strength` on the
descriptor and the scheme are one fact, stated once. The base framework never
parses the URI. NER/anchors resolve whether two URIs denote the same object.

This is *insufficient* (it does not solve removable-device identity — nothing
does) but not *overengineered* (one string), and above all it is **cheap to be
wrong**: a collector can change how it mints URIs without touching the observation
model or the store. When you know you will be wrong, buy revisability, not
correctness.

## 4. The collector is a live banding aggregator (firehose defense)

A modest local filesystem does hundreds of file operations per second and almost
none of them matter. Hundreds of ops/sec must **not** become hundreds of
facts/sec in the stream. The firehose is tamed **at birth, in the collector**, not
downstream.

Live state, keyed by a **stable handle**, one accumulator entry per active file:

```
entry:
    location       # collector-minted URI
    access_kinds   # bitmask, OR'd as events arrive; counts discarded
    band_start     # first access
    band_end       # advanced on each touch
    os_principal   # first-seen mention, if the source offers one

emit-and-evict when:
    causal boundary (e.g. close) if the source provides one   [exact]
    OR quiescence timeout (band-length, ~5–60 min)            [fallback]

elide UNEMITTED when:
    access_kinds == {create, delete} within one band
    # a temp file's whole life fit in one band — ~55% of files are deleted
    # within 30s of creation (Vogels, NT4). That churn is the firehose's bulk
    # and is noise at the episodic level.
```

**Key on the stable handle, not the mutable coordinate.** Indaleko's `fileaudit`
`LogCompactor` keys by `(procname-pid, fd)` — an fd survives a rename where a path
does not, so a single file's activity stays coherent *through* a rename. Keying by
path would fracture it. mtime-scan has no fd; its handle is the path, and its
bands are correspondingly weak (see §5). Prior art:
`../indaleko/fileaudit/logcompator.py` (misspelled by its author; the technique is
sound).

**Counts are discarded on purpose.** The goal is not to reconstruct the flow. It
is to find *temporal bands relative to episodic memory*. `{read: 400}` and
`{read: 1}` are the same band to a human or to Hamut'ay-Claude — neither helps
locate a memory. Per-file intensity is residue two-to-three orders of magnitude
finer than the resolution that does the real work: on Tony's ~28.5M-file corpus a
one-**month** window was a 99.9% search-space reduction. The coarse structure has
already won; the fine structure is below the noise floor.

## 5. Boundary policy and identity strength are source properties (descriptor)

Declared once, on the provider descriptor, not per event:

- `source_kind` — `mtime_scan`, `fanotify`, `ntfs_usn`, `fs_usage`, `gdrive`, `synthetic`, …
- `identity_strength` — implied by the URI scheme the collector mints
- `ordering_strength` — does the source hand you a monotonic sequence? (present ⇒ `source_sequence` is trustworthy)
- `boundary_capability` — `causal` (has close-like events) or `quiescence_only`

A weak-anchor source (mtime-scan mints `path:` URIs) **must not** have its bands
coalesced across the anchor, and rename is **not** inferred on it. A rename on a
path-only source looks like delete+create and the witness records exactly that —
inference is anchor-work, done later with more evidence, never guessed at the
witness.

## 6. Curation is deferred — TWO axes, neither built today

Curation will be needed. It is **not** needed today, and its policy will be shaped
by corpus data we do not yet have. Building it now would be overengineered *and*
insufficient. This pour builds no curator. It leaves seams.

**Axis 1 — temporal coarsening.** Aged bands coarsen: hour → daypart → day → week
as memory ages (07-04 §7). A year from now, single-day granularity is likely
enough. *Seam:* every band carries `granularity` and `compaction_level`. A future
curator reads bands and emits coarser bands. Not built.

**Axis 2 — relevance filtering.** Whole regions of the namespace may prove
uninteresting for episodic memory — nobody may care about `/tmp` or `C:\Windows`.
*Seam:* `location` is a first-class queryable field, so a future curator can
filter by URI prefix with no schema change.

> **The collector never filters by relevance.** Relevance is a learned,
> retrospective, **recorder-side** decision. Filtering at the collector is
> forbidden because it destroys the evidence that would later justify the filter.
> The `/tmp`-is-noise intuition is probably *correct* — and it still must not live
> at the collector, because being right is not the test; being revisable-with-
> evidence is. Observation is total at the collector; policy lives at the recorder.

Both `granularity`/`compaction_level` (temporal) and queryable `location`
(spatial) are the seams. Both curators are deferred with named owners so a
successor points the future work at the **recorder**, not the collector, and does
not build a parallel tree.

## 7. Scope of this pour

**Builds:**

1. `StorageActivityBand` model (§2), serialized into `FactRecord.data`.
2. The live banding aggregator (§4): stable-handle keying, bitmask kinds,
   causal-or-quiescence emit, create-delete-in-band elision.
3. An adapter driving the aggregator from the existing real `FsIncrementalCollector`
   / `FsChangeEvent` mtime-scan output (weak `path:` URIs).
4. A descriptor carrying source-kind / identity-strength / ordering-strength /
   boundary-capability (§5).

**Does NOT build:** any curator — temporal or relevance (§6). Only the seams.

**Does NOT require:** any OS event API (fanotify/inotify/NTFS-USN), a Windows
machine, or synthetic high-fidelity sources. The real mtime-scan collector on this
repo is sufficient ground truth for the falsification test.

## 8. Falsification target

The load-bearing claim, made testable **today** against the real mtime-scan
collector on this actual repo (ground truth, no synthetics grading my own
imagination):

1. **Firehose tamed at birth.** facts-out ≪ events-in; the band-emitter produces
   file-bands, not per-event facts. Count and show the reduction is real.
2. **Temp-file elision.** A file created and deleted within one band produces **no**
   emitted fact.
3. **Weak-anchor honesty.** mtime-scan bands are marked weak-identity and are **not**
   coalesced across `path:` URIs; rename is not inferred.

If the real, ground-truth source cannot satisfy these, the design is wrong and we
find it in a red test today — not in a parallel tree in three weeks.

## 9. Non-goals (inherited from 07-04 §11, plus)

- No general event-sourcing framework; raw-event replay is not a goal.
- The activity stream is not authoritative for storage object state.
- No source is required to provide stable object identity (weak `path:` is valid).
- No live OS-specific event APIs in this slice.
- **No curator (temporal or relevance) in this slice — seams only.**
- **No collector-side relevance filtering, ever.**
- **No per-file intensity/operation counts — band-granularity is the target.**
```
