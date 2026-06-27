from collections import Counter
from datetime import datetime, timezone
from uuid import uuid4, uuid5

import pytest

from yanantin.collector.storage.local.linux.models import (
    FileEntryData,
    FilesystemSnapshot,
    FileTimestamps,
)


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


def test_recontributing_snapshot_does_not_duplicate_contains_edges(live_db):
    from yanantin.collector.storage.local.linux.synthetic import (
        SyntheticFilesystemCollector,
    )
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import Registrar
    from yanantin.recorder.storage.local.linux.normalize import NAMESPACE
    from yanantin.recorder.storage.local.linux.registration import (
        LinuxStorageRegistration,
    )

    suffix = uuid4().hex
    catalog = f"EdgeIdempotenceCatalog_t{suffix}"
    objects = f"Objects_t{suffix}"
    relationships = f"Relationships_t{suffix}"

    ts = FileTimestamps(
        created=datetime.now(timezone.utc),
        modified=datetime.now(timezone.utc),
        accessed=datetime.now(timezone.utc),
        changed=datetime.now(timezone.utc),
    )
    parent_dir = FileEntryData(
        path="/synthetic/root",
        name="root",
        uri="file:///synthetic/root",
        is_directory=True,
        is_symlink=False,
        size=4096,
        mode=0o40755,
        file_attributes=("S_IFDIR", "S_IRUSR"),
        timestamps=ts,
        link_target=None,
    )
    child_a = FileEntryData(
        path="/synthetic/root/a.txt",
        name="a.txt",
        uri="file:///synthetic/root/a.txt",
        is_directory=False,
        is_symlink=False,
        size=10,
        mode=33188,
        file_attributes=("S_IFREG", "S_IRUSR"),
        timestamps=ts,
        link_target=None,
    )
    child_b = FileEntryData(
        path="/synthetic/root/b.txt",
        name="b.txt",
        uri="file:///synthetic/root/b.txt",
        is_directory=False,
        is_symlink=False,
        size=20,
        mode=33188,
        file_attributes=("S_IFREG", "S_IRUSR"),
        timestamps=ts,
        link_target=None,
    )
    snapshot = FilesystemSnapshot(
        root_path="/synthetic/root",
        entries=(parent_dir, child_a, child_b),
        total_files=2,
        total_dirs=1,
        error_count=0,
    )

    try:
        registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=catalog,
            name="edge-idempotence-registrar",
            description="owns edge idempotence regression collections",
            owned_collection=objects,
            owned_edge_collection=relationships,
        )
        reg = LinuxStorageRegistration(
            registrar,
            SyntheticFilesystemCollector(seed=1),
        )
        reg.register()
        provider = uuid4()

        reg.contribute_snapshot(snapshot, provider)
        edges_after_first = registrar.list_edge_contributions(reg.recorder_id)
        contains_after_first = [
            e for e in edges_after_first if e["relation_type"] == "contains"
        ]
        records_after_first = [
            e for e in edges_after_first if e["relation_type"] == "records"
        ]

        reg.contribute_snapshot(snapshot, provider)
        edges_after_second = registrar.list_edge_contributions(reg.recorder_id)
        contains_after_second = [
            e for e in edges_after_second if e["relation_type"] == "contains"
        ]
        records_after_second = [
            e for e in edges_after_second if e["relation_type"] == "records"
        ]

        assert len(contains_after_first) == 2
        assert len(contains_after_second) == len(contains_after_first)
        assert len(records_after_first) == len(snapshot.entries)
        assert len(records_after_second) == len(records_after_first)

        parent_key = str(uuid5(NAMESPACE, f"{provider}:file:///synthetic/root"))
        child_keys = [
            str(uuid5(NAMESPACE, f"{provider}:file:///synthetic/root/a.txt")),
            str(uuid5(NAMESPACE, f"{provider}:file:///synthetic/root/b.txt")),
        ]

        rel_field = registrar._obfuscator.field_name("relation_type")

        reached = list(
            live_db.aql.execute(
                f"FOR v, e IN 1..1 OUTBOUND @start `{relationships}` "
                "FILTER e[@rel_field] == @contains "
                "RETURN v._key",
                bind_vars={
                    "start": f"{objects}/{parent_key}",
                    "rel_field": rel_field,
                    "contains": "contains",
                },
            )
        )

        assert Counter(reached) == Counter(child_keys)
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)
