"""Red bars for the full-corpus batch landing path.

Contract source:
docs/superpowers/plans/2026-07-03-full-corpus-landing-batch-path.md

These tests are intentionally born red. They exercise the not-yet-built
streaming collector API, Registrar batch contribution APIs, batch-layer
idempotence, and the throughput gate that must be asserted by the landing
harness. Live DB tests use apacheta_test with config-file credentials and skip
narrowly when that disposable database is unreachable.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID, uuid4, uuid5

import pytest

from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.collector.storage.local.linux.models import (
    FileEntryData,
    FilesystemSnapshot,
)
from yanantin.core.khipu import Khipu
from yanantin.core.registration import Registrar
from yanantin.recorder.storage.local.linux.normalize import (
    NAMESPACE,
    normalize_file_entry,
)
from yanantin.recorder.storage.local.linux.registration import (
    CONTAINS_RELATION,
    RECORDER_ID,
)


def _fixture_tree(root: Path) -> Path:
    (root / "pkg" / "sub").mkdir(parents=True)
    (root / "pkg" / "a.py").write_text("a\n", encoding="utf-8")
    (root / "pkg" / "sub" / "b.txt").write_text("b\n", encoding="utf-8")
    (root / "README.md").write_text("# fixture\n", encoding="utf-8")
    return root


def _entry_projection(entries: tuple[FileEntryData, ...]) -> dict[str, tuple]:
    return {
        entry.uri: (
            entry.is_directory,
            entry.is_symlink,
            entry.size,
            entry.mode,
            entry.file_attributes,
            entry.link_target,
        )
        for entry in entries
    }


@pytest.fixture(scope="session")
def live_db():
    """A real StandardDatabase handle on apacheta_test, or a narrow skip."""
    if os.environ.get("APACHETA_SKIP_ARANGO"):
        pytest.skip("APACHETA_SKIP_ARANGO is set")

    from yanantin.infra.config import ApachetaDBConfig, get_database

    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    try:
        db = get_database(
            host=cfg.host_url,
            db_name="apacheta_test",
            username=creds["username"],
            password=creds["password"],
        )
        db.collections()
    except Exception as exc:  # noqa: BLE001 - fixture must skip all DB failures.
        pytest.skip(
            "Live ArangoDB apacheta_test is unreachable from this environment "
            f"(check ~/.yanantin/config/db.ini): {exc!r}"
        )
    return db


def _clean_doc(db, collection: str, key: str) -> dict:
    doc = db.collection(collection).get(key)
    assert doc is not None
    return {k: v for k, v in doc.items() if not k.startswith("_")}


def test_stream_entries_matches_collect_without_exposing_full_tree_list(
    tmp_path: Path,
) -> None:
    root = _fixture_tree(tmp_path)
    collector = LinuxFilesystemCollector(root, machine_id="stream-red-bar")

    snapshot = collector.collect()
    stream = collector.stream_entries()

    assert not isinstance(stream, (list, tuple, FilesystemSnapshot))
    streamed_entries = tuple(stream)

    assert _entry_projection(streamed_entries) == _entry_projection(snapshot.entries)


@pytest.mark.integration
def test_contribute_many_lands_same_attributed_object_shape_as_singular(
    live_db,
) -> None:
    suffix = uuid4().hex
    singular_catalog = f"BatchParitySingularCatalog_t{suffix}"
    singular_objects = f"BatchParitySingularObjects_t{suffix}"
    batch_catalog = f"BatchParityBatchCatalog_t{suffix}"
    batch_objects = f"BatchParityBatchObjects_t{suffix}"
    contributor_id = uuid4()
    key = uuid4().hex
    fields = {
        "_key": key,
        "uri": "file:///batch/parity/same.txt",
        "label": "same.txt",
        "size": 123,
        "semantic_attributes": {"mode": 33188, "file_attributes": ["S_IFREG"]},
        "raw": {"fixture": "same input"},
    }

    try:
        singular = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=singular_catalog,
            name="batch-parity-singular",
            description="singular side of batch parity test",
            owned_collection=singular_objects,
        )
        batch = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=batch_catalog,
            name="batch-parity-batch",
            description="batch side of batch parity test",
            owned_collection=batch_objects,
        )
        for registrar in (singular, batch):
            registrar.register(
                registrant_id=contributor_id,
                registrant_name="fixture contributor",
                registrant_kind="provider",
                description="contributes fixture objects",
            )

        singular.contribute(contributor_id, **fields)
        batch.contribute_many(contributor_id, [dict(fields)])

        singular_doc = _clean_doc(live_db, singular_objects, key)
        batch_doc = _clean_doc(live_db, batch_objects, key)

        assert batch_doc == singular_doc
        assert batch_doc["contributor_id"] == str(contributor_id)
    finally:
        for name in (
            singular_catalog,
            singular_objects,
            batch_catalog,
            batch_objects,
        ):
            if live_db.has_collection(name):
                live_db.delete_collection(name)


@pytest.mark.integration
def test_contribute_edge_many_lands_same_attributed_edge_shape_as_singular(
    live_db,
) -> None:
    suffix = uuid4().hex
    singular_catalog = f"BatchEdgeParitySingularCatalog_t{suffix}"
    singular_edges = f"BatchEdgeParitySingularEdges_t{suffix}"
    batch_catalog = f"BatchEdgeParityBatchCatalog_t{suffix}"
    batch_edges = f"BatchEdgeParityBatchEdges_t{suffix}"
    contributor_id = uuid4()
    from_ref = f"entities/{contributor_id}"
    to_ref = f"Objects/{uuid4()}"
    edge = {
        "from_ref": from_ref,
        "to_ref": to_ref,
        "relation_type": "records",
        "run_id": suffix,
    }
    edge_key = uuid5(UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"), f"{from_ref}|records|{to_ref}").hex

    try:
        singular = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=singular_catalog,
            name="batch-edge-parity-singular",
            description="singular side of batch edge parity test",
            owned_edge_collection=singular_edges,
        )
        batch = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=batch_catalog,
            name="batch-edge-parity-batch",
            description="batch side of batch edge parity test",
            owned_edge_collection=batch_edges,
        )
        singular.contribute_edge(contributor_id, **edge)
        batch.contribute_edge_many(contributor_id, [dict(edge)])

        singular_doc = _clean_doc(live_db, singular_edges, edge_key)
        batch_doc = _clean_doc(live_db, batch_edges, edge_key)

        assert batch_doc == singular_doc
        assert batch_doc["contributor_id"] == str(contributor_id)
    finally:
        for name in (
            singular_catalog,
            singular_edges,
            batch_catalog,
            batch_edges,
        ):
            if live_db.has_collection(name):
                live_db.delete_collection(name)


def _write_snapshot_jsonl(snapshot: FilesystemSnapshot, path: Path) -> None:
    path.write_text(
        "".join(entry.model_dump_json() + "\n" for entry in snapshot.entries),
        encoding="utf-8",
    )


def _read_entries_jsonl(path: Path) -> tuple[FileEntryData, ...]:
    return tuple(
        FileEntryData.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    )


def _batch_land_jsonl(
    registrar: Registrar,
    jsonl_path: Path,
    provider_id,
) -> None:
    entries = _read_entries_jsonl(jsonl_path)
    objects_name = registrar.owned_collection_name
    known_uris = {entry.uri for entry in entries}
    object_docs = []
    edge_docs = []

    for entry in entries:
        obj = normalize_file_entry(entry, source=provider_id)
        obj_key = str(obj.object_identifier)
        object_docs.append({"_key": obj_key, **obj.to_contribution_fields()})
        edge_docs.append(
            {
                "from_ref": f"entities/{RECORDER_ID}",
                "to_ref": f"{objects_name}/{obj_key}",
                "relation_type": "records",
            }
        )
        parent_uri = entry.uri.rsplit("/", 1)[0]
        if parent_uri != entry.uri and parent_uri in known_uris:
            parent_key = str(uuid5(NAMESPACE, f"{provider_id}:{parent_uri}"))
            edge_docs.append(
                {
                    "from_ref": f"{objects_name}/{parent_key}",
                    "to_ref": f"{objects_name}/{obj_key}",
                    "relation_type": CONTAINS_RELATION,
                }
            )

    registrar.contribute_many(provider_id, object_docs)
    registrar.contribute_edge_many(RECORDER_ID, edge_docs)


@pytest.mark.integration
def test_batch_jsonl_relanding_does_not_duplicate_objects_or_edges(
    live_db,
    tmp_path: Path,
) -> None:
    root = _fixture_tree(tmp_path / "tree")
    collector = LinuxFilesystemCollector(root, machine_id="batch-idempotence")
    snapshot = collector.collect()
    jsonl_path = tmp_path / "snapshot.jsonl"
    _write_snapshot_jsonl(snapshot, jsonl_path)

    suffix = uuid4().hex
    catalog = f"BatchIdempotenceCatalog_t{suffix}"
    objects = f"BatchIdempotenceObjects_t{suffix}"
    relationships = f"BatchIdempotenceRelationships_t{suffix}"

    try:
        registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=catalog,
            name="batch-idempotence",
            description="owns batch idempotence regression collections",
            owned_collection=objects,
            owned_edge_collection=relationships,
        )
        provider_id = collector.get_provider_id()

        _batch_land_jsonl(registrar, jsonl_path, provider_id)
        objects_after_first = live_db.collection(objects).count()
        edges_after_first = registrar.list_edge_contributions(RECORDER_ID)

        _batch_land_jsonl(registrar, jsonl_path, provider_id)
        objects_after_second = live_db.collection(objects).count()
        edges_after_second = registrar.list_edge_contributions(RECORDER_ID)

        assert objects_after_first == len(snapshot.entries)
        assert objects_after_second == objects_after_first
        assert len(edges_after_second) == len(edges_after_first)
        assert [e["relation_type"] for e in edges_after_second].count(
            CONTAINS_RELATION
        ) == [e["relation_type"] for e in edges_after_first].count(
            CONTAINS_RELATION
        )
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)


def test_landing_throughput_gate_uses_measured_count_and_elapsed_time() -> None:
    from yanantin.recorder.storage.local.linux.batch_landing import (
        BatchLandingRunReport,
        assert_landing_throughput,
    )

    fast_enough = BatchLandingRunReport(
        real_doc_count=100_000,
        landed_doc_count=100_000,
        landing_elapsed_seconds=10.0,
        landing_docs_per_second=10_000.0,
    )
    assert_landing_throughput(fast_enough)

    too_small = BatchLandingRunReport(
        real_doc_count=99_999,
        landed_doc_count=99_999,
        landing_elapsed_seconds=1.0,
        landing_docs_per_second=99_999.0,
    )
    with pytest.raises(AssertionError):
        assert_landing_throughput(too_small)

    suspicious_reported_rate = BatchLandingRunReport(
        real_doc_count=100_000,
        landed_doc_count=100_000,
        landing_elapsed_seconds=20.0,
        landing_docs_per_second=56_000.0,
    )
    with pytest.raises(AssertionError):
        assert_landing_throughput(suspicious_reported_rate)
