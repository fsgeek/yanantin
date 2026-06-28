"""Data models for the synthetic cloud storage provider.

These model the OPEN shape a real cloud API returns: `extra="allow"`, NOT the
`extra="forbid"` of the older dropbox models. The synthetic provider is the
schema-twin of a future real cloud collector, and a real cloud API returns fields
we have not enumerated. Forbidding extras here would train the shared schema to be
closed before any open lane saw the data — the collector-level save-it-all lesson.
The synthetic must model the open shape so the real twin inherits it.

`change_type` is what makes a listing usable as a DELTA: each entry in a delta
carries how it changed, which drives the feedback edge (modified/added → re-collect
+ update; deleted → mark, no re-collect).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ChangeType = Literal["added", "modified", "deleted", "unchanged"]


class CloudEntry(BaseModel):
    """A single cloud file/folder, with how it changed in this emission.

    Open model (extra="allow"): real cloud metadata carries fields we do not
    enumerate; keep them rather than drop them at the collector boundary.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    path: str
    name: str
    is_directory: bool = False
    size: int = 0
    content_hash: str = ""
    modified: datetime | None = None
    change_type: ChangeType = "unchanged"

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.path:
            raise ValueError("path must be non-empty")
        if not self.name:
            raise ValueError("name must be non-empty")
        if self.is_directory and self.size != 0:
            raise ValueError(f"directory size must be 0, got {self.size}")
        if self.size < 0:
            raise ValueError(f"size must be >= 0, got {self.size}")
        return self


class CloudListing(BaseModel):
    """A full listing (cursor=None call) — the collector's DataT for phase 1.

    `cursor` is the delta token: pass it back to `collect()` to get only what
    changed since this listing (phase 2).
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    account_id: str
    entries: tuple[CloudEntry, ...]
    cursor: str
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.account_id:
            raise ValueError("account_id must be non-empty")
        if not self.cursor:
            raise ValueError("cursor must be non-empty")
        return self


class CloudDelta(BaseModel):
    """The result of a delta poll (cursor!=None call) — only changed entries.

    `has_more` mirrors the cloud-cursor pagination flag; the feedback-edge loop
    terminates when the delta is exhausted (has_more=False). Every entry carries a
    non-"unchanged" change_type by construction.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    account_id: str
    entries: tuple[CloudEntry, ...]
    cursor: str
    has_more: bool = False
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.account_id:
            raise ValueError("account_id must be non-empty")
        if not self.cursor:
            raise ValueError("cursor must be non-empty")
        for e in self.entries:
            if e.change_type == "unchanged":
                raise ValueError(
                    f"delta entry {e.path!r} has change_type 'unchanged' — "
                    "a delta carries only changed entries"
                )
        return self
