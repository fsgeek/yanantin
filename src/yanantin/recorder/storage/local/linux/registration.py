# src/yanantin/recorder/storage/local/linux/registration.py
"""Linux-local-storage recorder ↔ registration leaf. The recorder registers
itself AND its collector (by proxy — the collector may have no DB access), and
declares its contributes_to mapping into the registrar's open tail. Mechanism
lives in core (Registrar); this leaf supplies the linux-storage specifics, the
way Indaleko's storage recorders carry normalize_*/find_* over a base."""

from __future__ import annotations

from uuid import NAMESPACE_DNS, UUID, uuid4, uuid5

from yanantin.collector._collector_base import CollectorBase
from yanantin.core.contribution import ContributedRecord, ContributionTarget
from yanantin.core.registration import Registrar, RegistrantRecord

STORAGE_OBJECTS = "Objects"
STORAGE_RELATIONSHIPS = "Relationships"

RECORDER_ID = uuid5(NAMESPACE_DNS, "yanantin.recorder.filesystem")


class LinuxStorageRegistration:
    """Registers the linux-local-storage recorder + its collector, declaring a
    two-target well_known mapping (Objects doc + Relationships edge)."""

    CONTRIBUTES_TO: tuple[ContributionTarget, ...] = (
        ContributionTarget(name=STORAGE_OBJECTS, kind="doc", naming="well_known"),
        ContributionTarget(
            name=STORAGE_RELATIONSHIPS, kind="edge", naming="well_known"
        ),
    )

    def __init__(self, registrar: Registrar, collector: CollectorBase) -> None:
        self._registrar = registrar
        self._collector = collector

    @property
    def recorder_id(self) -> UUID:
        return RECORDER_ID

    def register(self) -> tuple[RegistrantRecord, RegistrantRecord]:
        """Register recorder (with the mapping) and collector (by proxy, empty
        mapping). The collector supplies its identity; the recorder declares."""
        recorder_rec = self._registrar.register(
            registrant_id=RECORDER_ID,
            registrant_name="linux-local-storage recorder",
            registrant_kind="provider",
            description="records linux filesystem snapshots into Objects",
            contributes_to=[t.model_dump(mode="json") for t in self.CONTRIBUTES_TO],
        )
        collector_rec = self._registrar.register(
            registrant_id=self._collector.get_provider_id(),
            registrant_name="linux-local-storage collector",
            registrant_kind="provider",
            description=self._collector.get_description(),
            contributes_to=[],
        )
        return recorder_rec, collector_rec

    def contribute_snapshot(self, snapshot, provider_id: UUID) -> int:
        """Contribute each file entry as a thin provenance doc into Objects and
        a recorder→object edge into Relationships. Edge endpoints use canonical
        str(UUID) form so OUTBOUND traversal resolves (raw hex dangles)."""
        # well_known means "write through a collection an owning registrar
        # created" — never mint, and never half-write. If the handed registrar
        # owns no Objects/Relationships collection, raise BEFORE touching the
        # store (the mint path is `dynamic` only, not chosen here).
        if not self._registrar.owns_owned_collection:
            raise ValueError(
                "well_known Objects target has no owning collection on the "
                "handed registrar; construct it with owned_collection=Objects "
                "(well_known never mints — that is the dynamic path)"
            )
        if not self._registrar.owns_edge_collection:
            raise ValueError(
                "well_known Relationships target has no owning edge collection; "
                "construct the registrar with owned_edge_collection=Relationships"
            )
        objects_name = self._registrar.owned_collection_name
        count = 0
        for entry in snapshot.entries:
            obj_key = uuid4()
            rec = ContributedRecord(
                source=provider_id,
                raw=entry.model_dump(mode="json"),
            )
            self._registrar.contribute(
                provider_id, _key=str(obj_key), **rec.to_contribution_fields()
            )
            self._registrar.contribute_edge(
                contributor_id=self.recorder_id,
                from_ref=f"entities/{self.recorder_id}",
                to_ref=f"{objects_name}/{obj_key}",
                relation_type="records",
            )
            count += 1
        return count
