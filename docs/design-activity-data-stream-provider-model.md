# Design: Activity Data Stream Provider Model

**Status:** design proposal, not yet implemented
**Author:** Yanantin AI, 2026-07-04, with Tony
**Scope:** activity data stream providers, storage activity observations, episodic filesystem activity, synthetic twins, and advisory reindex suggestions.
**Read before implementation:** this document intentionally starts from the filesystem activity case, then generalizes only the pieces that need to be common across providers.

---

## 1. The one-sentence problem

Yanantin needs activity data providers that can ingest heterogeneous, source-specific activity metadata without pretending it is uniform, while still producing coherent, queryable, memory-shaped records that can support storage indexing, recall, and research datasets.

Storage activity is the grounding case. It looks uniform to a naive observer, but real providers disagree in exactly the places that matter:

- NTFS USN journal data can provide stable object identifiers, monotonic USN positions, curated change reasons, and journal-rotation semantics.
- macOS `fs_usage` or a filesystem filter can produce high-frequency syscall-like activity shaped by process, pid, file descriptor, and path, with far more noise.
- Linux fanotify, inotify, and mtime-diff scans each provide a different mix of event fidelity, ordering, object identity, and completeness.
- Cloud storage providers can provide provider object IDs, revision IDs, sharing state, sync state, trash/restore semantics, and sometimes no stable local path.

The model must preserve those differences. Flattening them into a closed "file event" schema would erase evidence quality and produce false confidence.

## 2. Core principles

1. **Open observation schemas are a correctness property.** Source observations should have required canonical fields, typed known optional fields, and `extra="allow"` for source-specific evidence. This is not an accident or an AI-coder shortcut; it reflects the domain.
2. **Closed models belong at structural boundaries.** Provider descriptors, cursors, windows, reindex requests, provenance links, and compaction records should be constrained because Yanantin owns those contracts.
3. **Raw activity is evidence, not memory.** High-frequency event streams are useful inputs, but the durable cognitive target is an episodic record at the coarseness a memory owner can later use.
4. **Normalization must be loss-aware.** A path-only mtime diff and an NTFS record with a file reference number are not the same kind of claim. The common model must encode fidelity, confidence, and evidence kind.
5. **Compaction is additive.** Older or coarser memory facts are derived from earlier observations or episodes. The activity stream remains append-only; corrections and summaries are new facts.
6. **Activity can advise storage indexing but must not become the storage index.** Activity observations can produce reindex suggestions. The storage collector/indexer must still verify and produce authoritative storage state.
7. **Every real collector should have a synthetic twin.** The synthetic twin emits shape-compatible data for tests, reproducible experiments, and publishable research datasets that preserve structure without exposing private activity.

## 3. Relation to existing code

Yanantin already has the basic pipeline pieces:

- `CollectorBase` gathers source data and exposes `collect()`, `get_provider_id()`, and `get_description()`.
- `WranglerEnvelope` moves collected data without transforming it.
- `FactRecorderBase` writes raw observations to `ActivityStreamStore`.
- `FactRecord` is intentionally open (`extra="allow"`) and append-only.
- `FsIncrementalCollector` and `FsEventFactRecorder` currently model Linux filesystem changes as one fact per detected event.

That existing path is useful as a low-level event source and diagnostic path. It is not sufficient as the durable memory shape, because one-fact-per-event preserves too much low-level churn and too little episodic meaning.

Indaleko provides useful prior art:

- Activity characteristics give a category vocabulary such as storage and file activity.
- NTFS USN collection shows a curated, cursorable source with strong object identity.
- The Mac fileaudit prototype shows collapse of noisy low-level records into compact process/path/fd activity records.
- Indaleko's storage schemas deliberately allow extra fields because storage metadata is inherently heterogeneous.

Yanantin should borrow the lessons, not copy the exact shapes.

## 3.1 Tiering decision: payload model, not a second store

