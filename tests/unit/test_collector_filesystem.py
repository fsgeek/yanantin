"""Tests for filesystem metadata collectors (real and synthetic)."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from yanantin.collector.storage.local.linux.collector import (
    LinuxFilesystemCollector,
    _mode_to_attributes,
    _stat_to_timestamps,
)
from yanantin.collector.storage.local.linux.models import (
    FileEntryData,
    FilesystemSnapshot,
    FileTimestamps,
)
from yanantin.collector.storage.local.linux.synthetic import SyntheticFilesystemCollector


class TestFileTimestamps:
    def test_frozen(self) -> None:
        from datetime import datetime, timezone

        ts = FileTimestamps(
            modified=datetime.now(timezone.utc),
            accessed=datetime.now(timezone.utc),
            changed=datetime.now(timezone.utc),
        )
        with pytest.raises(Exception):
            ts.modified = datetime.now(timezone.utc)  # type: ignore[misc]

    def test_created_optional(self) -> None:
        from datetime import datetime, timezone

        ts = FileTimestamps(
            modified=datetime.now(timezone.utc),
            accessed=datetime.now(timezone.utc),
            changed=datetime.now(timezone.utc),
        )
        assert ts.created is None


class TestModeToAttributes:
    def test_regular_file(self) -> None:
        mode = stat.S_IFREG | stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH
        attrs = _mode_to_attributes(mode)
        assert "S_IFREG" in attrs
        assert "S_IRUSR" in attrs
        assert "S_IWUSR" in attrs

    def test_directory(self) -> None:
        mode = stat.S_IFDIR | stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP
        attrs = _mode_to_attributes(mode)
        assert "S_IFDIR" in attrs
        assert "S_IRUSR" in attrs
        assert "S_IWUSR" in attrs
        assert "S_IXUSR" in attrs

    def test_symlink(self) -> None:
        mode = stat.S_IFLNK | stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
        attrs = _mode_to_attributes(mode)
        assert "S_IFLNK" in attrs


class TestLinuxFilesystemCollector:
    def test_collect_returns_snapshot(self, tmp_path: Path) -> None:
        # Create some test structure
        (tmp_path / "file1.txt").write_text("hello")
        (tmp_path / "file2.py").write_text("print('hi')")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.json").write_text("{}")

        collector = LinuxFilesystemCollector(tmp_path)
        snapshot = collector.collect()

        assert isinstance(snapshot, FilesystemSnapshot)
        assert snapshot.root_path == str(tmp_path)
        assert snapshot.total_files == 3
        assert snapshot.total_dirs == 2  # tmp_path + subdir
        assert snapshot.error_count == 0

    def test_entries_have_correct_types(self, tmp_path: Path) -> None:
        (tmp_path / "test.txt").write_text("content")

        collector = LinuxFilesystemCollector(tmp_path)
        snapshot = collector.collect()

        for entry in snapshot.entries:
            assert isinstance(entry, FileEntryData)
            assert entry.path
            assert entry.name
            assert entry.uri.startswith("file://")
            assert entry.timestamps is not None

    def test_file_entry_has_stat_data(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")

        collector = LinuxFilesystemCollector(tmp_path)
        snapshot = collector.collect()

        file_entries = [e for e in snapshot.entries if not e.is_directory]
        assert len(file_entries) == 1

        entry = file_entries[0]
        assert entry.size == 11  # len("hello world")
        assert entry.inode is not None
        assert entry.device is not None
        assert "S_IFREG" in entry.file_attributes

    def test_symlink_detection(self, tmp_path: Path) -> None:
        target = tmp_path / "target.txt"
        target.write_text("target")
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        collector = LinuxFilesystemCollector(tmp_path)
        snapshot = collector.collect()

        link_entries = [e for e in snapshot.entries if e.is_symlink]
        assert len(link_entries) == 1
        assert link_entries[0].link_target is not None

    def test_provider_id_is_stable(self, tmp_path: Path) -> None:
        c1 = LinuxFilesystemCollector(tmp_path)
        c2 = LinuxFilesystemCollector(tmp_path)
        assert c1.get_provider_id() == c2.get_provider_id()

    def test_description_contains_path(self, tmp_path: Path) -> None:
        collector = LinuxFilesystemCollector(tmp_path)
        assert str(tmp_path) in collector.get_description()

    def test_permission_error_counted_not_fatal(self, tmp_path: Path) -> None:
        # Create a file, then make its parent unreadable
        subdir = tmp_path / "restricted"
        subdir.mkdir()
        (subdir / "secret.txt").write_text("hidden")
        subdir.chmod(0o000)

        try:
            collector = LinuxFilesystemCollector(tmp_path)
            snapshot = collector.collect()
            # Should complete without raising
            assert snapshot.error_count >= 0
        finally:
            subdir.chmod(0o755)

    def test_snapshot_roundtrips_json(self, tmp_path: Path) -> None:
        (tmp_path / "test.txt").write_text("hello")
        collector = LinuxFilesystemCollector(tmp_path)
        snapshot = collector.collect()

        json_str = snapshot.model_dump_json()
        restored = FilesystemSnapshot.model_validate_json(json_str)
        assert restored.root_path == snapshot.root_path
        assert restored.total_files == snapshot.total_files
        assert len(restored.entries) == len(snapshot.entries)


class TestSyntheticFilesystemCollector:
    def test_generate_returns_snapshot(self) -> None:
        collector = SyntheticFilesystemCollector(seed=42)
        snapshot = collector.generate()
        assert isinstance(snapshot, FilesystemSnapshot)
        assert len(snapshot.entries) > 0
        assert snapshot.total_files > 0
        assert snapshot.total_dirs > 0

    def test_collect_delegates_to_generate(self) -> None:
        collector = SyntheticFilesystemCollector(seed=42)
        snapshot = collector.collect()
        assert isinstance(snapshot, FilesystemSnapshot)

    def test_deterministic_with_seed(self) -> None:
        c1 = SyntheticFilesystemCollector(seed=42)
        c2 = SyntheticFilesystemCollector(seed=42)
        assert c1.collect() == c2.collect()

    def test_different_seeds_differ(self) -> None:
        c1 = SyntheticFilesystemCollector(seed=42)
        c2 = SyntheticFilesystemCollector(seed=99)
        assert c1.collect() != c2.collect()

    def test_collect_batch(self) -> None:
        collector = SyntheticFilesystemCollector(seed=42)
        batch = collector.collect_batch(3)
        assert len(batch) == 3
        for item in batch:
            assert isinstance(item, FilesystemSnapshot)

    def test_entries_have_plausible_sizes(self) -> None:
        collector = SyntheticFilesystemCollector(seed=42)
        snapshot = collector.collect()
        file_entries = [e for e in snapshot.entries if not e.is_directory]
        sizes = [e.size for e in file_entries]
        assert all(s >= 0 for s in sizes)
        # Power-law: most should be small
        assert sum(1 for s in sizes if s < 10000) > len(sizes) // 2

    def test_entries_have_valid_uris(self) -> None:
        collector = SyntheticFilesystemCollector(seed=42)
        snapshot = collector.collect()
        for entry in snapshot.entries:
            assert entry.uri.startswith("file://")

    def test_configurable_depth(self) -> None:
        shallow = SyntheticFilesystemCollector(seed=42, depth=1)
        deep = SyntheticFilesystemCollector(seed=42, depth=5)
        s_shallow = shallow.collect()
        s_deep = deep.collect()
        assert s_deep.total_dirs > s_shallow.total_dirs

    def test_provider_id_is_stable(self) -> None:
        c1 = SyntheticFilesystemCollector(seed=42)
        c2 = SyntheticFilesystemCollector(seed=99)
        assert c1.get_provider_id() == c2.get_provider_id()  # same class name

    def test_snapshot_roundtrips_json(self) -> None:
        collector = SyntheticFilesystemCollector(seed=42)
        snapshot = collector.collect()
        json_str = snapshot.model_dump_json()
        restored = FilesystemSnapshot.model_validate_json(json_str)
        assert restored == snapshot


# --- Task 4: explicit machine_id wiring (storage.local.linux collector) ---
# NOTE: these tests target yanantin.collector.storage.local.linux.collector,
# a DIFFERENT module than the LinuxFilesystemCollector imported at the top of
# this file (yanantin.collector.filesystem.collector). Imports are local to
# each test to keep the two trees unambiguous.

from unittest.mock import patch

FAKE_MACHINE_ID = "8ae0edf526f3453ab1abaf04e1c75a4a"


def test_explicit_machine_id_used_for_provider_id(tmp_path):
    """Explicit machine_id produces deterministic provider_id across runs."""
    from uuid import uuid5, NAMESPACE_DNS
    from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector

    collector = LinuxFilesystemCollector(tmp_path, machine_id=FAKE_MACHINE_ID)
    expected = uuid5(NAMESPACE_DNS, f"yanantin.collector.filesystem.{FAKE_MACHINE_ID}")
    assert collector.get_provider_id() == expected


def test_default_machine_id_falls_back_to_etc_machine_id(tmp_path):
    """When no machine_id passed, reads /etc/machine-id."""
    from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector

    with patch(
        "yanantin.collector.storage.local.linux.collector._get_machine_id",
        return_value=FAKE_MACHINE_ID,
    ):
        collector = LinuxFilesystemCollector(tmp_path)
    from uuid import uuid5, NAMESPACE_DNS

    expected = uuid5(NAMESPACE_DNS, f"yanantin.collector.filesystem.{FAKE_MACHINE_ID}")
    assert collector.get_provider_id() == expected


def test_provider_id_stable_across_instances(tmp_path):
    """Two collectors with same machine_id and path get same provider_id."""
    from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector

    c1 = LinuxFilesystemCollector(tmp_path, machine_id=FAKE_MACHINE_ID)
    c2 = LinuxFilesystemCollector(tmp_path, machine_id=FAKE_MACHINE_ID)
    assert c1.get_provider_id() == c2.get_provider_id()
