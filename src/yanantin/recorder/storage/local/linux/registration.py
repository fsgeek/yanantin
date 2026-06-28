# src/yanantin/recorder/storage/local/linux/registration.py
"""Linux-local-storage recorder ↔ registration leaf. The recorder registers
itself AND its collector (by proxy — the collector may have no DB access), and
declares its contributes_to mapping into the registrar's open tail. Mechanism
lives in core (Registrar); this leaf supplies the linux-storage specifics, the
way Indaleko's storage recorders carry normalize_*/find_* over a base."""

from __future__ import annotations

from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.collector._collector_base import CollectorBase
from yanantin.core.collection_definition import CollectionDefinition
from yanantin.core.contribution import ContributionTarget
from yanantin.core.registration import Registrar, RegistrantRecord
from yanantin.recorder.storage.local.linux.normalize import (
    NAMESPACE,
    normalize_file_entry,
)

STORAGE_OBJECTS = "Objects"
STORAGE_RELATIONSHIPS = "Relationships"
CONTAINS_RELATION = "contains"  # directory -> child; DISTINCT from "records" provenance

RECORDER_ID = uuid5(NAMESPACE_DNS, "yanantin.recorder.filesystem")

# The shape of the Objects collection this leaf contributes into. The temporal
# window is the search-space reducer (the episodic pivot): a persistent sorted
# index on `modified` turns the temporal-window query from an O(n) full
# collection scan into an O(log n) IndexNode. Measured on the live 35,805-doc
# Objects slice: 38ms full scan -> 3ms index, and the gap widens with n (the
# full census is ~4.1M files). schema stays None — the open-lane posture A1/A2
# settled; this binds only the index, the invisible tuning the find model needs.
# The field name is SEMANTIC ("modified"); watay obfuscates it to the physical
# name when the index is created, same as the view-link path (gh #32).
OBJECTS_DEFINITION = CollectionDefinition(
    schema=None,
    indices=(
        {
            "type": "persistent",
            "fields": ["modified"],
            "name": "idx_objects_modified",
            "sparse": False,
        },
    ),
)


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
        known_uris = {e.uri for e in snapshot.entries}
        count = 0
        for entry in snapshot.entries:
            obj = normalize_file_entry(entry, source=provider_id)
            obj_key = str(obj.object_identifier)
            self._registrar.contribute(
                provider_id, _key=obj_key, **obj.to_contribution_fields()
            )
            self._registrar.contribute_edge(
                contributor_id=self.recorder_id,
                from_ref=f"entities/{self.recorder_id}",
                to_ref=f"{objects_name}/{obj_key}",
                relation_type="records",
            )
            # Directory -> child CONTAINMENT edge (the associative axis), DISTINCT
            # from the provenance "records" edge above. Only emitted when the
            # parent is itself an observed entry in this snapshot (known_uris
            # guard) so both endpoints are materialized Objects — no dangle. The
            # parent key derives from the SAME identity rule as the object
            # (uuid5(NAMESPACE, f"{source}:{uri}") in normalize.py) so endpoints
            # equal real object_identifiers and OUTBOUND traversal resolves.
            parent_uri = entry.uri.rsplit("/", 1)[0]
            if parent_uri != entry.uri and parent_uri in known_uris:
                parent_key = str(uuid5(NAMESPACE, f"{provider_id}:{parent_uri}"))
                self._registrar.contribute_edge(
                    contributor_id=self.recorder_id,
                    from_ref=f"{objects_name}/{parent_key}",
                    to_ref=f"{objects_name}/{obj_key}",
                    relation_type=CONTAINS_RELATION,
                )
            count += 1
        return count
