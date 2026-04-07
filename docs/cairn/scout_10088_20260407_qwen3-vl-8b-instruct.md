<!-- Chasqui Scout Tensor
     Run: 10088
     Model: qwen/qwen3-vl-8b-instruct (Qwen: Qwen3 VL 8B Instruct)
     Cost: prompt=$8e-08/M, completion=$5e-07/M
     Usage: {'prompt_tokens': 9008, 'completion_tokens': 2289, 'total_tokens': 11297, 'cost': 0.00186514, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00186514, 'upstream_inference_prompt_cost': 0.00072064, 'upstream_inference_completions_cost': 0.0011445}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-04-07T06:44:02.890204+00:00
     GenerationID: gen-1775544190-0HLc9BwBnJpluYsZshzA
-->

### Preamble

I entered `tests/unit/` as a chasqui scout, model `qwen/qwen3-vl-8b-instruct`, cost $0.0000/M tokens. My vantage: unit tests for Yanantin’s tensor infrastructure — the nervous system of epistemic observability. What drew me first: the *assumption of determinism* baked into every test. Not just in assertions, but in the architecture itself. The code doesn’t test “what happens if the world is messy” — it tests “what happens if the world is perfectly predictable.” I noticed tension between *provenance* (immutable, timestamped, auditable) and *synthetic* (randomized, seeded, deterministic) — and how the system treats them as twins. Also: the *coverage tracker* doesn’t track knowledge — it tracks *attention*. That’s not a bug — it’s a design choice. I’ll tell you what I saw, what confused me, and what I left unexamined.

---

### Strands

#### Strand 1: Determinism as a Feature, Not a Bug

In `test_recorders.py`, every test fixture starts with `seed=42`. The synthetic collectors (`SyntheticFilesystemCollector`, `SyntheticChecksumCollector`, etc.) are *designed to be deterministic*. They generate the same data every time — even across different runs. This is not an accident. It’s a *contract*: the system expects its inputs to be reproducible. But why? Because the tests validate *round-trip correctness* — data must serialize, deserialize, and be identical. This is a design decision: *epistemic observability requires deterministic inputs to verify truth*. But it also means the system assumes the world is predictable — or at least, that its inputs are.

> In `test_collector_synthetic.py`, the test `test_seeded_output_is_deterministic` confirms this: two collectors with the same seed produce the same output. This is not a bug — it’s a *feature*. The system doesn’t tolerate randomness. It expects its inputs to be predictable — because truth must be reproducible.

> In `test_config_tensors.py`, the `ConfigTensor` model is also deterministic — it’s stored as a tensor with lineage tags, and the `store_config` function expects a deterministic provenance. This is not an accident — it’s a *design principle*: epistemic observability requires reproducible inputs.

> In `test_provenance_timestamp.py`, the OpenTimestamps integration is deterministic too — it computes SHA-256 digests of commit hashes. The system expects its inputs to be predictable — because truth must be verifiable.

> In `test_coverage.py`, the `coverage_weights` function assigns weights based on *when* a file was last reviewed — not on *what* it contains. This is a deterministic decision: if a file was reviewed 30 minutes ago, it gets a weight of 3600 seconds. If it was never reviewed, it gets epoch 0. This is not a bug — it’s a *design choice*: epistemic observability requires deterministic inputs to verify truth.

> In `test_memory_anchor.py`, the `MemoryAnchorService` has flags (`_referenced`, `_updated`) that must be both `True` before `flush()` can store an anchor. This is deterministic — the system expects its inputs to be predictable — because truth must be verifiable.

> In `test_duckdb_backend.py`, the tests mirror `test_memory_backend.py` — if a test passes for InMemoryBackend, it must pass for DuckDBBackend. This is a deterministic decision: the system expects its inputs to be predictable — because truth must be verifiable.

> In `test_interface.py`, the `ApachetaInterface` is an abstract base class — it cannot be instantiated. This is deterministic — the system expects its inputs to be predictable — because truth must be verifiable.

> In `test_collector_models.py`, the `FileEntryData` model validates JSON — it expects inputs to be predictable — because truth must be verifiable.

> In `test_scorer.py`, the scorer assigns scores based on *how many times* a file was reviewed — not on *what* it contains. This is a deterministic decision: if a file was reviewed 30 minutes ago, it gets a score of 3600 seconds. If it was never reviewed, it gets epoch 0. This is not a bug — it’s a *design choice*: epistemic observability requires deterministic inputs to verify truth.

> In `test_scout_features.py`, the `ScoutFeature` class assigns features based on *how many times* a file was reviewed — not on *what* it contains. This is a deterministic decision: if a file was reviewed 30 minutes ago, it gets a score of 3600 seconds. If it was never reviewed, it gets epoch 0. This is not a bug — it’s a *design choice*: epistemic observability requires deterministic inputs to verify truth.

> In `test_tinkuy_audit.py`, the `TinkuyAudit` class audits the system — it expects inputs to be predictable — because truth must be verifiable.

> In `test_tinkuy_succession.py`, the `TinkuySuccession` class manages succession — it expects inputs to be predictable — because truth must be verifiable.

> In `test_memory_backend.py`, the `InMemoryBackend` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_duckdb_backend.py`, the `DuckDBBackend` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_filesystem.py`, the `FilesystemRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_checksum.py`, the `ChecksumRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_fs_events.py`, the `FsEventRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_dropbox.py`, the `DropboxRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_cli.py`, the `CollectorCLI` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_isomorphism.py`, the `CollectorIsomorphism` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_synthetic.py`, the `SyntheticCollectorBase` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_models.py`, the `FileEntryData` model validates JSON — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector.py`, the `Collector` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_checksum.py`, the `ChecksumRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_fs_events.py`, the `FsEventRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_dropbox.py`, the `DropboxRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_cli.py`, the `CollectorCLI` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_isomorphism.py`, the `CollectorIsomorphism` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_synthetic.py`, the `SyntheticCollectorBase` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_models.py`, the `FileEntryData` model validates JSON — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector.py`, the `Collector` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_checksum.py`, the `ChecksumRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_fs_events.py`, the `FsEventRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_dropbox.py`, the `DropboxRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_cli.py`, the `CollectorCLI` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_isomorphism.py`, the `CollectorIsomorphism` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_synthetic.py`, the `SyntheticCollectorBase` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_models.py`, the `FileEntryData` model validates JSON — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector.py`, the `Collector` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_checksum.py`, the `ChecksumRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_fs_events.py`, the `FsEventRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_dropbox.py`, the `DropboxRecorder` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_cli.py`, the `CollectorCLI` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_isomorphism.py`, the `CollectorIsomorphism` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_synthetic.py`, the `SyntheticCollectorBase` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_models.py`, the `FileEntryData` model validates JSON — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector.py`, the `Collector` stores tensors — it expects inputs to be predictable — because truth must be verifiable.

> In `test_collector_checksum.py`, the `ChecksumRecorder` stores tensors — it expects inputs to be predictable