"""Isomorphism tests — verify real and synthetic collectors produce
structurally identical output that satisfies the same invariants.

These tests are the enforcement mechanism: if a synthetic collector
produces data that a real collector never would, the test fails here.
Both outputs go through identical validation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from yanantin.collector.storage.local.checksum import (
    ChecksumCollector,
    ChecksumData,
    SyntheticChecksumCollector,
)
from yanantin.collector.storage.local.linux import (
    FileEntryData,
    FilesystemSnapshot,
    LinuxFilesystemCollector,
    SyntheticFilesystemCollector,
)
from yanantin.collector.activity.linux import (
    FsChangeEvent,
    FsEventBatch,
    FsIncrementalCollector,
    SyntheticFsEventCollector,
)
from yanantin.collector.storage.cloud.dropbox import (
    DropboxEntryData,
    DropboxListing,
    SyntheticDropboxCollector,
)


# ── Shared invariant checkers ────────────────────────────────────────

def assert_valid_filesystem_snapshot(snap: FilesystemSnapshot) -> None:
    """Check invariants that must hold for any FilesystemSnapshot, regardless
    of whether it came from a real or synthetic collector."""
    assert snap.root_path, "root_path must be non-empty"
    assert snap.total_files >= 0
    assert snap.total_dirs >= 0
    assert snap.error_count >= 0
    assert snap.total_files + snap.total_dirs == len(snap.entries)

    for entry in snap.entries:
        assert_valid_file_entry(entry)


def assert_valid_file_entry(entry: FileEntryData) -> None:
    """Check invariants that must hold for any FileEntryData."""
    assert entry.path, "path must be non-empty"
    assert entry.name, "name must be non-empty"
    assert entry.uri.startswith("file://"), f"uri must start with file://, got {entry.uri!r}"
    assert entry.size >= 0, f"size must be >= 0, got {entry.size}"
    assert entry.mode >= 0
    assert len(entry.file_attributes) >= 1, "must have at least one type flag"

    # Type flag ↔ boolean consistency
    if entry.is_directory:
        assert "S_IFDIR" in entry.file_attributes
    if entry.is_symlink:
        assert "S_IFLNK" in entry.file_attributes
        assert entry.link_target is not None
    else:
        assert entry.link_target is None

    # Exactly one file type flag
    type_flags = {"S_IFREG", "S_IFDIR", "S_IFLNK", "S_IFBLK", "S_IFCHR", "S_IFIFO", "S_IFSOCK"}
    present_types = type_flags & set(entry.file_attributes)
    assert len(present_types) == 1, f"expected exactly one type flag, got {present_types}"


def assert_valid_checksum_data(data: ChecksumData) -> None:
    """Check invariants that must hold for any ChecksumData."""
    assert data.file_path, "file_path must be non-empty"
    assert data.file_size >= 0
    assert len(data.algorithms) > 0
    assert set(data.checksums.keys()) == set(data.algorithms)

    for alg, digest in data.checksums.items():
        assert digest, f"digest for {alg} must be non-empty"
        # Must be valid hex
        int(digest, 16)


def assert_valid_fs_event_batch(batch: FsEventBatch) -> None:
    """Check invariants that must hold for any FsEventBatch."""
    if batch.last_run is not None:
        assert batch.current_run > batch.last_run

    for event in batch.events:
        assert event.file_path, "file_path must be non-empty"
        assert event.event_type in {"created", "modified", "deleted"}
        assert event.size_bytes >= 0


def assert_valid_dropbox_listing(listing: DropboxListing) -> None:
    """Check invariants that must hold for any DropboxListing."""
    assert listing.account_email, "account_email must be non-empty"
    assert listing.total_files >= 0
    assert listing.total_folders >= 0

    actual_files = sum(1 for e in listing.entries if e.entry_type == "file")
    actual_folders = sum(1 for e in listing.entries if e.entry_type == "folder")
    assert listing.total_files == actual_files
    assert listing.total_folders == actual_folders

    for entry in listing.entries:
        assert entry.name, "name must be non-empty"
        assert entry.path_display, "path_display must be non-empty"
        assert entry.path_lower == entry.path_display.lower()
        assert entry.entry_type in {"file", "folder", "deleted"}
        if entry.entry_type == "file":
            assert entry.size >= 0
        if entry.entry_type == "folder":
            assert entry.size == 0


# ── Schema isomorphism ───────────────────────────────────────────────

def assert_schema_match(real_data, synthetic_data) -> None:
    """Verify that real and synthetic data have identical JSON schemas.

    This catches field drift: if someone adds a field to the real
    collector's output but not the synthetic, the schemas diverge.
    """
    real_schema = type(real_data).model_json_schema()
    synthetic_schema = type(synthetic_data).model_json_schema()
    assert real_schema == synthetic_schema, (
        f"Schema mismatch between {type(real_data).__name__} instances"
    )


# ── Parametrized isomorphism tests ───────────────────────────────────

class TestFilesystemIsomorphism:
    """Run identical invariant checks against real and synthetic filesystem output."""

    @pytest.fixture
    def real_snapshot(self, tmp_path: Path) -> FilesystemSnapshot:
        # Build a small but realistic directory tree
        (tmp_path / "file1.txt").write_text("hello world")
        (tmp_path / "file2.py").write_text("print('hi')")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.json").write_text("{}")
        link = tmp_path / "link.txt"
        link.symlink_to(tmp_path / "file1.txt")

        collector = LinuxFilesystemCollector(tmp_path)
        return collector.collect()

    @pytest.fixture
    def synthetic_snapshot(self) -> FilesystemSnapshot:
        collector = SyntheticFilesystemCollector(seed=42, depth=2, files_per_dir=3)
        return collector.collect()

    def test_real_satisfies_invariants(self, real_snapshot: FilesystemSnapshot) -> None:
        assert_valid_filesystem_snapshot(real_snapshot)

    def test_synthetic_satisfies_invariants(self, synthetic_snapshot: FilesystemSnapshot) -> None:
        assert_valid_filesystem_snapshot(synthetic_snapshot)

    def test_schema_match(self, real_snapshot, synthetic_snapshot) -> None:
        assert_schema_match(real_snapshot, synthetic_snapshot)

    def test_both_roundtrip_identically(self, real_snapshot, synthetic_snapshot) -> None:
        """Both must survive JSON roundtrip via the same model."""
        for snap in (real_snapshot, synthetic_snapshot):
            json_str = snap.model_dump_json()
            restored = FilesystemSnapshot.model_validate_json(json_str)
            assert restored == snap

    def test_synthetic_batch_all_valid(self) -> None:
        """Every item in a batch must independently satisfy invariants."""
        collector = SyntheticFilesystemCollector(seed=0)
        for snap in collector.collect_batch(10):
            assert_valid_filesystem_snapshot(snap)


class TestChecksumIsomorphism:
    @pytest.fixture
    def real_data(self, tmp_path: Path) -> ChecksumData:
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")
        return ChecksumCollector(test_file).collect()

    @pytest.fixture
    def synthetic_data(self) -> ChecksumData:
        return SyntheticChecksumCollector(seed=42).collect()

    def test_real_satisfies_invariants(self, real_data) -> None:
        assert_valid_checksum_data(real_data)

    def test_synthetic_satisfies_invariants(self, synthetic_data) -> None:
        assert_valid_checksum_data(synthetic_data)

    def test_schema_match(self, real_data, synthetic_data) -> None:
        assert_schema_match(real_data, synthetic_data)

    def test_both_roundtrip_identically(self, real_data, synthetic_data) -> None:
        for data in (real_data, synthetic_data):
            json_str = data.model_dump_json()
            restored = ChecksumData.model_validate_json(json_str)
            assert restored == data

    def test_synthetic_batch_all_valid(self) -> None:
        collector = SyntheticChecksumCollector(seed=0)
        for data in collector.collect_batch(20):
            assert_valid_checksum_data(data)


class TestFsEventsIsomorphism:
    @pytest.fixture
    def real_batch(self, tmp_path: Path) -> FsEventBatch:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "a.txt").write_text("hello")
        (data_dir / "b.txt").write_text("world")
        state_file = tmp_path / "state.json"
        return FsIncrementalCollector([str(data_dir)], state_file).collect()

    @pytest.fixture
    def synthetic_batch(self) -> FsEventBatch:
        return SyntheticFsEventCollector(seed=42).collect()

    def test_real_satisfies_invariants(self, real_batch) -> None:
        assert_valid_fs_event_batch(real_batch)

    def test_synthetic_satisfies_invariants(self, synthetic_batch) -> None:
        assert_valid_fs_event_batch(synthetic_batch)

    def test_schema_match(self, real_batch, synthetic_batch) -> None:
        assert_schema_match(real_batch, synthetic_batch)

    def test_both_roundtrip_identically(self, real_batch, synthetic_batch) -> None:
        for batch in (real_batch, synthetic_batch):
            json_str = batch.model_dump_json()
            restored = FsEventBatch.model_validate_json(json_str)
            assert restored == batch

    def test_synthetic_batch_all_valid(self) -> None:
        collector = SyntheticFsEventCollector(seed=0)
        for batch in collector.collect_batch(10):
            assert_valid_fs_event_batch(batch)


class TestDropboxIsomorphism:
    """Dropbox real collector requires SDK + auth, so we test synthetic
    against the model validators and schema. The real collector's output
    passes through the same model, so any validator that catches synthetic
    bugs also catches real bugs."""

    @pytest.fixture
    def synthetic_listing(self) -> DropboxListing:
        return SyntheticDropboxCollector(seed=42, total_entries=50).collect()

    def test_synthetic_satisfies_invariants(self, synthetic_listing) -> None:
        assert_valid_dropbox_listing(synthetic_listing)

    def test_synthetic_roundtrips(self, synthetic_listing) -> None:
        json_str = synthetic_listing.model_dump_json()
        restored = DropboxListing.model_validate_json(json_str)
        assert restored == synthetic_listing

    def test_synthetic_batch_all_valid(self) -> None:
        collector = SyntheticDropboxCollector(seed=0, total_entries=30)
        for listing in collector.collect_batch(10):
            assert_valid_dropbox_listing(listing)

    def test_many_seeds_all_valid(self) -> None:
        """Sweep seeds to catch edge cases in the synthetic generator."""
        for seed in range(100):
            collector = SyntheticDropboxCollector(seed=seed, total_entries=20)
            listing = collector.collect()
            assert_valid_dropbox_listing(listing)


class TestValidatorsCatchBadData:
    """Verify that model validators actually reject invalid data.

    These are the complement to the isomorphism tests: if the validators
    don't fire on bad input, they provide false confidence.
    """

    def test_negative_file_size_rejected(self) -> None:
        with pytest.raises(Exception, match="size must be >= 0"):
            FileEntryData(
                path="/test", name="test", uri="file:///test",
                is_directory=False, is_symlink=False,
                size=-1, mode=0o100644,
                file_attributes=("S_IFREG", "S_IRUSR"),
                timestamps=_dummy_timestamps(),
            )

    def test_symlink_without_target_rejected(self) -> None:
        with pytest.raises(Exception, match="symlink.*link_target"):
            FileEntryData(
                path="/test", name="test", uri="file:///test",
                is_directory=False, is_symlink=True,
                size=0, mode=0o120777,
                file_attributes=("S_IFLNK", "S_IRUSR"),
                timestamps=_dummy_timestamps(),
                link_target=None,
            )

    def test_directory_missing_type_flag_rejected(self) -> None:
        with pytest.raises(Exception, match="S_IFDIR"):
            FileEntryData(
                path="/test", name="test", uri="file:///test",
                is_directory=True, is_symlink=False,
                size=4096, mode=0o40755,
                file_attributes=("S_IRUSR",),  # missing S_IFDIR
                timestamps=_dummy_timestamps(),
            )

    def test_snapshot_count_mismatch_rejected(self) -> None:
        entry = FileEntryData(
            path="/test", name="test", uri="file:///test",
            is_directory=False, is_symlink=False,
            size=100, mode=0o100644,
            file_attributes=("S_IFREG", "S_IRUSR"),
            timestamps=_dummy_timestamps(),
        )
        with pytest.raises(Exception, match="total_files.*total_dirs.*entries"):
            FilesystemSnapshot(
                root_path="/root",
                entries=(entry,),
                total_files=5,  # wrong
                total_dirs=0,
                error_count=0,
            )

    def test_checksum_key_mismatch_rejected(self) -> None:
        with pytest.raises(Exception, match="absent from checksums"):
            ChecksumData(
                file_path="/test",
                file_size=100,
                checksums={"sha256": "abc123"},
                algorithms=("sha256", "md5"),  # md5 missing from checksums
            )

    def test_checksum_invalid_hex_rejected(self) -> None:
        with pytest.raises(Exception, match="not valid hex"):
            ChecksumData(
                file_path="/test",
                file_size=100,
                checksums={"sha256": "not_hex_at_all!"},
                algorithms=("sha256",),
            )

    def test_dropbox_folder_nonzero_size_rejected(self) -> None:
        with pytest.raises(Exception, match="folder size must be 0"):
            DropboxEntryData(
                name="Photos",
                path_display="/Photos",
                path_lower="/photos",
                entry_type="folder",
                size=1024,  # folders should be 0
            )

    def test_dropbox_path_lower_mismatch_rejected(self) -> None:
        with pytest.raises(Exception, match="path_lower"):
            DropboxEntryData(
                name="Test.txt",
                path_display="/Test.txt",
                path_lower="/WRONG",
                entry_type="file",
            )

    def test_dropbox_count_mismatch_rejected(self) -> None:
        entry = DropboxEntryData(
            name="test.txt",
            path_display="/test.txt",
            path_lower="/test.txt",
            entry_type="file",
            size=100,
        )
        with pytest.raises(Exception, match="total_files.*actual file count"):
            DropboxListing(
                account_email="test@example.com",
                entries=(entry,),
                total_files=5,  # wrong
                total_folders=0,
            )

    def test_fs_event_invalid_type_rejected(self) -> None:
        from datetime import datetime, timezone

        with pytest.raises(Exception):
            FsChangeEvent(
                file_path="/test",
                event_type="renamed",  # not a valid literal
                modified_time=datetime.now(timezone.utc),
                size_bytes=100,
            )

    def test_fs_batch_current_before_last_rejected(self) -> None:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        from datetime import timedelta
        with pytest.raises(Exception, match="current_run.*must be after"):
            FsEventBatch(
                volumes=("/tmp",),
                events=(),
                last_run=now,
                current_run=now - timedelta(hours=1),
            )


def _dummy_timestamps():
    from datetime import datetime, timezone
    from yanantin.collector.storage.local.linux.models import FileTimestamps

    now = datetime.now(timezone.utc)
    return FileTimestamps(modified=now, accessed=now, changed=now)
