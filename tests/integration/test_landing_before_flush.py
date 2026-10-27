"""land_jsonl calls before_flush ahead of every write, so a caller can hold the
landing while the database is under pressure (2026-10-27: arango-apacheta now runs
under a 20 GiB cap; a landing must not push it into its limit)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from yanantin.collector.storage.local.linux.collector import LinuxFilesystemCollector
from yanantin.core.khipu import Khipu
from yanantin.core.registration import Registrar
from yanantin.recorder.storage.local.linux.batch_landing import land_jsonl, write_entries_jsonl


@pytest.fixture
def live_db():
    from yanantin.infra.config import ApachetaDBConfig, get_database

    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    try:
        db = get_database(host=cfg.host_url, db_name="apacheta_test",
                          username=creds["username"], password=creds["password"])
        db.collections()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"apacheta_test unreachable: {exc!r}")
    return db


def test_before_flush_runs_before_every_flush(live_db, tmp_path: Path):
    root = tmp_path / "tree"
    for i in range(7):
        (root / f"d{i}").mkdir(parents=True)
        (root / f"d{i}" / "f.txt").write_text("x")
    collector = LinuxFilesystemCollector(root, machine_id="before-flush")
    jsonl = tmp_path / "walk.jsonl"
    n = write_entries_jsonl(collector.stream_entries(), jsonl)

    sfx = uuid4().hex[:8]
    names = (f"BFCat_{sfx}", f"BFObj_{sfx}", f"BFRel_{sfx}")
    calls = []
    try:
        registrar = Registrar(db=live_db, khipu=Khipu(db=live_db), catalog_collection=names[0],
                              name="before-flush", description="before_flush test",
                              owned_collection=names[1], owned_edge_collection=names[2])
        land_jsonl(registrar, jsonl, collector.get_provider_id(), chunk_size=4,
                   before_flush=lambda: calls.append(live_db.collection(names[1]).count()))
        # One call per non-empty flush: ceil(n / 4). Each sees the writes so far.
        assert len(calls) == -(-n // 4)
        assert calls == sorted(calls) and calls[0] == 0
        assert live_db.collection(names[1]).count() == n
    finally:
        for name in names:
            if live_db.has_collection(name):
                live_db.delete_collection(name)
