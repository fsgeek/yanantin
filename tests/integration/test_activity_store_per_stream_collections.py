"""Re-seat: the activity store takes its collection identity as a parameter and
mints it through the registration path (Khipu/watay), not a hardcoded literal +
direct create_collection. Bug named by Tony 2026-07-07: "hardcoding collection
names is the antithesis of registration."

Target behavior — two providers, two DISTINCT collections, both joinable:
a band-shaped stream and a conversation-shaped stream land in SEPARATE named
collections (the contained-blast-radius property: each is deletable/rebuildable
alone) yet join in one query (the yanantin fold: separate, still joinable).

Live apacheta_test, config-file creds (env path silently skips in a worktree,
per the sandbox-skip lesson). Self-cleaning: drops its own collections.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.activity.models import FactRecord
from yanantin.infra.config import ApachetaDBConfig, get_database

pytestmark = pytest.mark.integration

_DB = "apacheta_test"


def _conn():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return cfg.host_url, creds["username"], creds["password"]


def _available() -> bool:
    try:
        host, user, pwd = _conn()
        get_database(host=host, db_name=_DB, username=user, password=pwd).collections()
        return True
    except Exception:
        return False


def _store(facts: str, anchors: str):
    host, user, pwd = _conn()
    return ArangoDBActivityStreamStore(
        host=host, db_name=_DB, username=user, password=pwd,
        facts_collection=facts, anchors_collection=anchors,
    )


def test_two_streams_land_in_distinct_collections_and_join():
    if not _available():
        pytest.skip("ArangoDB test database not available")

    band_col = f"activity_band_facts_{uuid4().hex}"
    conv_col = f"activity_conv_facts_{uuid4().hex}"
    band_anchors = f"activity_band_anchors_{uuid4().hex}"
    conv_anchors = f"activity_conv_anchors_{uuid4().hex}"
    band_store = _store(band_col, band_anchors)
    conv_store = _store(conv_col, conv_anchors)

    ts = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    band_pid = uuid4()
    conv_pid = uuid4()
    shared_cwd = "/data/projects/demo"

    band_fact = FactRecord(
        id=uuid4(), provider_id=band_pid, timestamp=ts,
        data={"location": f"path:{shared_cwd}/x", "access_kinds": 2},
        content_hash="band-1",
    )
    conv_fact = FactRecord(
        id=uuid4(), provider_id=conv_pid, timestamp=ts,
        data={"cwd": shared_cwd, "model": "claude-opus-4-8", "role": "assistant"},
        content_hash="conv-1",
    )
    try:
        band_store.store_fact(band_fact)
        conv_store.store_fact(conv_fact)

        # Distinct physical collections (contained blast radius).
        assert band_store._map.collection_name(band_col) != \
            conv_store._map.collection_name(conv_col)

        # Both round-trip intact through the real obfuscation boundary.
        assert band_store.get_fact(band_fact.id).data["access_kinds"] == 2
        assert conv_store.get_fact(conv_fact.id).data["model"] == "claude-opus-4-8"

        # The FOLD: separate collections, joined in ONE query on shared cwd.
        db = get_database(host=_conn()[0], db_name=_DB,
                          username=_conn()[1], password=_conn()[2])
        cur = db.aql.execute(
            "FOR c IN @@conv "
            "  FOR b IN @@band "
            "    FILTER b.data.location LIKE CONCAT('path:', c.data.cwd, '%') "
            "    RETURN {conv_model: c.data.model, band_loc: b.data.location}",
            bind_vars={
                "@conv": conv_store._map.collection_name(conv_col),
                "@band": band_store._map.collection_name(band_col),
            },
        )
        rows = list(cur)
        assert len(rows) == 1
        assert rows[0]["conv_model"] == "claude-opus-4-8"
        assert rows[0]["band_loc"] == f"path:{shared_cwd}/x"
    finally:
        for st, col in (
            (band_store, band_col), (band_store, band_anchors),
            (conv_store, conv_col), (conv_store, conv_anchors),
        ):
            physical = st._map.collection_name(col)
            if st._db.has_collection(physical):
                st._db.delete_collection(physical)
        band_store.close()
        conv_store.close()
