"""`since` keeps an entry if it was modified OR changed at or after the cutoff.

An incremental walk (Tony, 2026-10-26: give the re-walk a time, ignore what is
older) must not miss files that arrive with old mtimes: cp -p, tar x, rsync -t
and moves preserve mtime but set a new ctime. os.utime sets mtime and, as a side
effect, ctime to now, which is exactly that case.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector

OLD = datetime(2000, 1, 1, tzinfo=timezone.utc).timestamp()


def _names(root: Path, since):
    c = LinuxFilesystemCollector(root, machine_id="since-test", exclude_names=frozenset())
    return sorted(Path(e.path).name for e in c.stream_entries(since=since))


def test_old_mtime_new_ctime_is_kept(tmp_path):
    f = tmp_path / "copied_with_p.txt"
    f.write_text("x")
    os.utime(f, (OLD, OLD))  # mtime 2000; ctime now
    assert "copied_with_p.txt" in _names(tmp_path, datetime.now(timezone.utc) - timedelta(hours=1))


def test_directory_with_old_mtime_new_ctime_is_kept(tmp_path):
    d = tmp_path / "extracted"
    d.mkdir()
    os.utime(d, (OLD, OLD))
    assert "extracted" in _names(tmp_path, datetime.now(timezone.utc) - timedelta(hours=1))


def test_nothing_newer_than_the_cutoff_is_dropped(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    assert "a.txt" not in _names(tmp_path, datetime.now(timezone.utc) + timedelta(days=1))


def test_future_mtime_is_kept_by_mtime(tmp_path):
    f = tmp_path / "future.txt"
    f.write_text("x")
    future = (datetime.now(timezone.utc) + timedelta(days=2)).timestamp()
    os.utime(f, (future, future))
    assert _names(tmp_path, datetime.now(timezone.utc) + timedelta(days=1)) == ["future.txt"]


def test_no_cutoff_keeps_everything(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    os.utime(tmp_path / "a.txt", (OLD, OLD))
    assert "a.txt" in _names(tmp_path, None)
