# src/yanantin/recorder/storage/local/linux/normalize.py
"""The linux normalizer: FileEntryData -> StorageObject, at the recorder
boundary (the recorder owns the DB write; the collector stays silo-specific).

Maps the closed FileEntryData spine onto the open uniform StorageObject:
flat top-level file timestamps (kills d.raw.timestamps.modified), POSIX
specifics into the open lane (honest-absence on cloud), raw retained beside
the normalized view, and a DETERMINISTIC object identity so a rescan of the
same file under the same provider is idempotent re-observation, not a new row.

Spec: docs/superpowers/specs/2026-06-19-uniform-storage-object-design.md
§3.5 (normalization contract), §3.6 (source = provider/observer),
§3.7 (object_identifier = uuid5(NAMESPACE, source:uri)).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid5

from yanantin.collector.storage.local.linux.models import FileEntryData
from yanantin.collector.storage_object import StorageObject

# Fixed module-level namespace so the derivation is deterministic across runs.
NAMESPACE = UUID("6f8c9e2a-1d4b-5a3c-8e7f-0b1c2d3e4f50")


def normalize_file_entry(entry: FileEntryData, *, source: UUID) -> StorageObject:
    """Normalize one collected FileEntryData into the uniform StorageObject.

    `source` is the provider/collector id — who OBSERVED the object (§3.6),
    NOT the recorder (that lives on the recorder->object provenance edge).
    """
    object_identifier = uuid5(NAMESPACE, f"{source}:{entry.uri}")
    return StorageObject(
        object_identifier=object_identifier,
        uri=entry.uri,
        source=source,
        observed_at=datetime.now(timezone.utc),
        created=entry.timestamps.created,
        modified=entry.timestamps.modified,
        accessed=entry.timestamps.accessed,
        changed=entry.timestamps.changed,
        size=entry.size,
        label=entry.name,
        semantic_attributes={
            "inode": entry.inode,
            "device": entry.device,
            "mode": entry.mode,
            "file_attributes": entry.file_attributes,
            "link_target": entry.link_target,
        },
        raw=entry.model_dump(mode="json"),
    )