`StorageActivityObservation` is not a replacement for `FactRecord` and does not introduce a second stored row type. It is a validated payload shape for `FactRecord.data`, and a read/derive-time projection over the existing append-only activity stream.

The storage tiering is:

```text
FactRecord(provider_id, timestamp, content_hash, data=<open observation payload>)
  -> validated StorageActivityObservation projection over fact.data
  -> derived FilesystemActivityEpisode fact
  -> later coarser FilesystemActivityEpisode facts
```

This keeps `ActivityStreamStore` schema-agnostic and append-only. The typed observation model gives collectors, recorders, compactors, and tests a shared contract for the known fields without requiring the store to understand storage activity.

This decision moves a real cost to the read side. The current `ActivityStreamStore` query surface indexes top-level `FactRecord` fields such as `provider_id` and `timestamp`; it does not query into `FactRecord.data`. Canonical observation fields that become query or faceting pivots, such as `path`, `object_ref`, `activity_type`, or `process_name`, will need either explicit backend JSON-path indexes or promotion into a queryable projection. The payload model keeps the store generic, but the first compactor/query slice must name which canonical fields are indexed or promoted before scale testing.

This also explains the intentional asymmetry:

- `FactRecord` is open because the store is generic.
- `StorageActivityObservation` is open because source evidence is heterogeneous.
- `ActivityDataStreamProvider`, reindex suggestions, compaction policies, and episodes are closed because they are Yanantin-owned structural contracts.

## 4. Provider descriptor

The provider descriptor should describe the activity source, its evidence quality, its collection modes, and its synthetic twin. It is metadata about a stream, not the stream itself.

Proposed model shape:

```python
class ActivityDataStreamProvider(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    provider_id: UUID
    provider_name: str
    provider_version: str
    description: str

    activity_characteristics: tuple[str, ...]
    source_kind: str
    observation_level: str
    emission_mode: str
    cursor_kind: str

    identity_strength: str
    ordering_strength: str
    completeness: str
    noise_profile: str

    output_schema: dict
    canonical_fields: tuple[str, ...]
    extra_field_policy: str

    real_collector: str
    synthetic_collector: str
    supports_targeted_collection: bool = False
```

Initial vocabulary should remain simple strings or literals rather than a large enum hierarchy. Some terms are likely to stabilize:

- `source_kind`: `ntfs_usn`, `fanotify`, `inotify`, `fs_usage`, `mtime_scan`, `dropbox`, `gdrive`, `synthetic`
- `observation_level`: `journal`, `kernel_event`, `syscall_trace`, `snapshot_delta`, `cloud_event`
- `emission_mode`: `snapshot`, `delta`, `event`, `episode`
- `cursor_kind`: `usn`, `wall_clock`, `state_snapshot`, `provider_cursor`, `none`
- `identity_strength`: `stable_object_id`, `provider_object_id`, `path_only`, `path_plus_process`
- `ordering_strength`: `monotonic_sequence`, `timestamp_ordered`, `scan_order`, `best_effort`
- `completeness`: `complete_since_cursor`, `best_effort`, `sampled`, `diff_only`
- `noise_profile`: `curated`, `high_frequency`, `coalesced`, `lossy`

These are not merely labels. They tell consumers how much to trust a provider when deriving episodes, making reindex suggestions, or publishing synthetic analog datasets.

## 5. Open observations with required canonical fields

Observation models should constrain the known shared surface while allowing source-specific metadata.

The rule:

- Required fields are fields every provider of this observation type must supply.
- Optional typed fields are canonical fields that are common but not universal.
- Extra fields are source-specific evidence. They stay open until repeated use justifies promotion.

Proposed storage activity observation:

```python
class StorageActivityObservation(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="allow",
        validate_default=True,
    )

    provider_id: UUID
    observed_at: datetime
    activity_type: str
    evidence_kind: str

    item_kind: str | None = None
    path: str | None = None
    previous_path: str | None = None
    object_ref: str | None = None
    previous_object_ref: str | None = None
    process_id: int | None = None
    process_name: str | None = None
    actor: str | None = None
    source_sequence: str | int | None = None
    source_cursor: str | None = None
    confidence: float = 1.0
```

