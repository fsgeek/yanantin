"""Filesystem fact recorder — stores directory walk results as facts.

Unlike FilesystemRecorder (which stores a whole snapshot as one tensor),
this decomposes the snapshot into individual facts — one per file entry.
Each fact carries the full FileEntryData as its data dict, timestamped
by the entry's modified time.

Optionally writes provenance edges (machine->fact, collector->fact) when
an ApachetaInterface backend and machine_id are supplied.
"""

from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.apacheta.interface import ApachetaInterface
from yanantin.apacheta.models.provenance_edge import ProvenanceEdge
from yanantin.collector.storage.local.linux.models import FilesystemSnapshot
from yanantin.recorder.base import FactRecorderBase
from yanantin.transport.models import WranglerEnvelope


class FilesystemFactRecorder(FactRecorderBase[FilesystemSnapshot]):
    """Decomposes a filesystem snapshot into individual facts.

    One fact per FileEntryData entry. The fact's timestamp is the
    entry's modified time. The fact's data is the full entry as a dict.

    If backend and machine_id are provided, writes two provenance edges
    per fact: machine->fact ("contains") and collector->fact ("collected_by").
    """

    def __init__(
        self,
        store: ActivityStreamStore,
        backend: ApachetaInterface | None = None,
        machine_id: str | None = None,
    ) -> None:
        super().__init__(store)
        self._backend = backend
        self._machine_id = machine_id
        self._recorder_id = uuid5(
            NAMESPACE_DNS,
            "yanantin.fact_recorder.filesystem",
        )

    def record_facts(self, envelope: WranglerEnvelope[FilesystemSnapshot]) -> int:
        """Store one fact per file entry. Return count stored."""
        data = envelope.data
        count = 0

        for entry in data.entries:
            entry_dict = entry.model_dump(mode="json")
            content_hash = self._entry_content_hash(entry_dict)

            fact = FactRecord(
                provider_id=envelope.provider_id,
                timestamp=entry.timestamps.modified,
                data=entry_dict,
                content_hash=content_hash,
            )
            self.store.store_fact(fact)

            if self._backend is not None and self._machine_id is not None:
                self._write_edges(fact, envelope.provider_id)

            count += 1

        return count

    def _write_edges(self, fact: FactRecord, provider_id: UUID) -> None:
        """Write machine->fact and collector->fact provenance edges.

        Both entity endpoints use the canonical entity _key form — str(UUID) —
        so the edges resolve to the actual stored entity documents. The
        machine entity is keyed by str(UUID(machine_id)) (see MachineConfigRecorder),
        which is hyphenated; the raw 32-hex machine_id string would NOT match and
        the edge would dangle. provider_id is already a UUID, hence already canonical.
        """
        to_ref = f"records/{fact.id}"
        machine_ref = f"entities/{UUID(self._machine_id)}"

        machine_edge = ProvenanceEdge(
            **{
                "_from": machine_ref,
                "_to": to_ref,
            },
            relation_type="contains",
        )
        self._backend.store_provenance_edge(machine_edge)

        collector_edge = ProvenanceEdge(
            **{
                "_from": f"entities/{provider_id}",
                "_to": to_ref,
            },
            relation_type="collected_by",
        )
        self._backend.store_provenance_edge(collector_edge)

    @staticmethod
    def _entry_content_hash(entry_dict: dict) -> str:
        """SHA-256 of deterministic JSON, truncated to 16 hex chars."""
        serialized = json.dumps(entry_dict, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def get_recorder_id(self) -> UUID:
        return self._recorder_id

    def get_description(self) -> str:
        return "Filesystem fact recorder — stores one fact per file entry"
