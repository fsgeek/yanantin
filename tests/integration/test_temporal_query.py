from datetime import datetime, timedelta, timezone
from uuid import uuid4

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


def test_temporal_range_query_returns_in_window_files(live_db):
    from yanantin.collector.storage.local.linux.synthetic import (
        SyntheticFilesystemCollector,
    )
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import Registrar
    from yanantin.recorder.storage.local.linux.registration import (
        LinuxStorageRegistration,
    )

    suffix = uuid4().hex
    catalog = f"TemporalCatalog_t{suffix}"
    objects = f"Objects_t{suffix}"
    relationships = f"Relationships_t{suffix}"

    today = datetime.now(timezone.utc).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    yesterday = today - timedelta(days=1)
    t0 = yesterday + timedelta(hours=1)
    t1 = yesterday + timedelta(hours=2)

    def file_entry(name: str, modified: datetime) -> FileEntryData:
        timestamps = FileTimestamps(
            created=modified,
            modified=modified,
            accessed=modified,
            changed=modified,
        )
        return FileEntryData(
            path=f"/synthetic/root/{name}",
            name=name,
            uri=f"file:///synthetic/root/{name}",
            is_directory=False,
            is_symlink=False,
            size=1,
            mode=33188,
            file_attributes=("S_IFREG", "S_IRUSR"),
            timestamps=timestamps,
            link_target=None,
        )

    in_window = "changed-yesterday-0130.txt"
    after_window = "changed-yesterday-0300.txt"
    today_file = "changed-today.txt"
    at_upper_boundary = "changed-yesterday-0200.txt"
    entries = (
        file_entry(in_window, yesterday + timedelta(hours=1, minutes=30)),
        file_entry(after_window, yesterday + timedelta(hours=3)),
        file_entry(today_file, today + timedelta(hours=1)),
        file_entry(at_upper_boundary, t1),
    )
    snapshot = FilesystemSnapshot(
        root_path="/synthetic/root",
        entries=entries,
        total_files=4,
        total_dirs=0,
        error_count=0,
    )

    try:
        registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=catalog,
            name="temporal-query-registrar",
            description="owns temporal query regression collections",
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

        names = list(
            live_db.aql.execute(
                f"FOR d IN `{objects}` "
                "FILTER d.raw.timestamps.modified >= @t0 "
                "FILTER d.raw.timestamps.modified < @t1 "
                "RETURN d.raw.name",
                bind_vars={"t0": t0.isoformat(), "t1": t1.isoformat()},
            )
        )

        assert names == [in_window]
        assert after_window not in names
        assert today_file not in names
        assert at_upper_boundary not in names
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)
