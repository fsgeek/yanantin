"""Cloud storage recorder — the STORAGE leg of the fan-out.

Normalizes a CloudEntry onto the SAME uniform StorageObject the linux leaf uses,
and writes it into Objects through a Registrar — so cloud and local storage
CONVERGE on one collection. The uniform StorageObject's uri lane already permits
cloud:// (no file://-only validator), which is the seam that makes convergence
free rather than forced.

Idempotent by object identity: object_identifier = uuid5(NAMESPACE, source:uri),
passed as the contribution _key, so re-observing a file (the feedback edge's
re-collect) REPLACES the row in place — many changes to one file collapse to one
current Objects doc. This is the "many-to-one" the topology demonstrates.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid5

from yanantin.collector.storage.cloud.synthetic.models import CloudEntry
from yanantin.collector.storage_object import StorageObject
from yanantin.core.registration import Registrar

# Shared fixed namespace with the linux normalizer's identity rule, so the
# derivation is deterministic and cross-leaf consistent.
NAMESPACE = UUID("6f8c9e2a-1d4b-5a3c-8e7f-0b1c2d3e4f50")


def _cloud_uri(account_id: str, path: str) -> str:
    """Uniform cloud locator. Distinct scheme so cloud and local objects never
    collide on identity even if their paths coincide."""
    return f"cloud://{account_id}{path}"


def normalize_cloud_entry(
    entry: CloudEntry, *, source: UUID, account_id: str
) -> StorageObject:
    """Normalize one CloudEntry into the uniform StorageObject (cloud twin of
    normalize_file_entry). `source` is the collector/provider id (who observed)."""
    uri = _cloud_uri(account_id, entry.path)
    object_identifier = uuid5(NAMESPACE, f"{source}:{uri}")
    return StorageObject(
        object_identifier=object_identifier,
        uri=uri,
        source=source,
        observed_at=datetime.now(timezone.utc),
        modified=entry.modified,
        size=entry.size,
        label=entry.name,
        semantic_attributes={
            "content_hash": entry.content_hash,
            "is_directory": entry.is_directory,
            "change_type": entry.change_type,
        },
        raw=entry.model_dump(mode="json"),
    )


class CloudStorageRecorder:
    """Writes CloudEntries into Objects via a Registrar (the storage leg)."""

    def __init__(self, registrar: Registrar) -> None:
        self._registrar = registrar

    def update_object(self, entry: CloudEntry, *, source: UUID, account_id: str) -> UUID:
        """Normalize + contribute one entry into Objects. Idempotent on identity:
        re-observing the same uri REPLACES the row (current fields, no dupe)."""
        if not self._registrar.owns_owned_collection:
            raise ValueError(
                "CloudStorageRecorder needs a registrar that owns an Objects "
                "collection (construct it with owned_collection=Objects + "
                "owned_definition=OBJECTS_DEFINITION); well_known never mints."
            )
        obj = normalize_cloud_entry(entry, source=source, account_id=account_id)
        obj_key = str(obj.object_identifier)
        self._registrar.contribute(source, _key=obj_key, **obj.to_contribution_fields())
        return obj.object_identifier
