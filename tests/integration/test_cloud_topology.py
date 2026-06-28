from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.collector.storage.cloud.synthetic.collector import SyntheticCloudCollector
from yanantin.collector.storage.cloud.synthetic.models import CloudEntry
from yanantin.recorder.storage.cloud.synthetic.fact_recorder import CloudFactRecorder
from yanantin.recorder.storage.cloud.synthetic.monitor import StorageActivityMonitor
from yanantin.recorder.storage.cloud.synthetic.storage_recorder import (
    CloudStorageRecorder,
)


pytestmark = pytest.mark.integration


@pytest.fixture
def live_db():
    """A real StandardDatabase handle on apacheta_test (test-tier creds)."""
    from yanantin.infra.config import ApachetaDBConfig, get_database

    try:
        cfg = ApachetaDBConfig()
        creds = cfg.get_test_credentials()
        db = get_database(
            host=cfg.host_url,
            db_name="apacheta_test",
            username=creds["username"],
            password=creds["password"],
        )
        db.has_collection("__yanantin_connectivity_probe__")
    except Exception as exc:  # noqa: BLE001 - fixture should skip all DB failures.
        pytest.skip(f"apacheta_test live DB unavailable: {exc!r}")
    return db


def _make_registrar(live_db, *, suffix: str | None = None):
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import Registrar
    from yanantin.recorder.storage.objects_definition import OBJECTS_DEFINITION

    suffix = suffix or uuid4().hex
    catalog = f"CloudTopologyCatalog_t{suffix}"
    objects = f"Objects_t{suffix}"
    relationships = f"Relationships_t{suffix}"
    registrar = Registrar(
        db=live_db,
        khipu=Khipu(db=live_db),
        catalog_collection=catalog,
        name="cloud-topology-registrar",
        description="owns synthetic cloud topology test collections",
        owned_collection=objects,
        owned_edge_collection=relationships,
        owned_definition=OBJECTS_DEFINITION,
    )
    return registrar, (catalog, objects, relationships)


def _cleanup_collections(live_db, names: tuple[str, ...]) -> None:
    for name in names:
        if live_db.has_collection(name):
            live_db.delete_collection(name)


def _plan_nodes(live_db, query: str, bind_vars: dict) -> list[dict]:
    plan = live_db.aql.explain(query, bind_vars=bind_vars)
    if "nodes" in plan:
        return plan["nodes"]
    return plan["plan"]["nodes"]


def _entry_projection(entry: CloudEntry) -> tuple:
    return (
        entry.path,
        entry.name,
        entry.is_directory,
        entry.size,
        entry.content_hash,
        entry.modified,
        entry.change_type,
    )


def _doc_by_raw_path(registrar, provider_id: UUID) -> dict[str, dict]:
    return {
        doc["raw"]["path"]: doc
        for doc in registrar.list_contributions(provider_id)
    }


def test_phase_1_census_lands_ground_truth_objects_and_poll_records_facts(live_db):
    registrar, created = _make_registrar(live_db)
    collector = SyntheticCloudCollector(seed=11, total_entries=5, change_count=2)
    provider_id = collector.get_provider_id()
    store = InMemoryActivityStreamStore()
    monitor = StorageActivityMonitor(
        collector,
        CloudStorageRecorder(registrar),
        CloudFactRecorder(store),
    )

    try:
        expected_listing = SyntheticCloudCollector(
            seed=11, total_entries=5, change_count=2
        ).collect()

        assert monitor.census() == 5
        assert store.count_facts(provider_id) == 0
        assert live_db.collection(created[1]).count() == 5

        docs_by_path = _doc_by_raw_path(registrar, provider_id)
        assert set(docs_by_path) == {entry.path for entry in expected_listing.entries}

        for entry in expected_listing.entries:
            doc = docs_by_path[entry.path]
            raw = entry.model_dump(mode="json")
            assert doc["source"] == str(provider_id)
            assert doc["uri"] == f"cloud://synthetic-cloud-account{entry.path}"
            assert doc["label"] == entry.name
            assert doc["size"] == entry.size
            assert doc["modified"] == raw["modified"]
            assert doc["semantic_attributes"] == {
                "content_hash": entry.content_hash,
                "is_directory": entry.is_directory,
                "change_type": "unchanged",
            }
            assert doc["raw"] == raw

        result = monitor.poll()
        assert result.changes_seen == 2
        assert result.facts_recorded == 2
        assert store.count_facts(provider_id) == 2
        assert {
            fact.data["path"]
            for fact in store.query_range(provider_id)
        } == {
            entry.path
            for entry in SyntheticCloudCollector(
                seed=11, total_entries=5, change_count=2
            ).collect(cursor=expected_listing.cursor).entries
        }
    finally:
        _cleanup_collections(live_db, created)


