from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from yanantin.collector.storage_object import StorageObject
from yanantin.core.contribution import ContributionTarget


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
    record = StorageObject(
        object_identifier=uuid4(),
        uri="file:///data/x",
        source=source,
        observed_at=datetime.now(timezone.utc),
        raw={"a": 1},
    )

    fields = record.to_contribution_fields()
    assert fields["source"] == str(source)
    assert fields["raw"] == {"a": 1}

    extra_record = StorageObject(
        object_identifier=uuid4(),
        uri="file:///data/x",
        source=uuid4(),
        observed_at=datetime.now(timezone.utc),
        raw={"a": 1},
        path="/data/x",
    )
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
    from yanantin.core.khipu import Khipu
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
            khipu=Khipu(db=live_db),
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
    from yanantin.core.khipu import Khipu
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
            khipu=Khipu(db=live_db),
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


def test_contributed_record_provenance_round_trips(live_db):
    from yanantin.collector.storage.local.linux.synthetic import (
        SyntheticFilesystemCollector,
    )
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import Registrar
    from yanantin.recorder.storage.local.linux.registration import (
        LinuxStorageRegistration,
    )

    suffix = uuid4().hex
    catalog = f"RecorderCatalog_t{suffix}"
    objects = f"Objects_t{suffix}"
    relationships = f"Relationships_t{suffix}"

    try:
        registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=catalog,
            name="linux-storage-recorder-registrar",
            description="owns linux storage recorder contribution collections",
            owned_collection=objects,
            owned_edge_collection=relationships,
        )
        collector = SyntheticFilesystemCollector(seed=7)
        reg = LinuxStorageRegistration(registrar, collector)
        reg.register()

        snapshot = SyntheticFilesystemCollector(seed=7).collect()
        provider_id = collector.get_provider_id()
        n = reg.contribute_snapshot(snapshot, provider_id)

        assert n == len(snapshot.entries)
        assert n > 0

        docs = registrar.list_contributions(provider_id)
        assert len(docs) == n
        assert all(doc["source"] == str(provider_id) for doc in docs)
        assert all(doc.get("raw") for doc in docs)

        edges = registrar.list_edge_contributions(reg.recorder_id)
        records_edges = [e for e in edges if e["relation_type"] == "records"]
        assert len(records_edges) == n

        reached = list(
            live_db.aql.execute(
                f"FOR v, e IN 1..1 OUTBOUND @start `{relationships}` "
                "RETURN {vertex: v._id, edge_to: e._to}",
                bind_vars={"start": f"entities/{reg.recorder_id}"},
            )
        )
        assert len(reached) == n
        assert all(row["vertex"] == row["edge_to"] for row in reached)
        assert all(row["vertex"].startswith(f"{objects}/") for row in reached)
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)


def test_re_observation_is_idempotent(live_db):
    from yanantin.collector.storage.local.linux.synthetic import (
        SyntheticFilesystemCollector,
    )
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import Registrar
    from yanantin.recorder.storage.local.linux.registration import (
        LinuxStorageRegistration,
    )

    suffix = uuid4().hex
    catalog = f"RecorderCatalog_t{suffix}"
    objects = f"Objects_t{suffix}"
    relationships = f"Relationships_t{suffix}"

    try:
        registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=catalog,
            name="linux-storage-recorder-registrar",
            description="owns linux storage recorder contribution collections",
            owned_collection=objects,
            owned_edge_collection=relationships,
        )
        collector = SyntheticFilesystemCollector(seed=17)
        reg = LinuxStorageRegistration(registrar, collector)
        reg.register()

        snapshot = SyntheticFilesystemCollector(seed=17).collect()
        provider_id = collector.get_provider_id()
        n1 = reg.contribute_snapshot(snapshot, provider_id)

        object_count_after_first_scan = live_db.collection(objects).count()

        n2 = reg.contribute_snapshot(snapshot, provider_id)

        assert live_db.collection(objects).count() == object_count_after_first_scan
        assert n2 == n1
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)


