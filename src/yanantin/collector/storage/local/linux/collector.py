"""Linux filesystem metadata collector.

Walks a directory tree gathering stat data for every entry. Follows the
Indaleko pattern: os.walk() + os.lstat() per entry, error counting (not
crashing) on permission denied, and faithful capture of all stat fields.
"""

from __future__ import annotations

import logging
import os
import stat
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

# Paths never descended into during a local-storage walk. /mnt holds WSL DrvFs
# bridges to the Windows host (a foreign silo); /proc, /sys, /dev are kernel
# pseudo-filesystems (synthetic, not durable storage). The st_dev boundary
# (same_device_only) is the principled guard; this list is belt-and-suspenders
# for bridges that may share a device id with the root.
_DEFAULT_EXCLUDE_PATHS: frozenset[str] = frozenset(
    {"/mnt", "/proc", "/sys", "/dev", "/run"}
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
    """Extract timestamps from a stat result."""
    created = None
    # st_birthtime is available on Linux 4.11+ via statx
    if hasattr(st, "st_birthtime") and st.st_birthtime > 0:
        created = datetime.fromtimestamp(st.st_birthtime, tz=timezone.utc)
    return FileTimestamps(
        created=created,
        modified=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
        accessed=datetime.fromtimestamp(st.st_atime, tz=timezone.utc),
        changed=datetime.fromtimestamp(st.st_ctime, tz=timezone.utc),
    )


def _stat_to_entry(full_path: str, st: os.stat_result, is_symlink: bool) -> FileEntryData:
    """Convert an os.stat_result into a FileEntryData model."""
    name = os.path.basename(full_path)
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

    def _is_pruned(self, child_path: str, root_dev: int | None) -> bool:
        """True if the walk must NOT descend into child_path.

        Pruned when the path is in the exclude set, or (same_device_only) when
        it lives on a different device than the root — the host-bridge guard.
        Errors stat'ing the child are treated as 'prune' (fail-closed: never
        descend into something we cannot verify is on-device and local).
        """
        if child_path in self._exclude_paths:
            return True
        if root_dev is not None:
            try:
                if os.lstat(child_path).st_dev != root_dev:
                    return True
            except OSError:
                return True
        return False

    def collect(self, since: datetime | None = None) -> FilesystemSnapshot:
        """Walk the directory tree and return a snapshot.

        If ``since`` is provided, only entries whose mtime is at or after
        ``since`` are included. Totals reflect the filtered set.
        """
        entries: list[FileEntryData] = []
        total_files = 0
        total_dirs = 0
        error_count = 0

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
                    entries.append(entry)
                    total_dirs += 1
            except OSError as exc:
                logger.warning("Failed to stat directory %s: %s", dirpath, exc)
                error_count += 1

            # Stat each file
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                try:
                    file_stat = os.lstat(full_path)
                    is_link = stat.S_ISLNK(file_stat.st_mode)
                    entry = _stat_to_entry(full_path, file_stat, is_link)
                    if since is not None and entry.timestamps.modified < since:
                        continue
                    entries.append(entry)
                    if stat.S_ISDIR(file_stat.st_mode):
                        total_dirs += 1
                    else:
                        total_files += 1
                except OSError as exc:
                    logger.warning("Failed to stat file %s: %s", full_path, exc)
                    error_count += 1

        return FilesystemSnapshot(
            root_path=str(self._root_path),
            entries=tuple(entries),
            total_files=total_files,
            total_dirs=total_dirs,
            error_count=error_count,
        )

    def get_provider_id(self) -> UUID:
        return self._provider_id

    def get_description(self) -> str:
        return (
            f"Linux filesystem collector — gathers stat metadata "
            f"from {self._root_path}"
        )
