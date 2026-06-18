# src/yanantin/recorder/storage/local/linux/registration.py
"""Linux-local-storage recorder ↔ registration leaf. The recorder registers
itself AND its collector (by proxy — the collector may have no DB access), and
declares its contributes_to mapping into the registrar's open tail. Mechanism
lives in core (Registrar); this leaf supplies the linux-storage specifics, the
way Indaleko's storage recorders carry normalize_*/find_* over a base."""

from __future__ import annotations

from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.collector._collector_base import CollectorBase
from yanantin.core.contribution import ContributionTarget
from yanantin.core.registration import Registrar, RegistrantRecord

STORAGE_OBJECTS = "Objects"
STORAGE_RELATIONSHIPS = "Relationships"

RECORDER_ID = uuid5(NAMESPACE_DNS, "yanantin.recorder.filesystem")


class LinuxStorageRegistration:
    """Registers the linux-local-storage recorder + its collector, declaring a
    two-target well_known mapping (Objects doc + Relationships edge)."""

    CONTRIBUTES_TO: list[ContributionTarget] = [
        ContributionTarget(name=STORAGE_OBJECTS, kind="doc", naming="well_known"),
        ContributionTarget(
            name=STORAGE_RELATIONSHIPS, kind="edge", naming="well_known"
        ),
    ]

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