def test_one_delta_fans_out_to_objects_and_activity_store(live_db):
    registrar, created = _make_registrar(live_db)
    collector = SyntheticCloudCollector(seed=19, total_entries=4, change_count=1)
    provider_id = collector.get_provider_id()
    store = InMemoryActivityStreamStore()
    monitor = StorageActivityMonitor(
        collector,
        CloudStorageRecorder(registrar),
        CloudFactRecorder(store),
    )

    try:
        assert monitor.census() == 4
        result = monitor.poll()

        assert result.changes_seen == 1
        assert result.objects_updated == 1
        assert result.facts_recorded == 1
        assert result.recollects == 1
        assert live_db.collection(created[1]).count() == 4
        assert store.count_facts(provider_id) == 1

        fact = store.query_latest(provider_id)
        assert fact is not None
        changed_path = fact.data["path"]
        assert fact.data["change_type"] == "modified"

        changed_doc = _doc_by_raw_path(registrar, provider_id)[changed_path]
        assert changed_doc["raw"]["path"] == changed_path
        assert changed_doc["raw"]["content_hash"] == fact.data["content_hash"]
        assert changed_doc["semantic_attributes"]["content_hash"] == fact.data[
            "content_hash"
        ]
        assert changed_doc["semantic_attributes"]["change_type"] == "unchanged"
        assert changed_doc["source"] == str(provider_id)
    finally:
        _cleanup_collections(live_db, created)


class CountingCollector(SyntheticCloudCollector):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.recollect_paths: list[str] = []

    def recollect_one(self, path: str) -> CloudEntry | None:
        self.recollect_paths.append(path)
        return super().recollect_one(path)


@dataclass
class RecordingStorage:
    updates: list[tuple[CloudEntry, UUID, str]] = field(default_factory=list)

    def update_object(self, entry: CloudEntry, *, source: UUID, account_id: str) -> UUID:
        self.updates.append((entry, source, account_id))
        return uuid4()


@dataclass
class RecordingFacts:
    changes: list[tuple[CloudEntry, UUID]] = field(default_factory=list)

    def record_change(self, entry: CloudEntry, *, provider_id: UUID) -> UUID:
        self.changes.append((entry, provider_id))
        return uuid4()


def test_feedback_edge_terminates_in_exact_seeded_cycles():
    change_count = 4
    collector = CountingCollector(seed=23, total_entries=9, change_count=change_count)
    storage = RecordingStorage()
    facts = RecordingFacts()
    monitor = StorageActivityMonitor(collector, storage, facts)

    assert monitor.census() == 9
    storage.updates.clear()

    results = monitor.poll_until_quiet(max_cycles=2)

    assert len(results) == 2
    assert results[0].changes_seen == change_count
    assert results[0].objects_updated == change_count
    assert results[0].facts_recorded == change_count
    assert results[0].recollects == change_count
    assert results[0].has_more is False
    assert results[1].changes_seen == 0
    assert results[1].objects_updated == 0
    assert results[1].facts_recorded == 0
    assert results[1].recollects == 0
    assert results[1].has_more is False

    assert len(collector.recollect_paths) == change_count
    assert len(storage.updates) == change_count
    assert len(facts.changes) == change_count
    assert [entry.path for entry, _, _ in storage.updates] == collector.recollect_paths
    assert [entry.change_type for entry, _, _ in storage.updates] == [
        "unchanged"
    ] * change_count


