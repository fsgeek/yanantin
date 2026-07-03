"""The filesystem root is its own name — basename("/") is "", and the first
full-system walk (2026-07-03) died on FileEntryData's non-empty-name rule.
Every prior walk was a rooted subtree with a non-empty basename."""

from yanantin.collector.storage.local.linux.collector import _stat_to_entry

import os


def test_root_directory_entry_has_nonempty_name():
    st = os.lstat("/")
    entry = _stat_to_entry("/", st, is_symlink=False)
    assert entry.name == "/"
    assert entry.is_directory
    assert entry.uri == "file:///"
