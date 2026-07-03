"""Linux filesystem metadata collector.

Walks a directory tree gathering stat data for every entry. Follows the
Indaleko pattern: os.walk() + os.lstat() per entry, error counting (not
crashing) on permission denied, and faithful capture of all stat fields.
"""

from __future__ import annotations

import logging
import os
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.collector._collector_base import CollectorBase
from yanantin.collector.storage.local.linux.models import (
    FileEntryData,
    FilesystemSnapshot,
    FileTimestamps,
)
from yanantin.machine.base import _get_machine_id

logger = logging.getLogger(__name__)


@dataclass
class _WalkCounters:
    """Walk tallies that ride OUTSIDE the entry stream — a generator can't
    also return totals to a consumer that may stop early."""

    total_files: int = 0
    total_dirs: int = 0
    error_count: int = 0

# Paths never descended into during a local-storage walk. /mnt holds WSL DrvFs
# bridges to the Windows host (a foreign silo); /proc, /sys, /dev are kernel
# pseudo-filesystems (synthetic, not durable storage). The st_dev boundary
# (same_device_only) is the principled guard; this list is belt-and-suspenders
# for bridges that may share a device id with the root.
_DEFAULT_EXCLUDE_PATHS: frozenset[str] = frozenset(
    {"/mnt", "/proc", "/sys", "/dev", "/run"}
)

# Directory NAMES (not absolute paths) skipped anywhere in the tree: build/VCS
# noise that bloats the corpus without being query-worthy. Overridable — open,
# not frozen: a caller that WANTS .git contents passes a smaller set. Defaulting
# to the common noise keeps the ayllu self-index queryable rather than drowned
# in __pycache__ (the demo: 227 of 479 objects were .pyc).
_DEFAULT_EXCLUDE_NAMES: frozenset[str] = frozenset(
    {"__pycache__", ".git", ".venv", "node_modules", ".mypy_cache",
     ".pytest_cache", ".ruff_cache", ".cache"}
)

# POSIX mode bit names — derived from Indaleko's IndalekoPosix mapping.
_MODE_FLAGS: tuple[tuple[int, str], ...] = (
    (stat.S_ISUID, "S_ISUID"),
    (stat.S_ISGID, "S_ISGID"),
    (stat.S_ISVTX, "S_ISVTX"),
    (stat.S_IRUSR, "S_IRUSR"),
    (stat.S_IWUSR, "S_IWUSR"),
    (stat.S_IXUSR, "S_IXUSR"),
    (stat.S_IRGRP, "S_IRGRP"),
    (stat.S_IWGRP, "S_IWGRP"),
    (stat.S_IXGRP, "S_IXGRP"),
    (stat.S_IROTH, "S_IROTH"),
    (stat.S_IWOTH, "S_IWOTH"),
    (stat.S_IXOTH, "S_IXOTH"),
)

_FILE_TYPE_FLAGS: tuple[tuple[int, str], ...] = (
    (stat.S_IFREG, "S_IFREG"),
    (stat.S_IFDIR, "S_IFDIR"),
    (stat.S_IFLNK, "S_IFLNK"),
    (stat.S_IFBLK, "S_IFBLK"),
    (stat.S_IFCHR, "S_IFCHR"),
    (stat.S_IFIFO, "S_IFIFO"),
    (stat.S_IFSOCK, "S_IFSOCK"),
)


def _mode_to_attributes(mode: int) -> tuple[str, ...]:
    """Map a raw st_mode integer to named POSIX attribute strings."""
    attrs: list[str] = []
    # File type — only one matches
    fmt = stat.S_IFMT(mode)
    for flag, name in _FILE_TYPE_FLAGS:
        if fmt == flag:
            attrs.append(name)
            break
    # Permission and special bits
    for flag, name in _MODE_FLAGS:
        if mode & flag:
            attrs.append(name)
    return tuple(attrs)


