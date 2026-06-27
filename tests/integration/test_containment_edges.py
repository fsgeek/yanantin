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


def test_containment_edge_outbound_reaches_child(live_db):
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
    catalog = f"ContainmentCatalog_t{suffix}"
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
    child_file = FileEntryData(
        path="/synthetic/root/main.py",
        name="main.py",
        uri="file:///synthetic/root/main.py",
        is_directory=False,
        is_symlink=False,
        size=10,
        mode=33188,
        file_attributes=("S_IFREG", "S_IRUSR"),
        timestamps=ts,
        link_target=None,
    )
    snapshot = FilesystemSnapshot(
        root_path="/synthetic/root",
        entries=(parent_dir, child_file),
        total_files=1,
        total_dirs=1,
        error_count=0,
    )

    try:
        registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=catalog,
            name="containment-edge-registrar",
            description="owns containment edge regression collections",
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

        parent_key = str(uuid5(NAMESPACE, f"{provider}:file:///synthetic/root"))
        child_key = str(
            uuid5(NAMESPACE, f"{provider}:file:///synthetic/root/main.py")
        )

        # relation_type is an obfuscated FIELD NAME at rest — filter via the
        # registrar's obfuscator so the query speaks storage's labels
        # (mirror list_edge_contributions).
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

        # child reached -> edge does NOT dangle (raw-hex key would yield [])
        assert reached == [child_key]
        # no self/parent loop
        assert parent_key not in reached
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)
