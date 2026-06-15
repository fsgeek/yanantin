"""Data models for Dropbox metadata collection.

Carries file and folder metadata from the Dropbox API faithfully.
The content_hash is Dropbox's own hash (not SHA-256), useful for
detecting changes without downloading files.

Model validators enforce structural invariants that must hold for both
real and synthetic data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DropboxEntryData(BaseModel):
    """Single Dropbox file or folder metadata.

    entry_type is constrained to the three valid Dropbox entry kinds.
    Validators enforce: folders have zero size, path_lower matches
    path_display, and name is non-empty.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    path_display: str
    path_lower: str
    entry_type: Literal["file", "folder", "deleted"]
    size: int = 0
    content_hash: str = ""
    rev: str = ""
    modified_time: datetime | None = None
    shared: bool = False
    is_downloadable: bool = True
    media_info: dict = Field(default_factory=dict)
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if not self.name:
            raise ValueError("name must be non-empty")
        if not self.path_display:
            raise ValueError("path_display must be non-empty")
        if self.path_lower != self.path_display.lower():
            raise ValueError(
                f"path_lower ({self.path_lower!r}) must be "
                f"path_display.lower() ({self.path_display.lower()!r})"
            )
        if self.entry_type == "file" and self.size < 0:
            raise ValueError(f"file size must be >= 0, got {self.size}")
        if self.entry_type == "folder" and self.size != 0:
            raise ValueError(f"folder size must be 0, got {self.size}")
        return self


class DropboxListing(BaseModel):
    """Full Dropbox listing — the collector's DataT.

    cursor is the Dropbox pagination token for incremental sync:
    pass it back on the next collection to get only changes since
    this listing.

    Validators enforce: counts match actual entries, account_email
    is non-empty.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    account_email: str
    entries: tuple[DropboxEntryData, ...]
    total_files: int
    total_folders: int
    cursor: str = ""
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if not self.account_email:
            raise ValueError("account_email must be non-empty")
        if self.total_files < 0:
            raise ValueError(f"total_files must be >= 0, got {self.total_files}")
        if self.total_folders < 0:
            raise ValueError(f"total_folders must be >= 0, got {self.total_folders}")

        actual_files = sum(1 for e in self.entries if e.entry_type == "file")
        actual_folders = sum(1 for e in self.entries if e.entry_type == "folder")
        if self.total_files != actual_files:
            raise ValueError(
                f"total_files ({self.total_files}) != actual file count ({actual_files})"
            )
        if self.total_folders != actual_folders:
            raise ValueError(
                f"total_folders ({self.total_folders}) != actual folder count ({actual_folders})"
            )
        return self
