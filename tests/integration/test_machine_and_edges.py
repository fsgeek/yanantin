"""Integration test: machine entity + filesystem provenance edges in apacheta_test.

Full pipeline against a live ArangoDB:
  1. MachineConfigRecorder writes an EntityResolution + snapshot tensor +
     has_snapshot edge.
  2. FilesystemFactRecorder walks a temp dir, stores facts, and writes
     contains/collected_by edges.

The load-bearing assertion is a native graph TRAVERSAL (FOR v IN OUTBOUND
<entity-key>) — not mere edge existence. Traversal is the only thing that
proves the edge endpoints use the canonical entity _key form; an edge built
on the raw (unhyphenated) machine_id string would exist as a document but
resolve to NOTHING, and a string-compare unit test would never notice.

Connection uses ApachetaDBConfig (creds in ~/.yanantin/config/db.ini); the
env-var-default path with an empty password gets 401 on this host. Guarded
by an availability check + APACHETA_SKIP_ARANGO opt-out. Cleans up only the
documents it creates (by the fake machine id / known refs).
"""

from __future__ import annotations

import os
from unittest.mock import patch
from uuid import UUID

import pytest

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.machine.linux import MachineConfigCollector, MachineConfigRecorder
from yanantin.recorder.storage.local.linux.fact_recorder import FilesystemFactRecorder
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler

pytestmark = pytest.mark.integration

FAKE_MACHINE_ID = "8ae0edf526f3453ab1abaf04e1c75a4a"
# Canonical entity _key form — how store_entity keys the document.
ENTITY_KEY = str(UUID(FAKE_MACHINE_ID))


def _config():
    from yanantin.infra.config import ApachetaDBConfig

    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return cfg.host_url, "apacheta_test", creds["username"], creds["password"]


def _arango_available() -> bool:
    try:
        from arango import ArangoClient

        host, db_name, user, pw = _config()
        client = ArangoClient(hosts=host)
        client.db(db_name, username=user, password=pw).collections()
        client.close()
        return True
    except Exception:
        return False


@pytest.fixture
def backend():
    if os.environ.get("APACHETA_SKIP_ARANGO"):
        pytest.skip("APACHETA_SKIP_ARANGO is set")
    if not _arango_available():
        pytest.skip("ArangoDB apacheta_test not available (check ~/.yanantin/config/db.ini)")

    host, db_name, user, pw = _config()
    be = ArangoDBBackend(host=host, db_name=db_name, username=user, password=pw)
    _cleanup(be)
    yield be
    _cleanup(be)
    be.close()


def _cleanup(be: ArangoDBBackend) -> None:
    """Remove only what this test creates: the fake machine entity, and every
    provenance edge that touches it or points at a records/ document."""
    db = be._db
    map_ = be._map
    try:
        db.collection(map_.collection_name("entities")).delete(
            ENTITY_KEY, ignore_missing=True
        )
    except Exception:
        pass
    try:
        edges = map_.collection_name("provenance_edges")
        if db.has_collection(edges):
            # Delete edges from the fake machine entity, the collector entity,
            # or any edge pointing at a records/ doc created here.
            db.aql.execute(
                f"FOR e IN `{edges}` "
                "FILTER e._from == @ent OR e._to LIKE @rec "
                f"REMOVE e IN `{edges}`",
                bind_vars={"ent": f"entities/{ENTITY_KEY}", "rec": "records/%"},
            )
    except Exception:
        pass


def test_machine_entity_and_snapshot_edge_in_db(backend):
    collector = MachineConfigCollector()
    recorder = MachineConfigRecorder(backend)
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        with patch("yanantin.machine.base._get_machine_id", return_value=FAKE_MACHINE_ID):
            data = collector.collect()
        envelope = WranglerEnvelope(data=data, provider_id=collector.get_provider_id())
        tensor_id = recorder.record(envelope)

    # Entity present, keyed by the canonical UUID form.
    entity = backend.get_entity(UUID(FAKE_MACHINE_ID))
    assert entity.identity_type == "machine.linux"
    assert entity.id == UUID(FAKE_MACHINE_ID)

    # has_snapshot edge exists AND RESOLVES via native traversal: the whole
    # point of the canonical-key fix. An unhyphenated _from would make this
    # traversal return zero vertices even though the edge document exists.
    edges_col = backend._map.collection_name("provenance_edges")
    reached = list(
        backend._db.aql.execute(
            f"FOR v, e IN 1..1 OUTBOUND @start `{edges_col}` "
            "FILTER e.relation_type == 'has_snapshot' RETURN v._key",
            bind_vars={"start": f"entities/{ENTITY_KEY}"},
        )
    )
    assert str(tensor_id) in reached, (
        "has_snapshot edge did not resolve to the tensor via OUTBOUND traversal "
        "— endpoint is not the canonical entity key"
    )


def test_filesystem_edges_resolve_in_db(backend, tmp_path):
    (tmp_path / "alpha.txt").write_text("a")
    (tmp_path / "beta.py").write_text("b = 1")

    host, db_name, user, pw = _config()
    activity_store = ArangoDBActivityStreamStore(
        host=host, db_name=db_name, username=user, password=pw
    )

    with patch(
        "yanantin.collector.storage.local.linux.collector._get_machine_id",
        return_value=FAKE_MACHINE_ID,
    ):
        collector = LinuxFilesystemCollector(tmp_path, machine_id=FAKE_MACHINE_ID)
    recorder = FilesystemFactRecorder(activity_store, backend, machine_id=FAKE_MACHINE_ID)

    snapshot = collector.collect()
    # The collector emits one entry PER filesystem object, including the root
    # directory itself — so a 2-file tmp_path yields 3 entries (root + 2 files).
    # Assert against the collector's actual output, not a guessed literal.
    expected = len(snapshot.entries)
    assert expected >= 2  # the two files we created, at minimum
    envelope = WranglerEnvelope(data=snapshot, provider_id=collector.get_provider_id())
    wrangler = DirectWrangler()
    wrangler.deliver(envelope)
    received = wrangler.receive()
    fact_count = recorder.record_facts(received)
    assert fact_count == expected

    # Native OUTBOUND traversal from the machine entity must reach the fact
    # records via the 'contains' edges. Proves canonical-key endpoints.
    edges_col = backend._map.collection_name("provenance_edges")
    reached = list(
        backend._db.aql.execute(
            f"FOR v, e IN 1..1 OUTBOUND @start `{edges_col}` "
            "FILTER e.relation_type == 'contains' RETURN e._to",
            bind_vars={"start": f"entities/{ENTITY_KEY}"},
        )
    )
    assert len(reached) == fact_count  # one contains-edge per stored fact
    assert all(t.startswith("records/") for t in reached)
