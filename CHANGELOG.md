# Changelog

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