def test_real_and_synthetic_interchangeable(live_db, tmp_path):
    from yanantin.collector.storage.local.linux.collector import (
        LinuxFilesystemCollector,
    )
    from yanantin.collector.storage.local.linux.synthetic import (
        SyntheticFilesystemCollector,
    )
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import Registrar
    from yanantin.recorder.storage.local.linux.registration import (
        LinuxStorageRegistration,
    )

    (tmp_path / "alpha.txt").write_text("alpha")
    (tmp_path / "beta.txt").write_text("beta")

    real_suffix = uuid4().hex
    real_catalog = f"RecorderCatalog_t{real_suffix}"
    real_objects = f"Objects_t{real_suffix}"
    real_relationships = f"Relationships_t{real_suffix}"

    synth_suffix = uuid4().hex
    synth_catalog = f"RecorderCatalog_t{synth_suffix}"
    synth_objects = f"Objects_t{synth_suffix}"
    synth_relationships = f"Relationships_t{synth_suffix}"

    created = (
        real_catalog,
        real_objects,
        real_relationships,
        synth_catalog,
        synth_objects,
        synth_relationships,
    )

    try:
        real_registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=real_catalog,
            name="linux-storage-real-recorder-registrar",
            description="owns real linux storage recorder contribution collections",
            owned_collection=real_objects,
            owned_edge_collection=real_relationships,
        )
        real_collector = LinuxFilesystemCollector(root_path=tmp_path)
        real_registration = LinuxStorageRegistration(real_registrar, real_collector)
        real_registration.register()
        real_snapshot = real_collector.collect()
        real_count = real_registration.contribute_snapshot(
            real_snapshot,
            real_collector.get_provider_id(),
        )

        synth_registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=synth_catalog,
            name="linux-storage-synthetic-recorder-registrar",
            description="owns synthetic linux storage recorder contribution collections",
            owned_collection=synth_objects,
            owned_edge_collection=synth_relationships,
        )
        synth_collector = SyntheticFilesystemCollector(seed=7)
        synth_registration = LinuxStorageRegistration(synth_registrar, synth_collector)
        synth_registration.register()
        synth_snapshot = synth_collector.collect()
        synth_count = synth_registration.contribute_snapshot(
            synth_snapshot,
            synth_collector.get_provider_id(),
        )

        assert real_count > 0
        assert synth_count > 0

        real_docs = real_registrar.list_contributions(real_collector.get_provider_id())
        synth_docs = synth_registrar.list_contributions(
            synth_collector.get_provider_id()
        )
        assert len(real_docs) == real_count
        assert len(synth_docs) == synth_count
        assert set(real_docs[0].keys()) == set(synth_docs[0].keys())
    finally:
        for name in created:
            if live_db.has_collection(name):
                live_db.delete_collection(name)


def test_well_known_attaches_does_not_duplicate(live_db):
    import json

    from yanantin.collector.storage.local.linux.synthetic import (
        SyntheticFilesystemCollector,
    )
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import Registrar
    from yanantin.recorder.storage.local.linux.registration import (
        LinuxStorageRegistration,
    )

    suffix = uuid4().hex
    catalog = f"RecorderCatalog_t{suffix}"
    objects = f"Objects_t{suffix}"
    relationships = f"Relationships_t{suffix}"
    provider_a = uuid4()
    provider_b = uuid4()

    try:
        registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=catalog,
            name="linux-storage-shared-objects-recorder-registrar",
            description="owns one shared Objects collection for recorder mappings",
            owned_collection=objects,
            owned_edge_collection=relationships,
        )
        collector = SyntheticFilesystemCollector(seed=7)
        reg = LinuxStorageRegistration(registrar, collector)
        reg.register()

        snapshot_a = SyntheticFilesystemCollector(seed=7).collect()
        snapshot_b = SyntheticFilesystemCollector(seed=11).collect()
        n_a = reg.contribute_snapshot(snapshot_a, provider_a)
        n_b = reg.contribute_snapshot(snapshot_b, provider_b)

        collection_names = {collection["name"] for collection in live_db.collections()}
        assert objects in collection_names
        assert {name for name in collection_names if name.startswith(objects)} == {
            objects
        }
        assert live_db.collection(objects).count() == n_a + n_b

        docs = registrar.list_contributions()
        assert len(docs) == n_a + n_b
        assert {doc["source"] for doc in docs} == {str(provider_a), str(provider_b)}

        docs_a = registrar.list_contributions(provider_a)
        assert len(docs_a) == n_a
        assert all(doc["source"] == str(provider_a) for doc in docs_a)

        docs_b = registrar.list_contributions(provider_b)
        assert len(docs_b) == n_b
        assert all(doc["source"] == str(provider_b) for doc in docs_b)

        raw_a = {json.dumps(doc["raw"], sort_keys=True) for doc in docs_a}
        raw_b = {json.dumps(doc["raw"], sort_keys=True) for doc in docs_b}
        assert raw_a != raw_b
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)


