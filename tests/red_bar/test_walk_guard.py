from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector


def _is_at_or_under(path: str, parent: Path) -> bool:
    return Path(path).is_relative_to(parent)


def test_walk_excludes_named_paths(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_file = data_dir / "kept.txt"
    excluded_dir = tmp_path / "mnt"
    excluded_file = excluded_dir / "foreign.txt"

    data_dir.mkdir()
    data_file.write_text("local\n", encoding="utf-8")
    excluded_dir.mkdir()
    excluded_file.write_text("foreign\n", encoding="utf-8")

    collector = LinuxFilesystemCollector(
        tmp_path,
        machine_id="test",
        same_device_only=False,
        exclude_paths=frozenset({str(excluded_dir)}),
    )

    snapshot = collector.collect()
    collected_paths = {entry.path for entry in snapshot.entries}

    assert str(data_file) in collected_paths
    assert not any(_is_at_or_under(path, excluded_dir) for path in collected_paths)


def test_walk_stops_at_device_boundary(tmp_path: Path, monkeypatch) -> None:
    foreign_dir = tmp_path / "foreign"
    foreign_file = foreign_dir / "foreign.txt"
    local_file = tmp_path / "local.txt"

    foreign_dir.mkdir()
    foreign_file.write_text("foreign\n", encoding="utf-8")
    local_file.write_text("local\n", encoding="utf-8")

    real_lstat = os.lstat
    root_dev = real_lstat(tmp_path).st_dev

    def fake_lstat(path, *args, **kwargs):
        stat_result = real_lstat(path, *args, **kwargs)
        if "/foreign" not in str(path):
            return stat_result

        stat_fields = {
            "st_mode": stat_result.st_mode,
            "st_size": stat_result.st_size,
            "st_mtime": stat_result.st_mtime,
            "st_atime": stat_result.st_atime,
            "st_ctime": stat_result.st_ctime,
            "st_ino": stat_result.st_ino,
            "st_dev": root_dev + 1,
        }
        if hasattr(stat_result, "st_birthtime"):
            stat_fields["st_birthtime"] = stat_result.st_birthtime
        return SimpleNamespace(**stat_fields)

    monkeypatch.setattr(os, "lstat", fake_lstat)

    collector = LinuxFilesystemCollector(
        tmp_path,
        machine_id="test",
        same_device_only=True,
    )

    snapshot = collector.collect()
    collected_paths = {entry.path for entry in snapshot.entries}

    assert str(local_file) in collected_paths
    assert not any(_is_at_or_under(path, foreign_dir) for path in collected_paths)