This model is serialized into `FactRecord.data`. `FactRecord.id` is the observation identity; `FactRecord.provider_id` and `FactRecord.timestamp` remain the store's indexing surface. For storage activity facts, `FactRecord.timestamp` should match `observed_at`, and `FactRecord.content_hash` should be derived from the canonical JSON serialization of the validated observation payload.

Examples of source-specific extras:

- NTFS: `file_reference_number`, `parent_file_reference_number`, `usn`, `reason_flags`, `volume_name`, `journal_id`
- macOS syscall trace: `fd`, `syscall`, `errno`, `procname`, `pid`, `open_close_chain`
- Linux fanotify/inotify: `mask`, `cookie`, `watch_descriptor`, `mark_path`, `inode`
- Cloud storage: `revision_id`, `shared`, `web_url`, `sync_state`, `trash_state`, `provider_parent_id`

The compactor and core query path should depend only on required and known canonical fields. Source-specific extras may improve scoring or linking when present, but they must not be required for correctness.

### 5.1 Existing `FsChangeEvent`

The current Linux mtime-diff model, `FsChangeEvent`, is closed (`extra="forbid"`). That is correct for the source it models: a scan delta produces a path, event type, modified time, size, and detection time. There is no hidden NTFS USN, file descriptor, fanotify mask, or cloud revision to preserve.

That closed model should coexist with `StorageActivityObservation` as a source-specific collector output. The recorder or adapter that writes activity facts can project each `FsChangeEvent` into a `StorageActivityObservation` payload:

```text
FsChangeEvent / Ntfs-like event / fs_usage compact record
  -> StorageActivityObservation
  -> FactRecord.data
```

When a second filesystem activity source lands, it should not be forced into `FsChangeEvent`. It should get its own source-shaped collector model and converge only at the observation payload boundary.

## 6. Episodic filesystem activity

The long-term activity stream should not primarily remember every low-level filesystem event. It should remember episodes: bounded windows of meaningful storage activity.

Today, a memory owner may recall roughly one-hour windows. Tomorrow, quarter-day windows may be enough. Next week, morning versus evening may be appropriate. A year later, week-scale recall may be the useful level.

Proposed derived model:

```python
class FilesystemActivityEpisode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    id: UUID
    provider_id: UUID
    memory_owner_id: UUID | None = None

    window_start: datetime
    window_end: datetime
    granularity: str
    compaction_level: int = 0

    source_kinds: tuple[str, ...]
    observation_count: int
    operation_counts: dict[str, int]
    changed_roots: tuple[str, ...]
    representative_paths: tuple[str, ...]
    dominant_processes: tuple[str, ...] = ()
    intensity: float
    evidence_quality: str

    derived_from: tuple[UUID, ...]
    summary: str = ""
```

An episode can be created from NTFS-like curated events, Mac/fanotify-like noisy events, or mtime-scan deltas. The output should be comparable even when the evidence strength differs.

The episode model is stricter than the observation model because it is Yanantin-owned interpretation, not source-specific evidence.

Episode identity should be content-derived, not random. A first implementation should derive `id` from at least `(provider_id, memory_owner_id, window_start, window_end, granularity, compaction_level)` using `uuid5` or an equivalent deterministic key. Re-running the same compaction should produce the same episode identity and content hash. Re-coarsening produces a new identity because the granularity/window changes.

### 6.1 Episode boundary policy

The first implementation should support policy-driven boundaries with a simple default:

- **Time-window boundary:** bucket observations into fixed windows such as one hour. This is the first source-agnostic baseline.
- **Quiet-gap boundary:** within a time window, optionally split bursts separated by a configured inactive gap.
- **Causal boundary:** when the source provides causal structure, such as the Mac fileaudit prototype's `(procname-pid, fd)` open/read/write/close chain, the compactor may use that structure to avoid splitting coherent activity.

