"""Data models for filesystem metadata collection.

These models carry the output of os.stat() and os.walk() faithfully.
The raw stat data is preserved — log before you parse.

Model validators enforce structural invariants that must hold for both
real and synthetic data. If a synthetic collector produces something
a real collector never would, validation catches it here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FileTimestamps(BaseModel):
    """Filesystem timestamps from stat results.

    created may be None on older Linux kernels (pre-4.11) that don't
    support statx/st_birthtime. No ordering is enforced between
    timestamps — clock skew, `touch`, and NFS can all break ordering
    in real data.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    created: datetime | None = None
    modified: datetime
    accessed: datetime
    changed: datetime


class FileEntryData(BaseModel):
    """Single file or directory stat record.

    The typed fields are a curated VIEW; raw_stat holds the COMPLETE generic
    capture of every st_* field the OS exposes (save-it-all at collection —
    Indaleko's opaque-Record pattern). extra="allow" so the model itself never
    refuses an unanticipated field: enumerating a known list and forbidding the
    rest is extra="forbid" over the OS, and a dropped field at collection time
    is lost forever before it can reach the open lane.

    Validators enforce: symlinks carry targets, type flags match booleans,
    sizes are non-negative, and required strings are non-empty.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    path: str
    name: str
    uri: str
    is_directory: bool
    is_symlink: bool
    size: int
    mode: int
    file_attributes: tuple[str, ...]
    timestamps: FileTimestamps
    inode: int | None = None
    device: int | None = None
    link_target: str | None = None
    raw_stat: dict = Field(default_factory=dict)
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if not self.path:
            raise ValueError("path must be non-empty")
        if not self.name:
            raise ValueError("name must be non-empty")
        if not self.uri.startswith("file://"):
            raise ValueError(f"uri must start with file://, got {self.uri!r}")
        if self.size < 0:
            raise ValueError(f"size must be >= 0, got {self.size}")
        if self.mode < 0:
            raise ValueError(f"mode must be >= 0, got {self.mode}")
        if len(self.file_attributes) == 0:
            raise ValueError("file_attributes must contain at least a type flag")

        # Symlink ↔ link_target consistency
        if self.is_symlink and self.link_target is None:
            raise ValueError("symlink entry must have a link_target")
        if not self.is_symlink and self.link_target is not None:
            raise ValueError("non-symlink entry must not have a link_target")

        # Type flag consistency with booleans
        if self.is_directory and "S_IFDIR" not in self.file_attributes:
            raise ValueError("directory entry missing S_IFDIR in file_attributes")
        if self.is_symlink and "S_IFLNK" not in self.file_attributes:
            raise ValueError("symlink entry missing S_IFLNK in file_attributes")

        return self


class FilesystemSnapshot(BaseModel):
    """Container for a directory walk — the collector's DataT.

    A snapshot is the complete result of walking a directory tree.
    Entries are ordered as encountered during the walk (parent before
    children). error_count tracks permission-denied and other OS errors
    that prevented stat on specific paths.

    Validators enforce: counts are non-negative, total_files + total_dirs
    equals the number of entries (errors prevent both counting and entry
    creation), and root_path is non-empty.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    root_path: str
    entries: tuple[FileEntryData, ...]
    total_files: int
    total_dirs: int
    error_count: int
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if not self.root_path:
            raise ValueError("root_path must be non-empty")
        if self.total_files < 0:
            raise ValueError(f"total_files must be >= 0, got {self.total_files}")
        if self.total_dirs < 0:
            raise ValueError(f"total_dirs must be >= 0, got {self.total_dirs}")
        if self.error_count < 0:
            raise ValueError(f"error_count must be >= 0, got {self.error_count}")
        if self.total_files + self.total_dirs != len(self.entries):
            raise ValueError(
                f"total_files ({self.total_files}) + total_dirs ({self.total_dirs}) "
                f"!= len(entries) ({len(self.entries)})"
            )
        return self
