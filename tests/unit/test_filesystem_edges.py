"""Tests for provenance edges written by FilesystemFactRecorder."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID

from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.recorder.storage.local.linux.fact_recorder import FilesystemFactRecorder
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler

FAKE_MACHINE_ID = "8ae0edf526f3453ab1abaf04e1c75a4a"

# NOTE (deviation from plan): Task 4 (LinuxFilesystemCollector accepting an
# explicit machine_id kwarg) has NOT landed yet. Task 5 must not touch the
# collector. So instead of LinuxFilesystemCollector(path, machine_id=...),
# the collector is built normally with _get_machine_id patched to the fake id
# — this makes get_provider_id() deterministic in exactly the same way Task 4
# would, without depending on the unlanded kwarg.


def _make_collector(tmp_path):
    with patch(
        "yanantin.collector.storage.local.linux.collector._get_machine_id",
        return_value=FAKE_MACHINE_ID,
    ):
        return LinuxFilesystemCollector(tmp_path)


def _run_pipeline(tmp_path):
    """Collect a small real directory tree and record facts + edges."""
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.py").write_text("x = 1")

    store = InMemoryActivityStreamStore()
    backend = InMemoryBackend()

    collector = _make_collector(tmp_path)

    recorder = FilesystemFactRecorder(store, backend, machine_id=FAKE_MACHINE_ID)

    snapshot = collector.collect()
    envelope = WranglerEnvelope(data=snapshot, provider_id=collector.get_provider_id())

    wrangler = DirectWrangler()
    wrangler.deliver(envelope)
    received = wrangler.receive()
    fact_count = recorder.record_facts(received)
    return fact_count, store, backend, collector


def test_two_edges_per_fact(tmp_path):
    fact_count, store, backend, collector = _run_pipeline(tmp_path)
    edges = backend.list_provenance_edges()
    assert len(edges) == fact_count * 2


def test_contains_edges_from_machine(tmp_path):
    fact_count, store, backend, collector = _run_pipeline(tmp_path)
    edges = backend.list_provenance_edges()
    contains = [e for e in edges if e.relation_type == "contains"]
    assert len(contains) == fact_count
    for edge in contains:
        # Canonical entity-key form (str(UUID) — hyphenated) so the edge
        # resolves to the stored machine entity. Raw 32-hex would dangle.
        assert edge.from_ref == f"entities/{UUID(FAKE_MACHINE_ID)}"
        assert edge.to_ref.startswith("records/")


def test_collected_by_edges_from_provider(tmp_path):
    fact_count, store, backend, collector = _run_pipeline(tmp_path)
    edges = backend.list_provenance_edges()
    collected = [e for e in edges if e.relation_type == "collected_by"]
    assert len(collected) == fact_count
    provider_id = str(collector.get_provider_id())
    for edge in collected:
        assert edge.from_ref == f"entities/{provider_id}"
        assert edge.to_ref.startswith("records/")


def test_edge_to_ref_matches_stored_fact_id(tmp_path):
    """Edge _to UUIDs must match the IDs of stored facts.

    ActivityStreamStore has no get_all_facts; query_range over a wide
    window returns every fact. The window brackets the file mtimes.
    """
    fact_count, store, backend, collector = _run_pipeline(tmp_path)
    start = datetime(2000, 1, 1, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc) + timedelta(days=1)
    facts = store.query_range(collector.get_provider_id(), start=start, end=end)
    fact_ids = {str(f.id) for f in facts}
    edge_targets = {e.to_ref.split("/")[1] for e in backend.list_provenance_edges()}
    assert edge_targets == fact_ids


def test_backward_compat_no_backend(tmp_path):
    """FilesystemFactRecorder still works without backend — no edges written."""
    (tmp_path / "x.txt").write_text("hi")
    store = InMemoryActivityStreamStore()
    backend = InMemoryBackend()
    collector = _make_collector(tmp_path)
    recorder = FilesystemFactRecorder(store)  # no backend arg
    snapshot = collector.collect()
    envelope = WranglerEnvelope(data=snapshot, provider_id=collector.get_provider_id())
    wrangler = DirectWrangler()
    wrangler.deliver(envelope)
    received = wrangler.receive()
    count = recorder.record_facts(received)
    assert count > 0  # facts stored, no crash
    # A separate backend would have no edges; the recorder has none either.
    assert backend.list_provenance_edges() == []


def test_backward_compat_backend_without_machine_id(tmp_path):
    """Backend present but no machine_id => no edges (both required)."""
    (tmp_path / "y.txt").write_text("hi")
    store = InMemoryActivityStreamStore()
    backend = InMemoryBackend()
    collector = _make_collector(tmp_path)
    recorder = FilesystemFactRecorder(store, backend)  # no machine_id
    snapshot = collector.collect()
    envelope = WranglerEnvelope(data=snapshot, provider_id=collector.get_provider_id())
    wrangler = DirectWrangler()
    wrangler.deliver(envelope)
    received = wrangler.receive()
    count = recorder.record_facts(received)
    assert count > 0
    assert backend.list_provenance_edges() == []
