# Design: Activity Observation Reduction — the provider boundary as a banding witness

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
wrong. This doc reduces the persisted observation to a faithful band witness,
moves the firehose-taming reduction into the activity provider boundary
(collector + in-memory queue + recorder, whichever layer owns the live state),
and names — without building — the curation axes that will be needed later.

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

**Aggregation is not interpretation.** The provider boundary *may* hold live
state and collapse repeated activity on the same file into one band record (see
§4). That is intentionally lossy at sub-band resolution, but lossless with
respect to the question an episodic-memory-shaped record asks ("what happened to
this file in this band"). The witness stays illiterate about *meaning* while
becoming a stateful *aggregator*.

This is the edge where the simple rule "observe everything" needs precision, so
state it as two rules that never conflict:

- **Observation is total.** The source-facing collector observes the full stream
  available to it. This is never reduced, and it is what §6.1's learned sampling
  depends on (the probe is drawn from the full stream).
- **Persistence is band-resolution.** What crosses the durable `FactRecord`
  boundary is one band per (handle, principal), not sub-second/sub-minute churn.
  This is resolution reduction, not relevance filtering.

The *one* place persistence drops something observation saw is the bounded
intra-band create/delete elision (§4) — an exception to **persistence**, not to
**observation**. Relevance policy still lives downstream (§6); it is neither of
these two rules.

## 2. The reduced observation (banded)

An observation is not a point event. It is a **band**: "this file had the
following kinds of things done to it during this time band." This is the unit a
memory owner can actually recall.

```python
class StorageAccessKind(IntFlag):
    CREATE = 1 << 0
    READ = 1 << 1
    WRITE = 1 << 2
    RENAME = 1 << 3
    DELETE = 1 << 4


class StorageActivityBand(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow", validate_default=True)

    # --- required: the witness floor ---
    location: str                 # collector-minted URI. scheme = namespace,
                                  # authority = frame-of-reference. OPAQUE to the
                                  # base framework; the base NEVER parses it.
    access_kinds: int             # serialized StorageAccessKind bitmask,
                                  # OR'd across the band. COUNTS DISCARDED.
    band_start: datetime          # first access in the band
    band_end: datetime            # last access (quiescence measured from here)
    granularity: str = "band"     # seam for future temporal coarsening
    compaction_level: int = 0      # 0 = provider-emitted band

    # --- optional: opaque evidence, never required for correctness ---
    source_sequence: str | None = None   # source's own ordering token, opaque
    os_principal: str | None = None       # opaque OS principal MENTION (uid/SID/…)
                                          # → resolved by NER, not here
    process_id: int | None = None         # OS-local, non-identity syscall evidence
    process_name: str | None = None
```

**Serialized into `FactRecord.data`** (unchanged from 07-04 §3.1: the store row is
open, the store does not understand the payload).

`access_kinds` is stored as an integer for backend portability, but code should
treat it as a `StorageAccessKind` mask and reject bits outside the declared
mask. That keeps the persisted shape simple without making tests reason about
magic integers.

### 2.1 Query markers are secondary, not invisible

`FactRecord.provider_id` and `FactRecord.timestamp` remain the primary temporal
query surface, but storage activity cannot become time-only. The first provider
descriptor must declare a query-marker projection for the fields expected to
drive recall, curation, or reindexing:

- required marker: `location`
- common secondary markers: `access_kinds`, `os_principal`, `process_name`
- temporal markers: `band_start`, `band_end`, `granularity`, `compaction_level`

The base framework still does not parse `location`, but the value must be
queryable as a whole string. Implementations may satisfy this with backend
JSON-path indexes over `FactRecord.data` or with a separate projection table /
collection. The design requirement is visibility of the markers, not a specific
storage mechanism.

### 2.2 What was removed from the 07-04 observation model, and why

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

## 4. The provider boundary is a live banding aggregator (firehose defense)

A modest local filesystem does hundreds of file operations per second and almost
none of them matter. Hundreds of ops/sec must **not** become hundreds of
facts/sec in the stream. The firehose is tamed **at birth, inside the activity
data stream provider boundary**, not after raw facts have already been persisted.
For an implementation this may live in the collector, in an in-memory queue
consumer, or in the fact recorder; those are equivalent if the raw source stream
does not cross the durable `FactRecord` boundary first.

**This aggregator is a new stateful stage — it does not exist yet.** Verified
against the code (2026-07-06): `FactRecorderBase.record_facts(envelope) -> int`
is stateless, one-shot, batch — it holds no cross-call state, and the existing
`FsEventFactRecorder` docstring is literally "stores one fact per change event,"
i.e. the firehose this spec supersedes. So the pour introduces a component none
of the three named layers currently provides: a live accumulator keyed by
`(handle, principal)` that persists band records on quiescence/close. Do not plan
this as "edit the recorder"; plan it as a new banding stage the recorder (or a
queue consumer) hosts.

**On mtime-scan, the aggregator is batch-fed, not event-fed.** The one real,
ground-truth source (`FsIncrementalCollector`) emits `FsEventBatch` per scan run,
not a live event stream. So "live state across events" here means **state across
scan runs**: the aggregator accumulates across successive batches and closes a
band on quiescence measured in *scan cadence*. There is no `close` causal
boundary on mtime-scan (`boundary_capability = quiescence_only`, §5). The
real-time causal path (fanotify/fs_usage) is the case the `(proc, fd)`-keyed
accumulator model was built for; the mtime-scan adapter exercises the same
aggregator through a batch feed, which is enough to falsify the design (§8)
without any live OS API.

Live state, keyed by **(stable handle, principal)**, one accumulator entry per
active file *per actor*:

```
entry (key = (stable_handle, os_principal)):
    location       # collector-minted URI
    access_kinds   # bitmask, OR'd as events arrive; counts discarded
    band_start     # first access
    band_end       # advanced on each touch
    os_principal   # part of the key — each band is single-actor by construction

emit-and-evict when:
    causal boundary (e.g. close) if the source provides one   [exact]
    OR quiescence timeout (band-length, ~5–60 min)            [fallback]

elide before durable emission when:
    access_kinds == {create, delete} within one band
    # a temp file's whole life fit in one band — ~55% of files are deleted
    # within 30s of creation (Vogels, NT4). That churn is the firehose's bulk
    # and is noise at the episodic level.
```

This elision is the explicit edge-case exception to the "observe everything"
rule: the provider observed the lifecycle, but does not persist a band for an
object whose whole life was intra-band create/delete churn. That exception is
allowed only because the product is an episodic band stream. It is not permission
to add collector-side relevance policy such as "ignore `/tmp`."

**Key on the stable handle, not the mutable coordinate.** Indaleko's `fileaudit`
`LogCompactor` keys by `(procname-pid, fd)` — an fd survives a rename where a path
does not, so a single file's activity stays coherent *through* a rename. Keying by
path would fracture it. mtime-scan has no fd; its handle is the path, and its
bands are correspondingly weak (see §5). Prior art:
`../indaleko/fileaudit/logcompator.py` (misspelled by its author; the technique is
sound).

**Principal is part of the key — bands are single-actor by construction.** When
two principals touch the same file in one window, they produce two bands, not one
band with a set of actors. This is not fussiness: the band already collapses the
verb sequence into an OR'd `access_kinds` mask, and that collapse is truthful
*only while the band is single-actor*. Put two principals on one shared mask and
you lose which one held the `write` bit — the mask says "someone wrote, someone
read" and cannot say who did which. That is the smeared-actor failure the whole
reduction fights, reappearing one level up. Multi-writer is rare, so
principal-in-the-key costs an extra band only in the rare case and buys back
writer attribution in every case. (Where the source cannot attribute a principal
at all — mtime-scan — `os_principal` is `None`, the key's principal slot is null,
and the band is honestly single-"unknown-actor"; the anchor layer resolves who
later, per §5.)

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
*Seam:* `location` is a first-class query marker, so a future curator can filter
by URI prefix with no schema change once the implementation provides the marker
projection/index named in §2.1.

> **The provider never filters by relevance.** Relevance is a learned,
> retrospective, **recorder-side** decision. Filtering by relevance at the source
> collector is forbidden because it destroys the evidence that would later justify
> the filter.
> The `/tmp`-is-noise intuition is probably *correct* — and it still must not live
> at the collector, because being right is not the test; being revisable-with-
> evidence is. Source observation is total at the collector; relevance policy
> lives at the recorder/curator.

Both `granularity`/`compaction_level` (temporal) and queryable markers such as
`location` (spatial) are the seams. Both curators are deferred with named owners
so a successor points the future work at the **recorder/curator**, not the source
collector, and does not build a parallel tree.

### 6.1 What curation actually is: learned sampling with a probe

The two axes above are not two mechanisms. They are one — **learned per-pattern
sampling with a mandatory probe channel** — applied to different keys (time,
location; and on other streams, query shape).

The initial rule is *save everything*. This is **instrumental, not permanent**:
you save everything so you can learn what does not matter. It is the training-data
phase, and it has a per-pattern exit condition. Once a pattern is characterized —
"we've seen this before, it never participates in a recalled band" — retention
stops keeping full detail *for that pattern* and drops to sampling: keep 1-in-N,
not all.

The **probe** is load-bearing and non-negotiable. A blind filter cannot discover
it is wrong — it stops looking, so it never sees the day the pattern changed.
Sampling always keeps a probe: a trickle of full-detail retention held
specifically to catch when a "known-boring" pattern starts mattering. Sampling
without a probe is amnesia; sampling with a probe is curation.

This is why **source-side observation stays total even in the mature system**.
The sampling lives at the recorder/curator; the probe *requires* the collector to
keep observing everything, because the probe is drawn from the full stream before
learned relevance policy is applied. The collector's never-filter-by-relevance
rule is therefore not a temporary scaffold that learned curation eventually
removes — learned curation *depends* on it.

This is the same shape as the effective-action-space result elsewhere in the
project: save-everything is high recall / low precision (the 973,421-results law
at the storage layer); sampling-with-probe is the precision mechanism, spending a
bounded retention budget on what is informative while holding a cheap probe
against being wrong. File-activity banding, relevance filtering, and query
sampling are three instances of the one policy on three streams.

## 7. Scope of this pour

**Builds:**

1. `StorageActivityBand` model (§2), serialized into `FactRecord.data`.
2. The live banding aggregator (§4): stable-handle keying, `StorageAccessKind`
   bitmask kinds,
   causal-or-quiescence emit, create-delete-in-band elision.
3. An adapter driving the aggregator from the existing real `FsIncrementalCollector`
   / `FsChangeEvent` mtime-scan output (weak `path:` URIs).
4. A descriptor carrying source-kind / identity-strength / ordering-strength /
   boundary-capability (§5) and query-marker projection fields (§2.1).
   **DEFERRED (conscious decision, 2026-07-06):** the descriptor's fields are all
   metadata a *consumer* reads to decide how much to trust a provider, and no
   such consumer exists yet. Building it now is a struct with no reader — the
   speculative-flexibility anti-pattern §5 itself warns against ("a dedicated
   registry should be added only if core registration proves too coarse"). The
   descriptor lands with its first consumer (the query/curation layer), not
   before. The first mtime-scan pour ships items 1–3 only; identity/ordering
   strength are documented per-source here (§5) until a reader needs them typed.

**Does NOT build:** any curator — temporal or relevance (§6). Only the seams.

**Does NOT require:** any OS event API (fanotify/inotify/NTFS-USN), a Windows
machine, or synthetic high-fidelity sources. The real mtime-scan collector on this
repo is sufficient ground truth for the falsification test.

## 8. Falsification target

The load-bearing claim, made testable **today** against the real mtime-scan
collector on this actual repo (ground truth, no synthetics grading my own
imagination):

1. **Firehose tamed at birth.** facts-out ≪ events-in; the band-emitter produces
   file-bands, not per-event facts. Count and show the reduction is real. This is
   where real-time activity providers have the largest advantage over scan-diff
   sources: they can see high-frequency churn and reduce it before durable
   emission.
2. **Temp-file elision for observable lifecycles.** A file whose create and
   delete are both observed within one band produces **no** emitted fact.
   Mtime-scan cannot observe files that are created and deleted entirely between
   scans; real-time providers can. The mtime-scan adapter can still test the
   aggregator behavior with observable create/delete pairs.
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
- **No collector-side relevance filtering or sampling, ever** — the collector
  observes totally so the recorder's future sampling can keep an honest probe
  (§6.1). Provider-side banding and intra-band create/delete elision are the
  named firehose-resolution exception, not a learned relevance policy.
- **Recorder-side learned sampling is deferred, not forbidden** — its mature form
  is per-pattern sampling with a mandatory probe channel; "save everything" is the
  instrumental training phase, not a permanent state (§6.1).
- **No per-file operation counts** (`{read: 400}` ≡ `{read: 1}`) — band-granularity
  is the target, and per-file intensity is below the resolution that does the work
  (§4). *Band-coarseness* signals that aid band-finding — e.g. count of distinct
  files touched in a window — are not forbidden; they are a future signal, not
  built in this pour.
```
