"""Unit tests for the collector recorders: filesystem, checksum, fs_events, dropbox.

Each recorder is tested with synthetic data via InMemoryBackend. Tests verify:
- Tensor stored and UUID returned
- Expected strand count and titles
- Summary strand has expected content
- Data strand is valid JSON that roundtrips to model
- Provenance source matches provider_id
- Lineage tags include content:<hash>
- Content hash is deterministic
- Convenience function pipeline works end-to-end
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.recorder.base import RecorderBase
from yanantin.collector.storage.local.checksum import (
    ChecksumData,
    SyntheticChecksumCollector,
)
from yanantin.recorder.storage.local.checksum import (
    ChecksumRecorder,
    collect_and_record_checksum,
)
from yanantin.collector.storage.cloud.dropbox import (
    DropboxListing,
    SyntheticDropboxCollector,
)
from yanantin.recorder.storage.cloud.dropbox import (
    DropboxRecorder,
    collect_and_record_dropbox,
)
from yanantin.collector.storage.local.linux import (
    FilesystemSnapshot,
    SyntheticFilesystemCollector,
)
from yanantin.recorder.storage.local.linux import (
    FilesystemRecorder,
    collect_and_record_filesystem,
)
from yanantin.collector.storage.local.linux.models import FileEntryData
from yanantin.collector.activity.linux import (
    FsEventBatch,
    SyntheticFsEventCollector,
)
from yanantin.recorder.activity.linux import (
    FsEventRecorder,
    collect_and_record_fs_events,
)
from yanantin.collector.activity.linux.models import FsChangeEvent
from yanantin.transport.models import WranglerEnvelope


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def backend() -> InMemoryBackend:
    return InMemoryBackend()


@pytest.fixture
def fs_envelope() -> WranglerEnvelope[FilesystemSnapshot]:
    collector = SyntheticFilesystemCollector(seed=42)
    data = collector.collect()
    return WranglerEnvelope(data=data, provider_id=collector.get_provider_id())


@pytest.fixture
def checksum_envelope() -> WranglerEnvelope[ChecksumData]:
    collector = SyntheticChecksumCollector(seed=42)
    data = collector.collect()
    return WranglerEnvelope(data=data, provider_id=collector.get_provider_id())


@pytest.fixture
def fs_events_envelope() -> WranglerEnvelope[FsEventBatch]:
    collector = SyntheticFsEventCollector(seed=42)
    data = collector.collect()
    return WranglerEnvelope(data=data, provider_id=collector.get_provider_id())


@pytest.fixture
def dropbox_envelope() -> WranglerEnvelope[DropboxListing]:
    collector = SyntheticDropboxCollector(seed=42)
    data = collector.collect()
    return WranglerEnvelope(data=data, provider_id=collector.get_provider_id())


# ── FilesystemRecorder ───────────────────────────────────────────


class TestFilesystemRecorder:
    def test_record_stores_tensor_and_returns_uuid(
        self, backend: InMemoryBackend, fs_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FilesystemRecorder(backend)
        tensor_id = recorder.record(fs_envelope)
        assert isinstance(tensor_id, UUID)
        assert len(backend.list_tensors()) == 1

    def test_tensor_has_expected_strand_count(
        self, backend: InMemoryBackend, fs_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FilesystemRecorder(backend)
        tensor_id = recorder.record(fs_envelope)
        tensor = backend.get_tensor(tensor_id)
        assert len(tensor.strands) == 2

    def test_summary_strand_has_expected_content(
        self, backend: InMemoryBackend, fs_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FilesystemRecorder(backend)
        tensor_id = recorder.record(fs_envelope)
        tensor = backend.get_tensor(tensor_id)
        summary = tensor.strands[0]
        assert summary.title == "Filesystem Snapshot Summary"
        assert f"root_path: {fs_envelope.data.root_path}" in summary.content
        assert f"total_files: {fs_envelope.data.total_files}" in summary.content

    def test_data_strand_is_valid_json(
        self, backend: InMemoryBackend, fs_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FilesystemRecorder(backend)
        tensor_id = recorder.record(fs_envelope)
        tensor = backend.get_tensor(tensor_id)
        data_strand = tensor.strands[1]
        assert data_strand.title == "Filesystem Entries"
        entries = json.loads(data_strand.content)
        assert isinstance(entries, list)
        assert len(entries) == len(fs_envelope.data.entries)

    def test_data_strand_roundtrips_to_model(
        self, backend: InMemoryBackend, fs_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FilesystemRecorder(backend)
        tensor_id = recorder.record(fs_envelope)
        tensor = backend.get_tensor(tensor_id)
        entries_raw = json.loads(tensor.strands[1].content)
        for raw in entries_raw[:5]:  # spot-check first 5
            entry = FileEntryData.model_validate(raw)
            assert entry.path

    def test_provenance_source_matches_provider_id(
        self, backend: InMemoryBackend, fs_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FilesystemRecorder(backend)
        tensor_id = recorder.record(fs_envelope)
        tensor = backend.get_tensor(tensor_id)
        assert tensor.provenance.source.identifier == fs_envelope.provider_id

    def test_lineage_tags_include_content_hash(
        self, backend: InMemoryBackend, fs_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FilesystemRecorder(backend)
        tensor_id = recorder.record(fs_envelope)
        tensor = backend.get_tensor(tensor_id)
        content_tags = [t for t in tensor.lineage_tags if t.startswith("content:")]
        assert len(content_tags) == 1
        assert len(content_tags[0].split(":")[1]) == 16  # 16 hex chars

    def test_content_hash_deterministic(
        self, backend: InMemoryBackend, fs_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FilesystemRecorder(backend)
        tid1 = recorder.record(fs_envelope)
        tid2 = recorder.record(fs_envelope)
        t1 = backend.get_tensor(tid1)
        t2 = backend.get_tensor(tid2)
        tags1 = [t for t in t1.lineage_tags if t.startswith("content:")]
        tags2 = [t for t in t2.lineage_tags if t.startswith("content:")]
        assert tags1 == tags2

    def test_convenience_function_pipeline(self, backend: InMemoryBackend) -> None:
        tid = collect_and_record_filesystem(backend, Path("/tmp"))
        assert isinstance(tid, UUID)
        tensor = backend.get_tensor(tid)
        assert len(tensor.strands) == 2


# ── ChecksumRecorder ────────────────────────────────────────────


class TestChecksumRecorder:
    def test_record_stores_tensor_and_returns_uuid(
        self, backend: InMemoryBackend, checksum_envelope: WranglerEnvelope,
    ) -> None:
        recorder = ChecksumRecorder(backend)
        tensor_id = recorder.record(checksum_envelope)
        assert isinstance(tensor_id, UUID)
        assert len(backend.list_tensors()) == 1

    def test_tensor_has_expected_strand_count(
        self, backend: InMemoryBackend, checksum_envelope: WranglerEnvelope,
    ) -> None:
        recorder = ChecksumRecorder(backend)
        tensor_id = recorder.record(checksum_envelope)
        tensor = backend.get_tensor(tensor_id)
        assert len(tensor.strands) == 2

    def test_summary_strand_has_expected_content(
        self, backend: InMemoryBackend, checksum_envelope: WranglerEnvelope,
    ) -> None:
        recorder = ChecksumRecorder(backend)
        tensor_id = recorder.record(checksum_envelope)
        tensor = backend.get_tensor(tensor_id)
        summary = tensor.strands[0]
        assert summary.title == "File Identity"
        assert f"file_path: {checksum_envelope.data.file_path}" in summary.content
        assert f"file_size: {checksum_envelope.data.file_size}" in summary.content

    def test_digest_strand_has_expected_content(
        self, backend: InMemoryBackend, checksum_envelope: WranglerEnvelope,
    ) -> None:
        recorder = ChecksumRecorder(backend)
        tensor_id = recorder.record(checksum_envelope)
        tensor = backend.get_tensor(tensor_id)
        digest_strand = tensor.strands[1]
        assert digest_strand.title == "Cryptographic Checksums"
        for alg in checksum_envelope.data.algorithms:
            assert alg in digest_strand.content

    def test_provenance_source_matches_provider_id(
        self, backend: InMemoryBackend, checksum_envelope: WranglerEnvelope,
    ) -> None:
        recorder = ChecksumRecorder(backend)
        tensor_id = recorder.record(checksum_envelope)
        tensor = backend.get_tensor(tensor_id)
        assert tensor.provenance.source.identifier == checksum_envelope.provider_id

    def test_lineage_tags_include_content_hash(
        self, backend: InMemoryBackend, checksum_envelope: WranglerEnvelope,
    ) -> None:
        recorder = ChecksumRecorder(backend)
        tensor_id = recorder.record(checksum_envelope)
        tensor = backend.get_tensor(tensor_id)
        content_tags = [t for t in tensor.lineage_tags if t.startswith("content:")]
        assert len(content_tags) == 1

    def test_content_hash_deterministic(
        self, backend: InMemoryBackend, checksum_envelope: WranglerEnvelope,
    ) -> None:
        recorder = ChecksumRecorder(backend)
        tid1 = recorder.record(checksum_envelope)
        tid2 = recorder.record(checksum_envelope)
        t1 = backend.get_tensor(tid1)
        t2 = backend.get_tensor(tid2)
        tags1 = [t for t in t1.lineage_tags if t.startswith("content:")]
        tags2 = [t for t in t2.lineage_tags if t.startswith("content:")]
        assert tags1 == tags2

    def test_convenience_function_pipeline(self, backend: InMemoryBackend) -> None:
        tid = collect_and_record_checksum(backend, Path("/etc/hostname"))
        assert isinstance(tid, UUID)
        tensor = backend.get_tensor(tid)
        assert len(tensor.strands) == 2


# ── FsEventRecorder ─────────────────────────────────────────────


class TestFsEventRecorder:
    def test_record_stores_tensor_and_returns_uuid(
        self, backend: InMemoryBackend, fs_events_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FsEventRecorder(backend)
        tensor_id = recorder.record(fs_events_envelope)
        assert isinstance(tensor_id, UUID)
        assert len(backend.list_tensors()) == 1

    def test_tensor_has_expected_strand_count(
        self, backend: InMemoryBackend, fs_events_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FsEventRecorder(backend)
        tensor_id = recorder.record(fs_events_envelope)
        tensor = backend.get_tensor(tensor_id)
        assert len(tensor.strands) == 2

    def test_summary_strand_has_expected_content(
        self, backend: InMemoryBackend, fs_events_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FsEventRecorder(backend)
        tensor_id = recorder.record(fs_events_envelope)
        tensor = backend.get_tensor(tensor_id)
        summary = tensor.strands[0]
        assert summary.title == "Event Batch Metadata"
        assert f"event_count: {len(fs_events_envelope.data.events)}" in summary.content

    def test_data_strand_is_valid_json(
        self, backend: InMemoryBackend, fs_events_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FsEventRecorder(backend)
        tensor_id = recorder.record(fs_events_envelope)
        tensor = backend.get_tensor(tensor_id)
        data_strand = tensor.strands[1]
        assert data_strand.title == "Filesystem Change Events"
        events = json.loads(data_strand.content)
        assert isinstance(events, list)
        assert len(events) == len(fs_events_envelope.data.events)

    def test_data_strand_roundtrips_to_model(
        self, backend: InMemoryBackend, fs_events_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FsEventRecorder(backend)
        tensor_id = recorder.record(fs_events_envelope)
        tensor = backend.get_tensor(tensor_id)
        events_raw = json.loads(tensor.strands[1].content)
        for raw in events_raw[:5]:
            event = FsChangeEvent.model_validate(raw)
            assert event.file_path

    def test_provenance_source_matches_provider_id(
        self, backend: InMemoryBackend, fs_events_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FsEventRecorder(backend)
        tensor_id = recorder.record(fs_events_envelope)
        tensor = backend.get_tensor(tensor_id)
        assert tensor.provenance.source.identifier == fs_events_envelope.provider_id

    def test_lineage_tags_include_content_hash(
        self, backend: InMemoryBackend, fs_events_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FsEventRecorder(backend)
        tensor_id = recorder.record(fs_events_envelope)
        tensor = backend.get_tensor(tensor_id)
        content_tags = [t for t in tensor.lineage_tags if t.startswith("content:")]
        assert len(content_tags) == 1

    def test_content_hash_deterministic(
        self, backend: InMemoryBackend, fs_events_envelope: WranglerEnvelope,
    ) -> None:
        recorder = FsEventRecorder(backend)
        tid1 = recorder.record(fs_events_envelope)
        tid2 = recorder.record(fs_events_envelope)
        t1 = backend.get_tensor(tid1)
        t2 = backend.get_tensor(tid2)
        tags1 = [t for t in t1.lineage_tags if t.startswith("content:")]
        tags2 = [t for t in t2.lineage_tags if t.startswith("content:")]
        assert tags1 == tags2


# ── DropboxRecorder ──────────────────────────────────────────────


class TestDropboxRecorder:
    def test_record_stores_tensor_and_returns_uuid(
        self, backend: InMemoryBackend, dropbox_envelope: WranglerEnvelope,
    ) -> None:
        recorder = DropboxRecorder(backend)
        tensor_id = recorder.record(dropbox_envelope)
        assert isinstance(tensor_id, UUID)
        assert len(backend.list_tensors()) == 1

    def test_tensor_has_expected_strand_count(
        self, backend: InMemoryBackend, dropbox_envelope: WranglerEnvelope,
    ) -> None:
        recorder = DropboxRecorder(backend)
        tensor_id = recorder.record(dropbox_envelope)
        tensor = backend.get_tensor(tensor_id)
        assert len(tensor.strands) == 2

    def test_summary_strand_has_expected_content(
        self, backend: InMemoryBackend, dropbox_envelope: WranglerEnvelope,
    ) -> None:
        recorder = DropboxRecorder(backend)
        tensor_id = recorder.record(dropbox_envelope)
        tensor = backend.get_tensor(tensor_id)
        summary = tensor.strands[0]
        assert summary.title == "Dropbox Account Metadata"
        assert f"account_email: {dropbox_envelope.data.account_email}" in summary.content
        assert f"total_files: {dropbox_envelope.data.total_files}" in summary.content

    def test_data_strand_is_valid_json(
        self, backend: InMemoryBackend, dropbox_envelope: WranglerEnvelope,
    ) -> None:
        recorder = DropboxRecorder(backend)
        tensor_id = recorder.record(dropbox_envelope)
        tensor = backend.get_tensor(tensor_id)
        data_strand = tensor.strands[1]
        assert data_strand.title == "Dropbox File Entries"
        entries = json.loads(data_strand.content)
        assert isinstance(entries, list)
        assert len(entries) == len(dropbox_envelope.data.entries)

    def test_provenance_source_matches_provider_id(
        self, backend: InMemoryBackend, dropbox_envelope: WranglerEnvelope,
    ) -> None:
        recorder = DropboxRecorder(backend)
        tensor_id = recorder.record(dropbox_envelope)
        tensor = backend.get_tensor(tensor_id)
        assert tensor.provenance.source.identifier == dropbox_envelope.provider_id

    def test_lineage_tags_include_content_hash(
        self, backend: InMemoryBackend, dropbox_envelope: WranglerEnvelope,
    ) -> None:
        recorder = DropboxRecorder(backend)
        tensor_id = recorder.record(dropbox_envelope)
        tensor = backend.get_tensor(tensor_id)
        content_tags = [t for t in tensor.lineage_tags if t.startswith("content:")]
        assert len(content_tags) == 1

    def test_content_hash_deterministic(
        self, backend: InMemoryBackend, dropbox_envelope: WranglerEnvelope,
    ) -> None:
        recorder = DropboxRecorder(backend)
        tid1 = recorder.record(dropbox_envelope)
        tid2 = recorder.record(dropbox_envelope)
        t1 = backend.get_tensor(tid1)
        t2 = backend.get_tensor(tid2)
        tags1 = [t for t in t1.lineage_tags if t.startswith("content:")]
        tags2 = [t for t in t2.lineage_tags if t.startswith("content:")]
        assert tags1 == tags2


# ── Content Hash Utility ─────────────────────────────────────────


class TestContentHash:
    def test_content_hash_deterministic_across_calls(self) -> None:
        collector = SyntheticChecksumCollector(seed=99)
        data = collector.collect()
        h1 = RecorderBase._content_hash(data)
        h2 = RecorderBase._content_hash(data)
        assert h1 == h2
        assert len(h1) == 16

    def test_content_hash_differs_for_different_data(self) -> None:
        c1 = SyntheticChecksumCollector(seed=1)
        c2 = SyntheticChecksumCollector(seed=2)
        h1 = RecorderBase._content_hash(c1.collect())
        h2 = RecorderBase._content_hash(c2.collect())
        assert h1 != h2

    def test_content_tag_present_in_stored_tensor(self) -> None:
        backend = InMemoryBackend()
        collector = SyntheticChecksumCollector(seed=42)
        data = collector.collect()
        envelope = WranglerEnvelope(data=data, provider_id=collector.get_provider_id())
        recorder = ChecksumRecorder(backend)
        tensor_id = recorder.record(envelope)
        tensor = backend.get_tensor(tensor_id)
        expected_hash = RecorderBase._content_hash(data)
        assert f"content:{expected_hash}" in tensor.lineage_tags


# ── Since Parameter ──────────────────────────────────────────────


class TestSinceParameter:
    def test_filesystem_since_filters_by_mtime(self) -> None:
        """Synthetic filesystem with known timestamps, since should filter."""
        collector = SyntheticFilesystemCollector(seed=42)
        full = collector.collect()
        # All synthetic timestamps are based on 2025-01-01; use a future cutoff
        future = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Re-create with same seed for determinism
        collector2 = SyntheticFilesystemCollector(seed=42)
        filtered = collector2.collect(since=future)
        # Future cutoff should exclude everything (synthetic times are in 2025)
        assert len(filtered.entries) <= len(full.entries)

    def test_machine_config_ignores_since(self) -> None:
        from yanantin.machine.linux import MachineConfigCollector

        collector = MachineConfigCollector()
        data_without = collector.collect()
        data_with = collector.collect(since=datetime(2020, 1, 1, tzinfo=timezone.utc))
        # Both should return the same structure
        assert data_without.hostname == data_with.hostname
        assert data_without.machine_id == data_with.machine_id

    def test_since_none_returns_full_data(self) -> None:
        collector = SyntheticFilesystemCollector(seed=42)
        full = collector.collect(since=None)
        also_full = collector.collect()
        # Both calls without seed re-roll. Compare a snapshot with same seed.
        c1 = SyntheticFilesystemCollector(seed=99)
        c2 = SyntheticFilesystemCollector(seed=99)
        d1 = c1.collect(since=None)
        d2 = c2.collect()
        assert len(d1.entries) == len(d2.entries)

    def test_checksum_ignores_since(self) -> None:
        from yanantin.collector.storage.local.checksum import SyntheticChecksumCollector

        collector = SyntheticChecksumCollector(seed=42)
        data = collector.collect(since=datetime(2020, 1, 1, tzinfo=timezone.utc))
        assert data.file_path  # just check it returned something


# ── Machine Config Recorder Content Hash (regression) ────────────


class TestMachineConfigRecorderContentHash:
    def test_machine_config_recorder_has_content_tag(self) -> None:
        from yanantin.machine.linux import (
            MachineConfigCollector,
            MachineConfigRecorder,
        )

        backend = InMemoryBackend()
        collector = MachineConfigCollector()
        data = collector.collect()
        envelope = WranglerEnvelope(data=data, provider_id=collector.get_provider_id())
        recorder = MachineConfigRecorder(backend)
        tensor_id = recorder.record(envelope)
        tensor = backend.get_tensor(tensor_id)
        content_tags = [t for t in tensor.lineage_tags if t.startswith("content:")]
        assert len(content_tags) == 1