def _stat_to_timestamps(st: os.stat_result) -> FileTimestamps:
    """Extract timestamps from a stat result. `created` is normalized from
    st_birthtime when present (Linux 4.11+ via statx); when absent it is None
    (honest absence). The raw value is also kept generically in raw_stat — this
    is only the curated typed view."""
    birthtime = getattr(st, "st_birthtime", 0)
    created = (
        datetime.fromtimestamp(birthtime, tz=timezone.utc)
        if birthtime and birthtime > 0
        else None
    )
    return FileTimestamps(
        created=created,
        modified=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
        accessed=datetime.fromtimestamp(st.st_atime, tz=timezone.utc),
        changed=datetime.fromtimestamp(st.st_ctime, tz=timezone.utc),
    )


def _full_stat_dump(st: os.stat_result) -> dict:
    """Capture EVERY st_* field the OS exposes, generically — save-it-all at the
    point of collection. We do NOT enumerate a known list (that is extra="forbid"
    over the OS: a field we never named — st_uid, st_gid, st_nlink, the *_ns
    nanosecond timestamps, st_blocks, st_rdev, or anything a future kernel/FS
    adds — would be silently lost forever before reaching the open lane). The
    normalized view below is a CONVENIENCE projection on top of this complete
    capture, not a replacement for it."""
    # Indaleko's pattern (storage/collectors/base.py:376) — capture every
    # st_* field, do not filter by type. Filtering by "types I expect" would be
    # a small extra="forbid" of its own.
    return {key: getattr(st, key) for key in dir(st) if key.startswith("st_")}


def _stat_to_entry(full_path: str, st: os.stat_result, is_symlink: bool) -> FileEntryData:
    """Convert an os.stat_result into a FileEntryData model.

    The typed fields are a curated VIEW; raw_stat is the COMPLETE capture so
    nothing the OS exposes is enumerated away (Indaleko's opaque-Record pattern:
    save the whole source datum, normalize a view on top)."""
    # basename("/") is "" — the filesystem root is its own name. Found by the
    # first full-system walk (2026-07-03); every rooted-subtree walk before it
    # had a non-empty basename.
    name = os.path.basename(full_path) or full_path
    link_target = None
    if is_symlink:
        try:
            link_target = os.readlink(full_path)
        except OSError:
            link_target = "<unreadable>"

    return FileEntryData(
        path=full_path,
        name=name,
        uri=Path(full_path).as_uri(),
        is_directory=stat.S_ISDIR(st.st_mode),
        is_symlink=is_symlink,
        size=st.st_size,
        mode=st.st_mode,
        file_attributes=_mode_to_attributes(st.st_mode),
        timestamps=_stat_to_timestamps(st),
        inode=st.st_ino,
        device=st.st_dev,
        link_target=link_target,
        raw_stat=_full_stat_dump(st),
    )


