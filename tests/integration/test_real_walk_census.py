"""Real-walk census proof: criteria 2a + 2c of the storage census vertical.

2a — the REAL LinuxFilesystemCollector walk lands StorageObjects + containment
     edges into Objects/Relationships on the live DB; traversal resolves.
2c — re-walking the SAME tree WITHOUT reset is idempotent at the snapshot level:
     object count and containment-edge count do not double (the collision gate
     holding for a real walk, not just a hand-built snapshot).

Uses the real collector over a real tmp tree (deterministic, fast) so the actual
os.walk/_is_pruned/normalize path is exercised — not a synthetic stand-in.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from yanantin.infra.config import ApachetaDBConfig, get_database


@pytest.fixture
def live_db():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )


@pytest.fixture
def real_tree(tmp_path: Path) -> Path:
    """A small real directory tree the collector can walk."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("a\n")
    (tmp_path / "pkg" / "b.py").write_text("b\n")
    (tmp_path / "pkg" / "sub").mkdir()
    (tmp_path / "pkg" / "sub" / "c.txt").write_text("c\n")
    (tmp_path / "readme.md").write_text("# r\n")
    return tmp_path


def _count(db, name: str) -> int:
    return db.collection(name).count()


def test_real_walk_lands_objects_and_edges_and_is_idempotent(live_db, real_tree):
    from yanantin.collector.storage.local.linux.collector import (
        LinuxFilesystemCollector,
    )
    from yanantin.core.khipu import Khipu
    from yanantin.core.registration import Registrar
    from yanantin.recorder.storage.local.linux.registration import (
        LinuxStorageRegistration,
    )

    suffix = uuid4().hex
    catalog = f"RealWalkCatalog_t{suffix}"
    objects = f"Objects_t{suffix}"
    relationships = f"Relationships_t{suffix}"

    try:
        registrar = Registrar(
            db=live_db,
            khipu=Khipu(db=live_db),
            catalog_collection=catalog,
            name="real-walk-registrar",
            description="owns real-walk census regression collections",
            owned_collection=objects,
            owned_edge_collection=relationships,
        )
        collector = LinuxFilesystemCollector(real_tree, machine_id="test")
        reg = LinuxStorageRegistration(registrar, collector)
        reg.register()
        provider = collector.get_provider_id()

        # --- 2a: first real walk lands objects + edges ---
        snapshot = collector.collect()
        n_entries = len(snapshot.entries)
        assert n_entries >= 6  # tmp_path, pkg, sub, a.py, b.py, c.txt, readme.md

        reg.contribute_snapshot(snapshot, provider)

        objects_after_first = _count(live_db, objects)
        edges = registrar.list_edge_contributions(reg.recorder_id)
        contains_first = [e for e in edges if e["relation_type"] == "contains"]
        assert objects_after_first == n_entries
        assert len(contains_first) > 0  # real parent/child containment present

        # traversal resolves: pick a contains edge, walk OUTBOUND, get the child
        sample = contains_first[0]
        reached = list(
            live_db.aql.execute(
                f"FOR v IN 1..1 OUTBOUND @start `{relationships}` RETURN v._key",
                bind_vars={"start": sample["_from"]},
            )
        )
        assert reached  # non-empty: endpoints are canonical, traversal resolves

        # --- 2c: re-walk WITHOUT reset is idempotent at scale ---
        snapshot2 = collector.collect()
        reg.contribute_snapshot(snapshot2, provider)

        objects_after_second = _count(live_db, objects)
        edges2 = registrar.list_edge_contributions(reg.recorder_id)
        contains_second = [e for e in edges2 if e["relation_type"] == "contains"]

        assert objects_after_second == objects_after_first  # no object doubling
        assert len(contains_second) == len(contains_first)  # no edge doubling
    finally:
        for name in (catalog, objects, relationships):
            if live_db.has_collection(name):
                live_db.delete_collection(name)
