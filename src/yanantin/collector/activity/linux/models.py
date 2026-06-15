"""Data models for filesystem change event collection.

Events represent detected changes between two collection runs: files
created, modified, or deleted. The batch records the time window and
which volumes were scanned.

Model validators enforce structural invariants that must hold for both
real and synthetic data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FsChangeEvent(BaseModel):
    """A single filesystem change event.

    event_type is constrained to the three valid values at the type level.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str
    event_type: Literal["created", "modified", "deleted"]
    modified_time: datetime
    size_bytes: int
    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if not self.file_path:
            raise ValueError("file_path must be non-empty")
        if self.size_bytes < 0:
            raise ValueError(f"size_bytes must be >= 0, got {self.size_bytes}")
        return self


class FsEventBatch(BaseModel):
    """Batch of filesystem change events since last collection.

    last_run is None for the first collection — all files are reported
    as 'created' events. Subsequent runs detect modifications (mtime
    changed) and deletions (file in previous scan but not current).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    volumes: tuple[str, ...]
    events: tuple[FsChangeEvent, ...]
    last_run: datetime | None
    current_run: datetime
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if self.last_run is not None and self.current_run <= self.last_run:
            raise ValueError(
                f"current_run ({self.current_run}) must be after "
                f"last_run ({self.last_run})"
            )
        return self
