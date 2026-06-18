from uuid import uuid4

import pytest
from pydantic import ValidationError

from yanantin.core.contribution import ContributionTarget, ContributedRecord


def test_collector_mapping_is_empty():
    target = ContributionTarget(name="X", kind="doc", naming="well_known")
    assert target.model_dump(mode="json") == {
        "name": "X",
        "kind": "doc",
        "naming": "well_known",
    }

    with pytest.raises(ValidationError):
        ContributionTarget(name="X", kind="banana", naming="well_known")

    source = uuid4()
    record = ContributedRecord(source=source, raw={"a": 1})
    assert record.timestamp is not None

    fields = record.to_contribution_fields()
    assert fields["source"] == str(source)
    assert fields["raw"] == {"a": 1}

    extra_record = ContributedRecord(source=uuid4(), raw={"a": 1}, path="/data/x")
    assert extra_record.path == "/data/x"
    assert extra_record.to_contribution_fields()["path"] == "/data/x"


@pytest.fixture
def live_db():
    """A real StandardDatabase handle on apacheta_test (test-tier creds)."""
    from yanantin.infra.config import ApachetaDBConfig, get_database

    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )


def test_registrar_owns_doc_and_edge_collections(live_db):
    from yanantin.core.registration import Registrar

    suffix = uuid4().hex
    catalog = f"RegistrarCatalog_t{suffix}"
    objects = f"Objects_t{suffix}"
    relationships = f"Relationships_t{suffix}"
    provider = uuid4()
    from_ref = f"entities/{uuid4()}"
    to_ref = f"records/{uuid4()}"

    try:
        registrar = Registrar(
            db=live_db,
            catalog_collection=catalog,
            name="doc-edge-registrar",
            description="owns document and edge contribution collections",
            owned_collection=objects,
            owned_edge_collection=relationships,
        )

        assert live_db.has_collection(objects)
        assert live_db.collection(objects).properties()["type"] == 2
        assert live_db.has_collection(relationships)
        assert live_db.collection(relationships).properties()["type"] == 3

        registrar.contribute_edge(
            provider,
            from_ref=from_ref,
            to_ref=to_ref,
            relation_type="contains",
        )

        edges = registrar.list_edge_contributions(provider)
        assert len(edges) == 1
        assert edges[0]["_from"] == from_ref
        assert edges[0]["_to"] == to_ref
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)


def test_recorder_declares_two_well_known_targets(live_db):
    from yanantin.core.registration import Registrar
    from yanantin.recorder.storage.local.linux.registration import (
        LinuxStorageRegistration,
    )
    from yanantin.collector.storage.local.linux.synthetic import (
        SyntheticFilesystemCollector,
    )

    suffix = uuid4().hex
    catalog = f"RecorderCatalog_t{suffix}"
    objects = f"Objects_t{suffix}"
    relationships = f"Relationships_t{suffix}"

    try:
        registrar = Registrar(
            db=live_db,
            catalog_collection=catalog,
            name="linux-storage-recorder-registrar",
            description="owns linux storage recorder contribution collections",
            owned_collection=objects,
            owned_edge_collection=relationships,
        )
        collector = SyntheticFilesystemCollector(seed=7)
        reg = LinuxStorageRegistration(registrar, collector)

        reg.register()

        registrants = registrar.list_registrants()
        assert len(registrants) == 2

        recorder_record = registrar.lookup_by_identifier(reg.recorder_id)
        collector_record = registrar.lookup_by_identifier(collector.get_provider_id())
        assert recorder_record is not None
        assert collector_record is not None

        try:
            recorder_targets = recorder_record.contributes_to
        except AttributeError:
            recorder_targets = recorder_record.model_extra["contributes_to"]
        assert isinstance(recorder_targets, list)
        assert len(recorder_targets) == 2
        targets_by_kind = {target["kind"]: target for target in recorder_targets}
        assert set(targets_by_kind) == {"doc", "edge"}
        assert targets_by_kind["doc"]["naming"] == "well_known"
        assert targets_by_kind["edge"]["naming"] == "well_known"

        try:
            collector_targets = collector_record.contributes_to
        except AttributeError:
            collector_targets = collector_record.model_extra["contributes_to"]
        assert collector_targets == []
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)