class LinuxFilesystemCollector(CollectorBase[FilesystemSnapshot]):
    """Walks a directory tree and collects stat metadata for every entry.

    Uses os.lstat() to avoid following symlinks (symlink targets are
    recorded separately). Errors on individual entries are logged and
    counted, never fatal to the walk.
    """

    def __init__(
        self,
        root_path: Path,
        machine_id: str | None = None,
        *,
        same_device_only: bool = True,
        exclude_paths: frozenset[str] = _DEFAULT_EXCLUDE_PATHS,
        exclude_names: frozenset[str] = _DEFAULT_EXCLUDE_NAMES,
    ) -> None:
        self._root_path = root_path.resolve()
        resolved_machine_id = machine_id if machine_id is not None else _get_machine_id()
        self._machine_id = resolved_machine_id
        self._provider_id = uuid5(
            NAMESPACE_DNS,
            f"yanantin.collector.filesystem.{resolved_machine_id}",
        )
        # Walk guard: stay on the originating device (don't cross filesystem
        # boundaries) and never descend into the excluded pseudo/bridge mounts.
        # In WSL, /mnt/c etc. are DrvFs bridges to the Windows HOST — following
        # them would silently ingest a foreign silo into "linux local storage",
        # conflating two tenants (the opposite of the federation goal).
        self._same_device_only = same_device_only
        self._exclude_paths = frozenset(
            str(Path(p)) for p in exclude_paths
        )
        self._exclude_names = frozenset(exclude_names)

    def _is_pruned(self, child_path: str, root_dev: int | None) -> bool:
        """True if the walk must NOT descend into child_path.

        Pruned when the path is in the exclude set, or (same_device_only) when
        it lives on a different device than the root — the host-bridge guard.
        Errors stat'ing the child are treated as 'prune' (fail-closed: never
        descend into something we cannot verify is on-device and local).
        """
        if child_path in self._exclude_paths:
            return True
        if os.path.basename(child_path) in self._exclude_names:
            return True
        if root_dev is not None:
            try:
                if os.lstat(child_path).st_dev != root_dev:
                    return True
            except OSError:
                return True
        return False

    def _walk_entries(
        self, since: datetime | None, counters: _WalkCounters
    ) -> Iterator[FileEntryData]:
        """The ONE traversal both collect() and stream_entries() ride — walk
        guard included. Yields entries as they are stat'd; tallies land on the
        passed counters (a generator cannot also return totals to a consumer
        that stops early, so the counts live outside the yield channel)."""
        # Root device id anchors the same-device guard. If the root itself can't
        # be stat'd we cannot enforce the boundary, so disable that check (the
        # path-exclude list still applies).
        root_dev: int | None = None
        if self._same_device_only:
            try:
                root_dev = os.lstat(str(self._root_path)).st_dev
            except OSError as exc:
                logger.warning(
                    "Cannot stat root %s for device guard: %s",
                    self._root_path,
                    exc,
                )

        for dirpath, dirnames, filenames in os.walk(str(self._root_path)):
            # Walk guard: prune dirnames IN PLACE so os.walk never descends into
            # excluded paths or across a device boundary. Mutating the list is
            # the documented os.walk pruning idiom.
            dirnames[:] = [
                d
                for d in dirnames
                if not self._is_pruned(os.path.join(dirpath, d), root_dev)
            ]

            # Stat the directory itself
            try:
                dir_stat = os.lstat(dirpath)
                is_link = stat.S_ISLNK(dir_stat.st_mode)
                entry = _stat_to_entry(dirpath, dir_stat, is_link)
                if since is None or entry.timestamps.modified >= since:
                    counters.total_dirs += 1
                    yield entry
            except OSError as exc:
                logger.warning("Failed to stat directory %s: %s", dirpath, exc)
                counters.error_count += 1

            # Stat each file
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                try:
                    file_stat = os.lstat(full_path)
                    is_link = stat.S_ISLNK(file_stat.st_mode)
                    entry = _stat_to_entry(full_path, file_stat, is_link)
                    if since is not None and entry.timestamps.modified < since:
                        continue
                    if stat.S_ISDIR(file_stat.st_mode):
                        counters.total_dirs += 1
                    else:
                        counters.total_files += 1
                    yield entry
                except OSError as exc:
                    logger.warning("Failed to stat file %s: %s", full_path, exc)
                    counters.error_count += 1

    def stream_entries(
        self, since: datetime | None = None
    ) -> Iterator[FileEntryData]:
        """Walk the tree yielding entries incrementally — the millions-scale
        path. Same traversal, same walk guard, same filtering as collect();
        the only difference is that no full-tree list is ever materialized
        (2.2M pydantic entries would be GBs of RAM; the batch landing path
        streams them straight to JSONL instead)."""
        yield from self._walk_entries(since, _WalkCounters())

    def collect(self, since: datetime | None = None) -> FilesystemSnapshot:
        """Walk the directory tree and return a snapshot.

        If ``since`` is provided, only entries whose mtime is at or after
        ``since`` are included. Totals reflect the filtered set.
        """
        counters = _WalkCounters()
        entries = tuple(self._walk_entries(since, counters))
        return FilesystemSnapshot(
            root_path=str(self._root_path),
            entries=entries,
            total_files=counters.total_files,
            total_dirs=counters.total_dirs,
            error_count=counters.error_count,
        )

    def get_provider_id(self) -> UUID:
        return self._provider_id

    def get_description(self) -> str:
        return (
            f"Linux filesystem collector — gathers stat metadata "
            f"from {self._root_path}"
        )