def test_repeated_updates_to_same_cloud_file_replace_one_objects_doc(live_db):
    registrar, created = _make_registrar(live_db)
    collector = SyntheticCloudCollector(seed=31, total_entries=3, change_count=0)
    provider_id = collector.get_provider_id()
    recorder = CloudStorageRecorder(registrar)
    base = collector.collect().entries[0]
    second = base.model_copy(
        update={
            "size": base.size + 10,
            "content_hash": "second-content-hash",
            "modified": base.modified + timedelta(days=1),
            "change_type": "modified",
        }
    )
    third = base.model_copy(
        update={
            "size": base.size + 20,
            "content_hash": "third-content-hash",
            "modified": base.modified + timedelta(days=2),
            "change_type": "modified",
        }
    )

    try:
        ids = [
            recorder.update_object(entry, source=provider_id, account_id="acct-idem")
            for entry in (base, second, third)
        ]

        assert ids[0] == ids[1] == ids[2]
        assert live_db.collection(created[1]).count() == 1

        docs = registrar.list_contributions(provider_id)
        assert len(docs) == 1
        doc = docs[0]
        assert doc["object_identifier"] == str(ids[0])
        assert doc["uri"] == f"cloud://acct-idem{base.path}"
        assert doc["size"] == third.size
        assert doc["modified"] == third.model_dump(mode="json")["modified"]
        assert doc["semantic_attributes"]["content_hash"] == "third-content-hash"
        assert doc["raw"]["content_hash"] == "third-content-hash"
        assert doc["raw"]["change_type"] == "modified"
    finally:
        _cleanup_collections(live_db, created)


def test_cloud_objects_query_reuses_modified_index(live_db):
    registrar, created = _make_registrar(live_db)
    collector = SyntheticCloudCollector(seed=41, total_entries=3, change_count=0)
    provider_id = collector.get_provider_id()
    recorder = CloudStorageRecorder(registrar)
    listing = collector.collect()
    in_window = listing.entries[0]
    after_window = listing.entries[1].model_copy(
        update={"modified": in_window.modified + timedelta(hours=3)}
    )
    before_window = listing.entries[2].model_copy(
        update={"modified": in_window.modified - timedelta(hours=3)}
    )
    t0 = in_window.modified - timedelta(minutes=1)
    t1 = in_window.modified + timedelta(minutes=1)
    query = (
        f"FOR d IN `{created[1]}` "
        "FILTER d.modified >= @t0 "
        "FILTER d.modified < @t1 "
        "RETURN d.label"
    )
    bind_vars = {
        "t0": t0.isoformat(),
        "t1": t1.isoformat(),
    }

    try:
        for entry in (in_window, after_window, before_window):
            recorder.update_object(
                entry,
                source=provider_id,
                account_id="synthetic-cloud-account",
            )

        index_names = {index["name"] for index in live_db.collection(created[1]).indexes()}
        assert "idx_objects_modified" in index_names
        assert list(live_db.aql.execute(query, bind_vars=bind_vars)) == [
            in_window.name
        ]

        node_types = {
            node["type"]
            for node in _plan_nodes(live_db, query, bind_vars)
        }
        assert "IndexNode" in node_types, node_types
        assert "EnumerateCollectionNode" not in node_types, node_types
    finally:
        _cleanup_collections(live_db, created)


def test_same_seed_yields_identical_census_and_delta():
    left = SyntheticCloudCollector(seed=53, total_entries=7, change_count=3)
    right = SyntheticCloudCollector(seed=53, total_entries=7, change_count=3)

    left_listing = left.collect()
    right_listing = right.collect()

    assert left_listing.account_id == right_listing.account_id
    assert left_listing.cursor == right_listing.cursor
    assert [_entry_projection(e) for e in left_listing.entries] == [
        _entry_projection(e) for e in right_listing.entries
    ]

    left_delta = left.collect(cursor=left_listing.cursor)
    right_delta = right.collect(cursor=right_listing.cursor)

    assert left_delta.account_id == right_delta.account_id
    assert left_delta.cursor == right_delta.cursor
    assert left_delta.has_more == right_delta.has_more
    assert [_entry_projection(e) for e in left_delta.entries] == [
        _entry_projection(e) for e in right_delta.entries
    ]
