"""statx-backed lstat: everything os.lstat gives, plus the birth time.

Python 3.14's os.stat has no st_birthtime on Linux (os.statx arrives in 3.15),
though ext4/xfs/btrfs keep one. The collector already reads st_birthtime when a
stat result has it; this supplies it through glibc's statx via ctypes.
"""

from __future__ import annotations

import os
import subprocess

import pytest

from yanantin.collector.storage.local.linux.statx import lstat_with_btime


def _fs_has_btime(path) -> bool:
    out = subprocess.run(["stat", "-c", "%W", str(path)], capture_output=True, text=True).stdout.strip()
    return out not in ("", "0", "-")


@pytest.fixture
def entries(tmp_path):
    f = tmp_path / "f.txt"
    f.write_text("hello")
    d = tmp_path / "d"
    d.mkdir()
    link = tmp_path / "link"
    link.symlink_to(f)
    return [f, d, link]


def test_every_lstat_field_matches(entries):
    for p in entries:
        ref = os.lstat(p)
        ours = lstat_with_btime(p)
        for key in ("st_mode", "st_ino", "st_dev", "st_nlink", "st_uid", "st_gid", "st_size",
                    "st_atime_ns", "st_mtime_ns", "st_ctime_ns", "st_blocks", "st_blksize", "st_rdev"):
            assert getattr(ours, key) == getattr(ref, key), (p.name, key)
        for key in ("st_atime", "st_mtime", "st_ctime"):
            assert getattr(ours, key) == pytest.approx(getattr(ref, key), abs=1e-6), (p.name, key)


def test_symlink_is_not_followed(entries):
    link = entries[2]
    assert lstat_with_btime(link).st_ino == os.lstat(link).st_ino != os.stat(link).st_ino


def test_birth_time_when_the_filesystem_keeps_one(entries):
    f = entries[0]
    st = lstat_with_btime(f)
    if _fs_has_btime(f):
        expected = int(subprocess.run(["stat", "-c", "%W", str(f)], capture_output=True, text=True).stdout)
        assert int(st.st_birthtime) == expected
    else:
        assert getattr(st, "st_birthtime", None) is None


def test_missing_path_raises_like_lstat(tmp_path):
    with pytest.raises(FileNotFoundError):
        lstat_with_btime(tmp_path / "nope")


def test_collector_fills_created(tmp_path):
    from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector

    (tmp_path / "a.txt").write_text("x")
    if not _fs_has_btime(tmp_path / "a.txt"):
        pytest.skip("this filesystem keeps no birth time")
    c = LinuxFilesystemCollector(tmp_path, machine_id="statx-test")
    entry = next(e for e in c.stream_entries() if e.name == "a.txt")
    assert entry.timestamps.created is not None
    assert "st_birthtime" in entry.raw_stat


def test_statx_is_linux_only(monkeypatch):
    """On Windows or macOS the loader must yield to os.lstat, not fail at import:
    ctypes.CDLL(None) raises TypeError on Windows. (Windows has st_birthtime natively.)"""
    import sys

    from yanantin.collector.storage.local.linux import statx as mod

    for platform in ("win32", "darwin"):
        monkeypatch.setattr(sys, "platform", platform)
        assert mod._load_statx() is None
