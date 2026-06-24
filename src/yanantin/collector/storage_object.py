"""Uniform StorageObject — the open, silo-independent storage object (#17, Pour B).

The StorageObject is naive: the boundary (Pukara) and the provenance (Record)
carry cross-silo machinery, so the object itself stays a plain bag of values.

Spec: docs/superpowers/specs/2026-06-19-uniform-storage-object-design.md §1.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StorageObject(BaseModel):
    model_config = ConfigDict(extra="allow")  # the open lane — NEVER extra="forbid"

    # ── Required spine (always-present floor; schema-strict) ──
    object_identifier: UUID
    uri: str  # UNIFORM locator: file:// | dropbox:// | https://cdn... (no file://-only validator)
    source: UUID  # the PROVIDER/COLLECTOR id — who OBSERVED the object (§3.6)
    observed_at: datetime  # contribution/observation time — "when we LEARNED this"

    # ── Flat FILE timestamps (top-level, nullable — absence is legible) ──
    created: datetime | None = None
    modified: datetime | None = None
    accessed: datetime | None = None
    changed: datetime | None = None

    # ── Optional spine ──
    size: int | None = None
    label: str | None = None  # base name; indexed

    # ── Designed open lane (the unstructured pipeline writes here) ──
    semantic_attributes: dict[str, Any] = Field(default_factory=dict)

    # ── Save-it-all: the original blob retained beside the normalized view ──
    raw: dict = Field(default_factory=dict)

    def to_contribution_fields(self) -> dict:
        return self.model_dump(mode="json")
