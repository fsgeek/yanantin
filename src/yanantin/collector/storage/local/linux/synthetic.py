"""Synthetic filesystem snapshot generator.

Produces FilesystemSnapshot instances with realistic directory trees:
common extensions, power-law file sizes, plausible timestamps, occasional
symlinks. Seeded for deterministic output.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath

from yanantin.collector._synthetic_base import SyntheticCollectorBase
from yanantin.collector.storage.local.linux.models import (
    FileEntryData,
    FilesystemSnapshot,
    FileTimestamps,
)

_COMMON_EXTENSIONS = (
    ".py", ".txt", ".json", ".md", ".log", ".csv", ".pdf",
    ".html", ".css", ".js", ".yaml", ".toml", ".xml", ".sh",
    ".cfg", ".ini", ".rst", ".png", ".jpg", ".gz",
)

_DIR_NAMES = (
    "src", "tests", "docs", "data", "config", "scripts", "lib",
    "build", "dist", "tmp", "cache", "logs", "output", "input",
    "assets", "static", "templates", "utils", "core", "api",
)

_FILE_STEMS = (
    "main", "config", "setup", "test", "utils", "helpers",
    "models", "views", "routes", "index", "app", "server",
    "client", "handler", "worker", "manager", "service",
    "parser", "reader", "writer", "report", "summary",
)


def _power_law_size(rng, min_size: int = 0, max_size: int = 100_000_000) -> int:
    """Generate a file size following a power-law distribution.

    Most files are small, few are large — matches real filesystem patterns.
    """
    # Pareto distribution shifted to [min_size, max_size]
    alpha = 1.5
    u = rng.random()
    raw = min_size * ((1 - u) ** (-1 / alpha))
    return min(int(raw), max_size)


class SyntheticFilesystemCollector(SyntheticCollectorBase[FilesystemSnapshot]):
    """Generates realistic filesystem snapshots with deterministic output.

    Configurable depth, files per directory, and time window. Seeded
    RNG ensures the same parameters produce identical snapshots.
    """

    def __init__(
        self,
        seed: int | None = None,
        depth: int = 3,
        files_per_dir: int = 5,
        root_path: str = "/synthetic/root",
        time_window_days: int = 365,
        symlink_probability: float = 0.05,
    ) -> None:
        super().__init__(seed)
        self._depth = depth
        self._files_per_dir = files_per_dir
        self._root_path = root_path
        self._time_window = timedelta(days=time_window_days)
        self._symlink_prob = symlink_probability
        self._base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

    def _random_timestamp(self) -> datetime:
        """Generate a random timestamp within the configured window."""
        offset = self._rng.random() * self._time_window.total_seconds()
        return self._base_time + timedelta(seconds=offset)

    def _make_timestamps(self) -> FileTimestamps:
        """Generate a plausible set of file timestamps.

        created <= modified <= accessed, changed near modified.
        """
        created = self._random_timestamp()
        modified = created + timedelta(
            seconds=self._rng.random() * 86400 * 30,
        )
        accessed = modified + timedelta(
            seconds=self._rng.random() * 86400 * 7,
        )
        changed = modified + timedelta(
            seconds=self._rng.random() * 3600,
        )
        return FileTimestamps(
            created=created,
            modified=modified,
            accessed=accessed,
            changed=changed,
        )

    def _make_dir_entry(self, path: str, collected_at: datetime) -> FileEntryData:
        """Create a directory entry."""
        name = PurePosixPath(path).name or path
        return FileEntryData(
            path=path,
            name=name,
            uri=f"file://{path}",
            is_directory=True,
            is_symlink=False,
            size=4096,
            mode=0o40755,  # drwxr-xr-x
            file_attributes=("S_IFDIR", "S_IRUSR", "S_IWUSR", "S_IXUSR",
                             "S_IRGRP", "S_IXGRP", "S_IROTH", "S_IXOTH"),
            timestamps=self._make_timestamps(),
            inode=self._rng.randint(100000, 9999999),
            device=self._rng.randint(1, 255),
            collected_at=collected_at,
        )

    def _make_file_entry(
        self, dir_path: str, collected_at: datetime, used_names: set[str]
    ) -> FileEntryData:
        """Create a file entry within the given directory. Names are made unique
        within the directory: a real filesystem cannot hold two entries at the
        same path, and deterministic object identity (uuid5 over the uri) relies
        on that natural-key uniqueness."""
        stem = self._rng.choice(_FILE_STEMS)
        ext = self._rng.choice(_COMMON_EXTENSIONS)
        name = f"{stem}{ext}"
        if name in used_names:
            suffix = 1
            while f"{stem}_{suffix}{ext}" in used_names:
                suffix += 1
            name = f"{stem}_{suffix}{ext}"
        used_names.add(name)
        path = f"{dir_path}/{name}"
        is_symlink = self._rng.random() < self._symlink_prob

        link_target = None
        if is_symlink:
            link_target = f"/synthetic/target/{self._rng.choice(_FILE_STEMS)}{ext}"

        return FileEntryData(
            path=path,
            name=name,
            uri=f"file://{path}",
            is_directory=False,
            is_symlink=is_symlink,
            size=_power_law_size(self._rng),
            mode=0o100644 if not is_symlink else 0o120777,
            file_attributes=(
                ("S_IFREG", "S_IRUSR", "S_IWUSR", "S_IRGRP", "S_IROTH")
                if not is_symlink
                else ("S_IFLNK", "S_IRUSR", "S_IWUSR", "S_IXUSR",
                       "S_IRGRP", "S_IWGRP", "S_IXGRP",
                       "S_IROTH", "S_IWOTH", "S_IXOTH")
            ),
            timestamps=self._make_timestamps(),
            inode=self._rng.randint(100000, 9999999),
            device=self._rng.randint(1, 255),
            link_target=link_target,
            collected_at=collected_at,
        )

    def _walk_synthetic(
        self,
        current_path: str,
        current_depth: int,
        entries: list[FileEntryData],
        stats: dict[str, int],
        collected_at: datetime,
    ) -> None:
        """Recursively build a synthetic directory tree."""
        # Add directory entry
        entries.append(self._make_dir_entry(current_path, collected_at))
        stats["dirs"] += 1

        # Add files (names unique within this directory)
        used_names: set[str] = set()
        n_files = self._rng.randint(1, self._files_per_dir)
        for _ in range(n_files):
            entries.append(
                self._make_file_entry(current_path, collected_at, used_names)
            )
            stats["files"] += 1

        # Recurse into subdirectories (subdir names unique within this directory,
        # and distinct from file names — one namespace per directory)
        if current_depth < self._depth:
            n_subdirs = self._rng.randint(1, 3)
            for _ in range(n_subdirs):
                subdir_name = self._rng.choice(_DIR_NAMES)
                if subdir_name in used_names:
                    suffix = 1
                    while f"{subdir_name}_{suffix}" in used_names:
                        suffix += 1
                    subdir_name = f"{subdir_name}_{suffix}"
                used_names.add(subdir_name)
                subdir_path = f"{current_path}/{subdir_name}"
                self._walk_synthetic(
                    subdir_path, current_depth + 1, entries, stats,
                    collected_at,
                )

    def generate(self) -> FilesystemSnapshot:
        """Generate a synthetic filesystem snapshot."""
        entries: list[FileEntryData] = []
        stats: dict[str, int] = {"files": 0, "dirs": 0}
        # Use a deterministic timestamp for all entries in this snapshot
        collected_at = self._random_timestamp()

        self._walk_synthetic(
            self._root_path, 0, entries, stats, collected_at,
        )

        return FilesystemSnapshot(
            root_path=self._root_path,
            entries=tuple(entries),
            total_files=stats["files"],
            total_dirs=stats["dirs"],
            error_count=0,
            collected_at=collected_at,
        )

    def get_description(self) -> str:
        return (
            f"Synthetic filesystem collector — generates fake directory "
            f"trees with depth={self._depth}, "
            f"files_per_dir={self._files_per_dir}"
        )