The boundary rule belongs in compaction policy, not in the observation model. The first implementation can start with fixed time windows and tests should name that choice explicitly. The design should leave room for quiet-gap and causal policies because they better match how a memory owner recalls "a session" rather than a clock bucket.

## 7. Granularity and memory-owner policy

Episodic compaction should be controlled by a memory-owner policy. The same source activity may be remembered differently for a human, an AI instance, or a shared workspace.

Proposed policy shape:

```python
class EpisodicGranularityPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    owner_id: UUID
    policy_name: str
    rules: tuple[GranularityRule, ...]


class GranularityRule(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    after_age: timedelta
    granularity: str
    max_representative_paths: int
    retain_raw_observation_refs: bool = True
```

Example rule sequence:

- Current day: hour windows
- Next day: quarter-day windows
- Next week: daypart windows such as morning, afternoon, evening
- Later: day or week windows

This policy should not require deletion of raw observations. Retention is a separate storage policy. Compaction creates derived facts and may later support pruning or cold-tier movement, but it should not mutate the activity stream.

The first trigger can be an explicit maintenance command or scheduled job. Query-time lazy compaction is attractive later, but it makes correctness harder to reason about because reads would create new facts. The initial implementation should keep compaction as an explicit write-side maintenance operation.

## 8. Reindex suggestion loop

Storage activity can help keep the storage index fresh, but it should be advisory.

The loop:

```text
activity provider observes change
  -> records FactRecord carrying StorageActivityObservation payload
  -> derives StorageReindexSuggestion
  -> wrangler delivers targeted collection request
  -> storage collector gathers authoritative data for path/object/root
  -> storage recorder updates authoritative storage index
```

Proposed suggestion model:

```python
class StorageReindexSuggestion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    id: UUID
    provider_id: UUID
    observed_at: datetime
    target_kind: Literal["path", "object_ref", "root", "collection"]
    target: str
    reason: str
    priority: int = 0
    confidence: float = 1.0
    source_observation_id: UUID | None = None
    source_cursor: str | None = None
```

`source_observation_id`, when present, refers to the enclosing `FactRecord.id` for the storage activity observation.

Important rules:

- A suggestion can trigger collection, but it cannot mutate the authoritative storage object index.
- Delete, rename, and move suggestions must be verified by the collector or handled through explicit tombstone logic.
- Low-fidelity sources may suggest roots or paths. High-fidelity sources may suggest exact object references.
- Suggestions must be idempotent and coalescible.
- The storage indexer can record whether a suggestion was useful, stale, redundant, or wrong. That feedback can later improve provider scoring and compaction.

Targeted collection should be a normal collector operation, not a second indexing path. A reindex request can be pushed to the relevant collector through a wrangler connector; the collector then emits the same shaped data it would emit during normal collection, scoped to the requested target.

Suggestion identity should also be deterministic. A useful starting key is `(provider_id, target_kind, target, reason, source_cursor or source_observation_id)`, with time-window coalescing if a source emits frequent repeats. A random `uuid4` would make de-duplication and replay harder.

Reindex suggestions should be both recorded and acted on when the action path is enabled: the fact is the audit trail; the wrangler-delivered request is the operational signal.

## 9. Synthetic twin requirement

Every real provider should have a synthetic twin that emits shape-compatible data.

The synthetic collector is not just a random-data generator. It should preserve the structural challenges of the real source:

- bursty and quiet periods
- redundant events
- missing fields
- source-specific extras
- stable-object-id and path-only cases
- rename pairs and delete cases
- noisy process activity
- different fidelity and confidence levels
- realistic timing and coarsening behavior

Proposed model:

```python
class ProviderTwinSpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)

    real_collector: str
    synthetic_collector: str
    output_schema: dict
    synthetic_fidelity_targets: dict
    privacy_boundary: str
```

Synthetic twins support three separate uses:

1. **Unit and integration tests.** The compactor and reindex loop can be tested without live filesystem hooks or cloud credentials.
2. **Cross-source algorithm work.** NTFS-like, fanotify-like, fs_usage-like, and mtime-scan-like streams can all feed the same episode model.
3. **Publishable research datasets.** Yanantin can publish synthetic data that is consistent in shape with private real data while not exposing paths, names, object IDs, timestamps, or content.

A research export should declare:

```text
Generated by synthetic twin of provider X
Shape-compatible with schema version Y
Distribution fitted from private corpus Z
Contains no original paths, names, object IDs, or timestamps
Preserves burst/process/activity/timing characteristics within declared bounds
```

This is stronger and clearer than simple anonymization. The output is a structural analog, not sanitized real activity.

## 10. Filesystem case study

The first implementation should probably use filesystem activity because the repo already has a working collector/recorder path and because the source heterogeneity is visible.

Inputs to model:

- Existing `FsIncrementalCollector` mtime-diff output
- Synthetic NTFS-like curated observations
- Synthetic Mac/fanotify-like noisy high-frequency observations

First derived output:

- `FactRecord` entries carrying `StorageActivityObservation` payloads
- `FilesystemActivityEpisode` facts over one configurable window
- Optional `StorageReindexSuggestion` facts or wrangler-delivered requests

This gives a small testable slice without committing to live fanotify, inotify, or NTFS support yet.

## 11. Non-goals

- Do not build a general event-sourcing framework.
- Do not make raw event replay the primary goal.
- Do not close source observation schemas prematurely.
- Do not make the activity stream authoritative for storage object state.
- Do not require every source to provide stable object identity.
- Do not require live OS-specific event APIs in the first implementation slice.
- Do not make synthetic data a sanitized copy of real data.

## 12. Settled defaults and open questions

1. Provider descriptors should default to core registration records keyed by `provider_id`, with evidence-quality metadata queryable as provenance. A dedicated registry should be added only if core registration proves too coarse.
2. Should `StorageActivityObservation` live under `yanantin.activity`, `yanantin.collector.activity`, or a new shared activity data model package?
3. Reindex suggestions should be recorded as facts and, when enabled, delivered through a wrangler. The fact is audit/provenance; the wrangler message is action.
4. How long should raw observations be retained once episodes exist?
5. How should memory-owner granularity policies be represented for AI owners versus human owners?
6. What exact feedback should the storage indexer emit after consuming a reindex suggestion?
7. How much of Indaleko's activity characteristic UUID vocabulary should Yanantin preserve versus re-express in Yanantin-native terms?

## 13. Suggested first implementation boundary

Keep the first boundary deliberately small:

0. Implement `StorageActivityObservation` as a validated `FactRecord.data` payload, not as a new store type.
1. Add `StorageActivityObservation` and `FilesystemActivityEpisode` models with deterministic identity rules.
2. Add an adapter from existing `FsChangeEvent` to `StorageActivityObservation`.
3. Choose the first query/facet projection fields for storage activity. A conservative starting set is `activity_type`, `path`, `object_ref`, and `process_name`, with explicit tests documenting whether they remain JSON-path indexed payload fields or are promoted to a separate queryable projection.
4. Add a deterministic fixed-window compactor that consumes validated observations and emits one or more episodes for a configured window.
5. Add a synthetic filesystem activity observation generator with profiles for `ntfs_usn`, `fs_usage`, and `mtime_scan`.
6. Add tests showing that different source shapes produce comparable fixed-window episodes while preserving evidence quality.
7. Add `StorageReindexSuggestion` only after the observation -> episode path is green, unless targeted reindexing becomes the immediate driver.

This boundary tests the hardest conceptual question first: whether heterogeneous source activity can converge into useful episodic memory without erasing source fidelity.

Before implementing quiet-gap or causal episode boundaries, add tests that make the boundary choice visible. The Mac fileaudit `LogCompactor` is the concrete prior art for causal boundaries: it keys state by process/pid plus file descriptor and closes compact records on `close`.