def test_well_known_fails_stop_without_owning_collection(live_db):
    from yanantin.collector.storage.local.linux.synthetic import (
        SyntheticFilesystemCollector,
    )
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import Registrar
    from yanantin.recorder.storage.local.linux.registration import (
        LinuxStorageRegistration,
    )

    suffix = uuid4().hex
    catalog = f"RecorderCatalog_t{suffix}"
    minted = set()

    try:
        registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=catalog,
            name="linux-storage-catalog-only-recorder-registrar",
            description="catalog-only registrar must not host well_known mappings",
        )
        assert registrar.owns_owned_collection is False
        assert registrar.owns_edge_collection is False

        collector = SyntheticFilesystemCollector(seed=7)
        reg = LinuxStorageRegistration(registrar, collector)
        reg.register()
        snapshot = SyntheticFilesystemCollector(seed=7).collect()

        catalog_count_before = live_db.collection(catalog).count()
        before = {collection["name"] for collection in live_db.collections()}
        with pytest.raises(ValueError) as exc_info:
            reg.contribute_snapshot(snapshot, collector.get_provider_id())

        assert live_db.collection(catalog).count() == catalog_count_before

        message = str(exc_info.value).lower()
        assert "well_known" in message or (
            "own" in message and "collection" in message
        )

        after = {collection["name"] for collection in live_db.collections()}
        minted = after - before
        assert after == before
    finally:
        for name in minted:
            if live_db.has_collection(name):
                live_db.delete_collection(name)
        if live_db.has_collection(catalog):
            live_db.delete_collection(catalog)


def test_end_to_end_visible_through_cli(live_db):
    import json
    from contextlib import redirect_stdout
    from io import StringIO

    from yanantin.collector.storage.local.linux.synthetic import (
        SyntheticFilesystemCollector,
    )
    from yanantin.core.__main__ import main
    from yanantin.core.registration import RegistrationService
    from yanantin.recorder.storage.local.linux.registration import (
        LinuxStorageRegistration,
    )

    suffix = uuid4().hex
    catalog = f"CliCatalog_t{suffix}"
    objects = f"Objects_t{suffix}"
    relationships = f"Relationships_t{suffix}"

    try:
        svc = RegistrationService(
            db=live_db,
            catalog_collection=catalog,
            owned_collection=objects,
            owned_edge_collection=relationships,
        )
        collector = SyntheticFilesystemCollector(seed=7)
        reg = LinuxStorageRegistration(svc.base_registrar, collector)
        reg.register()

        snapshot = SyntheticFilesystemCollector(seed=7).collect()
        provider_id = collector.get_provider_id()
        n = reg.contribute_snapshot(snapshot, provider_id)

        out = StringIO()
        with redirect_stdout(out):
            main(["--json", "list"], service=svc)
        rows = json.loads(out.getvalue())

        recorder_row = next(
            row
            for row in rows
            if row["registrant_name"] == "linux-local-storage recorder"
        )
        assert recorder_row["contributes_to"] == [
            {"name": "Objects", "kind": "doc", "naming": "well_known"},
            {"name": "Relationships", "kind": "edge", "naming": "well_known"},
        ]

        collector_row = next(
            row for row in rows if row["registrant_id"] == str(provider_id)
        )
        assert n > 0
        assert collector_row["contributions"] == n
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)
