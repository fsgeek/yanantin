"""Red bar: temporal Objects queries must be view- or index-backed.

The current Objects temporal-window AQL enumerates the collection. This test is
intentionally red until the production query path is backed by an ArangoSearch
view or an index-backed plan node instead of a full collection scan.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from yanantin.collector.storage.local.linux.models import (
    FileEntryData,
    FilesystemSnapshot,
    FileTimestamps,
)


pytestmark = pytest.mark.integration


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


def _plan_nodes(live_db, query: str, bind_vars: dict) -> list[dict]:
    plan = live_db.aql.explain(query, bind_vars=bind_vars)
    if "nodes" in plan:
        return plan["nodes"]
    return plan["plan"]["nodes"]


def test_objects_temporal_window_query_plan_is_view_or_index_backed(live_db):
    from yanantin.collector.storage.local.linux.synthetic import (
        SyntheticFilesystemCollector,
    )
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import Registrar
    from yanantin.recorder.storage.local.linux.registration import (
        OBJECTS_DEFINITION,
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

    in_window = "objects-query-window-0130.md"
    after_window = "objects-query-window-0300.md"
    today_file = "objects-query-today.md"
    entries = (
        file_entry(in_window, yesterday + timedelta(hours=1, minutes=30)),
        file_entry(after_window, yesterday + timedelta(hours=3)),
        file_entry(today_file, today + timedelta(hours=1)),
    )
    snapshot = FilesystemSnapshot(
        root_path="/synthetic/root",
        entries=entries,
        total_files=3,
        total_dirs=0,
        error_count=0,
    )

    query = (
        f"FOR d IN `{objects}` "
        "FILTER d.modified >= @t0 "
        "FILTER d.modified < @t1 "
        "FILTER d.label LIKE @label "
        "RETURN d.label"
    )
    bind_vars = {
        "t0": t0.isoformat(),
        "t1": t1.isoformat(),
        "label": "%.md",
    }

    try:
        registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=catalog,
            name="objects-query-plan-registrar",
            description="owns Objects query-plan regression collections",
            owned_collection=objects,
            owned_edge_collection=relationships,
            owned_definition=OBJECTS_DEFINITION,
        )
        reg = LinuxStorageRegistration(
            registrar,
            SyntheticFilesystemCollector(seed=1),
        )
        reg.register()
        provider = uuid4()
        reg.contribute_snapshot(snapshot, provider)

        names = list(live_db.aql.execute(query, bind_vars=bind_vars))
        assert names == [in_window]

        node_types = {
            node["type"]
            for node in _plan_nodes(live_db, query, bind_vars)
        }
        view_node_types = {"EnumerateViewNode", "IResearchViewNode"}
        index_node_types = {
            node_type for node_type in node_types if "Index" in node_type
        }

        assert "EnumerateCollectionNode" not in node_types, node_types
        assert node_types & view_node_types or index_node_types, node_types
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)
