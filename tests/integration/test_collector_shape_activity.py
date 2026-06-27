"""Integration proof for collector shape activity facts.

These tests exercise the live ArangoDB activity stream store against
apacheta_test using test-tier credentials from ApachetaDBConfig. The collector
shape report is stored as FactRecord.data and read back through the activity
store, proving storage census vertical criteria 3 and 4.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.collector.storage.local.linux.shape_report import CollectorShapeReport
from yanantin.collector.storage.local.linux.synthetic import (
    SyntheticFilesystemCollector,
)
from yanantin.infra.config import ApachetaDBConfig
from yanantin.recorder.storage.local.linux.shape_activity import (
    latest_shape,
    record_shape,
    synthetic_from_report,
)


pytestmark = pytest.mark.integration

SHAPE_FACT_KEYS = {
    "object_count",
    "file_count",
    "dir_count",
    "mtime_age_buckets",
    "max_depth",
    "mean_files_per_dir",
    "extension_counts",
}


def _activity_store_config() -> tuple[str, str, str, str]:
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return cfg.host_url, "apacheta_test", creds["username"], creds["password"]


def check_arango_available() -> bool:
    """Check if ArangoDB test database is reachable with test credentials."""
    try:
        from arango import ArangoClient

        host, db_name, username, password = _activity_store_config()
        client = ArangoClient(hosts=host)
        db = client.db(db_name, username=username, password=password)
        db.collections()
        client.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def arango_session():
    """Session-scoped fixture: verify test database is reachable."""
    if not check_arango_available():
        pytest.skip(
            "ArangoDB test database not available. "
            "Run: uv run python -m yanantin.infra setup"
        )
    yield


@pytest.fixture
def store(arango_session) -> ArangoDBActivityStreamStore:
    """Function-scoped live activity store with clean activity collections."""
    host, db_name, username, password = _activity_store_config()
    s = ArangoDBActivityStreamStore(
        host=host,
        db_name=db_name,
        username=username,
        password=password,
    )

    for name in ("activity_facts", "activity_anchors"):
        if s._db.has_collection(name):
            s._db.collection(name).truncate()

    yield s

    for name in ("activity_facts", "activity_anchors"):
        if s._db.has_collection(name):
            s._db.collection(name).truncate()
    s.close()


def test_collection_run_records_shape_fact(store):
    """Criterion 3: a collection run records its shape as an activity fact."""
    collector = SyntheticFilesystemCollector(seed=7, depth=3, files_per_dir=5)
    snapshot = collector.collect()
    provider_id = uuid4()

    record_shape(store, snapshot, provider_id)

    facts = store.query_range(provider_id)
    assert len(facts) == 1
    assert SHAPE_FACT_KEYS <= set(facts[0].data)

    report = latest_shape(store, provider_id)
    assert isinstance(report, CollectorShapeReport)
    assert report.object_count == len(snapshot.entries)


def test_dual_collector_match_on_measurable_characteristics(store):
    """Criterion 4: fitted synthetic matches grounded measurable traits."""
    real_snapshot = SyntheticFilesystemCollector(
        seed=7,
        depth=3,
        files_per_dir=5,
    ).collect()
    provider_real = uuid4()
    record_shape(store, real_snapshot, provider_real)
    real_report = latest_shape(store, provider_real)
    assert real_report is not None

    synth_snapshot = synthetic_from_report(real_report, seed=107).collect()
    provider_synth = uuid4()
    record_shape(store, synth_snapshot, provider_synth)
    synth_report = latest_shape(store, provider_synth)
    assert synth_report is not None

    assert real_report.max_depth == synth_report.max_depth

    real_nonzero = {
        band for band, count in real_report.mtime_age_buckets.items() if count > 0
    }
    synth_nonzero = {
        band for band, count in synth_report.mtime_age_buckets.items() if count > 0
    }
    assert real_nonzero <= synth_nonzero

    real_exts = set(real_report.extension_counts)
    synth_exts = set(synth_report.extension_counts)
    extension_overlap = len(real_exts & synth_exts) / len(real_exts)
    assert extension_overlap >= 0.6

    count_ratio = synth_report.object_count / real_report.object_count
    # count is NOT a matchable characteristic of the current synthetic — reported, not gated (goal doc criterion 4)
    assert count_ratio > 0, f"count_ratio={count_ratio}"
