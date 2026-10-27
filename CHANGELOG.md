# Changelog

## 0.3.0 — 2026-10-26

Additive in the supported core; two behaviour changes outside it. Stability tiers are
in [`docs/stability.md`](docs/stability.md).

### Supported core

- **`ActivityStreamStore.query_matching(provider_id, match)`** (new, concrete): facts
  whose data fields equal the given strings. The default filters `query_range`, so
  existing subclasses keep working. The memory backend filters before copying; DuckDB
  pushes the match into SQL. No removals or signature changes.

### Behaviour changes (Active tier)

- **Jabberwock:** an alias or membership given no gyre is unbounded, no longer
  "valid from when recorded" (#47). Records stored before keep their stored gyre.
- **`LinuxFilesystemCollector(since=...)`** keeps entries modified **or changed**
  (mtime or ctime) after the cutoff. mtime alone dropped files that arrive with old
  mtimes (`cp -p`, `tar x`, `rsync -t`, moves).

### Added

- **Jabberwock world time:** `galumph(..., at=)` and `uffish(..., at=)` say what held at
  a world time (#41). `import_record` backfills with the record's own id and time (#42).
  Resolution pushes its lookups to the store (#46): on levadura's crosswalk, 108 s
  became 22 s with identical answers.
- **The AQL gateway (`yanantin.core.aql`):** every AQL query runs through `run()`, which
  streams rows unchanged and reports each query's cost (rows, the server's scan and
  filter counts, time) to `observe()`d callbacks. Bind values are never recorded.
  `yanantin.query.recorder.AqlObservationRecorder` keeps observations as facts. A red
  bar forbids executing AQL elsewhere.
- **Finding files by path (`yanantin.recorder.storage.objects_find`):** `find_objects`
  by exact path segment (".ssh" anywhere, not "ssh"), name and time window, across
  machines. Each hit names its machine. On 4.4M objects: 2.8 ms, where a scan took
  2,973 ms. `ensure_objects_find_view` builds the view and analyzer;
  `CollectionDefinition` gains `analyzers`, which Khipu creates before views.
- **Linux birth time:** the collector stats through glibc `statx` (ctypes), so
  `created` is filled where the filesystem keeps it. Python 3.14's `os.stat` has no
  `st_birthtime` on Linux. Walks cost about 18% more.
- **`yanantin.eval.finding_chains`:** the instrument behind
  `docs/finding-metrics-scorecard.md` (search abandonment and cost to find).

### Fixed

- `import yanantin.machine` failed with a circular import unless `yanantin.collector`
  was imported first.

## 0.2.0 — 2026-10-16

The first release since 0.1.2 (2026-05-16). Stability tiers are in
[`docs/stability.md`](docs/stability.md).

### Breaking

- **The old collector modules are gone.** `yanantin.collector.{base, checksum,
  models, synthetic, wranglers, machine_config}` and the `filesystem`, `dropbox`,
  `fs_events` and `openrouter` collector packages from 0.1.2 were replaced by a
  rebuilt collector/recorder tree (`yanantin.collector`, `yanantin.recorder`).
  `yanantin.collector` was marked *Active*, not supported core; the supported
  core is unchanged.
- `StorageObfuscator` and `TransparentObfuscator` moved to
  `yanantin.core.storage_obfuscator`. The old import path still works; it is a
  re-export.

### Supported core

No removals or signature changes in `yanantin.apacheta.models`,
`yanantin.apacheta.interface`, `yanantin.apacheta.backends.memory`,
`yanantin.activity.{models, store, backends.memory}` or
`yanantin.query.{models, engine}`.

### Added

- **`find()` on the ArangoDB backend is BM25 over a passage index**, replacing a
  substring scan. Records are indexed when written. On 101 real queries judged
  blind, it found something useful for 76% against 37%
  ([scorecard](docs/find-quality-scorecard.md)). Records written by older clients
  are indexed by `python -m yanantin.apacheta.passages sync`.
- **`yanantin.evidence`**: `evidence:` references in memory frontmatter (git
  commits and files, khipumaq episodes, other memories), with
  `python -m yanantin.evidence check | pin`. "Intact" means the evidence is
  unchanged, never that the memory is true.
- **A read-only database account**: `python -m yanantin.infra reader --grant <db>`
  writes `~/.yanantin/config/reader.ini` (no admin key) for consumers that only
  read or count.
- The six-factor shape (`yanantin.factors`), the intent resolver
  (`yanantin.resolver`), per-query facet discrimination (`yanantin.llika.facets`),
  claim re-grounding on recall (`yanantin.memory.regrounding`), and an
  obfuscating ArangoDB façade (`yanantin.core`). These are research-tier.
- Storage objects: a full-stat Linux collector and recorder, batch landing, and
  indexes on `modified` and `label`.

### Changed

- A fully specified database target (`get_database(host, db_name, username,
  password)`) no longer loads or creates yanantin's own config file.
