"""Dual-collector interchangeability proof at the recorder boundary (gh #27).

FALSIFIABLE PROPERTY: one FilesystemRecorder instance, fed a
WranglerEnvelope[FilesystemSnapshot] from the REAL collector
(LinuxFilesystemCollector over a tmp dir) and one from the SYNTHETIC
collector (SyntheticFilesystemCollector), must (a) both succeed via the
identical record() code path, (b) produce TensorRecords structurally
indistinguishable in every field the RECORDER controls, and (c) differ
ONLY in fields that are functions of the input DATA — never of the
input's provenance-as-a-collector. The recorder never branches on
collector type: it imports only the data model (FilesystemSnapshot).

Per the no-mock-databases rule these run against the live apacheta_test
database — store_tensor truly writes to ArangoDB and get_tensor truly
reads back. Every assertion is made on the ROUND-TRIPPED tensor, not the
in-memory object: round-trip through live storage is the point.

Fixture credentials follow test_core_registration.py (config-cred,
ApachetaDBConfig().get_test_credentials()), NOT the env-var pattern
(empty in this environment → 401). The shared `tensors` collection is
NEVER truncated — teardown deletes exactly the two tensors created, by id.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.collector.storage.local.linux.models import FileEntryData
from yanantin.collector.storage.local.linux.synthetic import (
    SyntheticFilesystemCollector,
)
from yanantin.infra.config import ApachetaDBConfig
from yanantin.recorder.base import RecorderBase
from yanantin.recorder.storage.local.linux.recorder import FilesystemRecorder
from yanantin.transport.models import WranglerEnvelope


pytestmark = pytest.mark.integration


@pytest.fixture
def interface():
    """A real ArangoDBBackend over live apacheta_test (test-tier creds).

    The recorder's store_tensor truly hits ArangoDB and get_tensor truly
    reads it back. Teardown deletes ONLY the tensors this test created, by
    id — apacheta_test's `tensors` collection is shared, so truncation
    would be collateral damage.
    """
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    be = ArangoDBBackend(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )
    created: list = []
    be._created_tensor_ids = created  # test records ids it must clean up
    try:
        yield be
    finally:
        for tid in created:
            try:
                be._db.collection("tensors").delete(str(tid))
            except Exception:  # noqa: BLE001 — best-effort surgical cleanup
                pass
        be.close()


@pytest.fixture
def tmp_tree(tmp_path: Path) -> Path:
    """A real directory with one file and one subdir.

    Nonzero total_files and total_dirs exercise the FilesystemSnapshot
    validator (total_files + total_dirs == len(entries)) on REAL data.
    """
    (tmp_path / "note.txt").write_text("hello dual-collector proof\n")
    (tmp_path / "sub").mkdir()
    return tmp_path


def _record_both(interface, tmp_tree):
    """Build two envelopes from two collectors, record both through ONE
    recorder instance, return the round-tripped tensors and the collectors."""
    real = LinuxFilesystemCollector(Path(tmp_tree))  # MUST be Path (.resolve())
    syn = SyntheticFilesystemCollector(seed=7)
    rec = FilesystemRecorder(interface)  # the SAME instance for both

    env_r = WranglerEnvelope(data=real.collect(), provider_id=real.get_provider_id())
    env_s = WranglerEnvelope(data=syn.collect(), provider_id=syn.get_provider_id())

    tid_r = rec.record(env_r)
    tid_s = rec.record(env_s)
    interface._created_tensor_ids.extend([tid_r, tid_s])

    tr = interface.get_tensor(tid_r)
    ts = interface.get_tensor(tid_s)
    return rec, real, syn, env_r, env_s, tid_r, tid_s, tr, ts


def test_both_sources_store_and_return_uuid(interface, tmp_tree):
    """Both sources record successfully and round-trip: distinct UUIDs,
    both retrievable from live storage (no NotFoundError)."""
    _, _, _, _, _, tid_r, tid_s, tr, ts = _record_both(interface, tmp_tree)

    assert tid_r != tid_s
    # get_tensor already succeeded in the helper; reconfirm identity round-trip.
    assert interface.get_tensor(tid_r).id == tid_r
    assert interface.get_tensor(tid_s).id == tid_s
    assert tr.id == tid_r
    assert ts.id == tid_s


def test_recorder_controlled_fields_are_identical(interface, tmp_tree):
    """The indistinguishability core: every field the recorder controls is
    identical across the real and synthetic round-tripped tensors."""
    _, _, _, _, _, _, _, tr, ts = _record_both(interface, tmp_tree)

    # Strand structure: count, titles, topics.
    assert len(tr.strands) == len(ts.strands) == 2
    assert (
        [s.title for s in tr.strands]
        == [s.title for s in ts.strands]
        == ["Filesystem Snapshot Summary", "Filesystem Entries"]
    )
    assert [s.topics for s in tr.strands] == [s.topics for s in ts.strands]

    # Author model family and source description.
    assert (
        tr.provenance.author_model_family
        == ts.provenance.author_model_family
        == "collector"
    )
    assert (
        tr.provenance.source.description
        == ts.provenance.source.description
        == "Filesystem metadata collector"
    )

    # lineage_tags shape: filesystem + snapshot present, exactly one content tag
    # of 16 hex chars, in both.
    for tags in (tr.lineage_tags, ts.lineage_tags):
        assert "filesystem" in tags
        assert "snapshot" in tags
        content_tags = [t for t in tags if t.startswith("content:")]
        assert len(content_tags) == 1
        hexpart = content_tags[0].split("content:", 1)[1]
        assert len(hexpart) == 16
        int(hexpart, 16)  # raises ValueError if not hex


def test_provenance_tracks_provider_not_recorder(interface, tmp_tree):
    """provenance.source.identifier follows the envelope's provider_id — the
    ONE legitimate per-source delta — while everything else is shared."""
    _, real, syn, _, _, _, _, tr, ts = _record_both(interface, tmp_tree)

    assert tr.provenance.source.identifier == real.get_provider_id()
    assert ts.provenance.source.identifier == syn.get_provider_id()
    assert real.get_provider_id() != syn.get_provider_id()


def test_recorder_identity_is_source_independent(interface, tmp_tree):
    """The recorder id is an instance attribute, stable across both records,
    and is the deterministic uuid5 — never a function of the source."""
    from uuid import NAMESPACE_DNS, uuid5

    rec, _, _, _, _, _, _, _, _ = _record_both(interface, tmp_tree)

    expected = uuid5(NAMESPACE_DNS, "yanantin.recorder.filesystem")
    assert rec.get_recorder_id() == expected


def test_data_strands_validate_back_to_model_for_both(interface, tmp_tree):
    """The lossless data path is collector-agnostic at the storage round-trip:
    the entries strand's JSON validates back to FileEntryData for BOTH the
    real and synthetic payloads."""
    _, _, _, _, _, _, _, tr, ts = _record_both(interface, tmp_tree)

    for tensor in (tr, ts):
        entries = json.loads(tensor.strands[1].content)
        assert entries, "expected at least one entry"
        FileEntryData.model_validate(entries[0])


def test_content_hashes_differ(interface, tmp_tree):
    """Anti-tautology guard: the two inputs are genuinely different data, so
    leg 2's 'identical structure' is a real interchangeability result rather
    than identical input trivially producing identical output."""
    _, _, _, env_r, env_s, _, _, _, _ = _record_both(interface, tmp_tree)

    assert RecorderBase._content_hash(env_r.data) != RecorderBase._content_hash(
        env_s.data
    )
