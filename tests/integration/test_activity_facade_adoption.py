"""Activity backend document paths, routed through the Database façade, under a
NON-TRANSPARENT obfuscator on the live DB.

Façade adoption (roadmap step 4, slice 1): store_fact/get_fact/store_anchor/
get_anchor route document-key obfuscation + collection naming through the façade
instead of hand-rolled collection_name + field_name loops. The round-trip
(store then get returns the original) passes only if the façade correctly
obfuscates keys on write and deobfuscates on read — proven by the prefix
obfuscator making physical names observably different. Immutability (the has()
guard) must survive the migration too.

Config-file creds, not env vars (env path silently skips in a worktree).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.activity.models import AnchorCursor, FactRecord, MemoryAnchor
from yanantin.apacheta.interface.errors import ImmutabilityError, NotFoundError
from yanantin.infra.config import ApachetaDBConfig, get_database

from tests.integration._obfuscators import PrefixObfuscator

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


@pytest.fixture
def obf_store():
    if not _available():
        pytest.skip("ArangoDB test database not available")
    host, user, pwd = _conn()
    obf = PrefixObfuscator(f"facadeadopt_{uuid4().hex}_")
    store = ArangoDBActivityStreamStore(
        host=host, db_name=_DB, username=user, password=pwd, obfuscator=obf,
    )
    yield store, obf
    for name in ("activity_facts", "activity_anchors"):
        physical = obf.collection_name(name)
        if store._db.has_collection(physical):
            store._db.delete_collection(physical)
    store.close()


def test_fact_roundtrip_through_facade_under_obfuscation(obf_store):
    """store_fact then get_fact returns the original — only works if the façade
    obfuscates keys on write and reverses them on read."""
    store, obf = obf_store
    pid = uuid4()
    ts = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
    fact = FactRecord(
        id=uuid4(), provider_id=pid, timestamp=ts,
        data={"value": 42}, content_hash="h-42",
    )
    store.store_fact(fact)

    got = store.get_fact(fact.id)
    assert got.id == fact.id
    assert got.provider_id == pid
    assert got.data["value"] == 42
    assert got.content_hash == "h-42"


def test_fact_stored_on_wire_with_obfuscated_field_keys(obf_store):
    """The physical document has PREFIXED field keys — semantic names never hit
    the wire. Proves the façade actually obfuscated (not a transparent pass)."""
    store, obf = obf_store
    pid = uuid4()
    ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
    fact = FactRecord(
        id=uuid4(), provider_id=pid, timestamp=ts,
        data={"value": 1}, content_hash="h-1",
    )
    store.store_fact(fact)

    physical_col = store._db.collection(obf.collection_name("activity_facts"))
    raw_doc = physical_col.get(str(fact.id))
    assert raw_doc is not None
    assert obf.field_name("provider_id") in raw_doc  # obfuscated key present
    assert "provider_id" not in raw_doc  # semantic key absent from the wire


def test_fact_immutability_survives_facade(obf_store):
    """The has()-guarded immutability check still fires through the façade."""
    store, _ = obf_store
    fid = uuid4()
    ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
    f1 = FactRecord(id=fid, provider_id=uuid4(), timestamp=ts,
                    data={"v": 1}, content_hash="h1")
    store.store_fact(f1)

    dup = FactRecord(id=fid, provider_id=uuid4(), timestamp=ts,
                     data={"v": 2}, content_hash="h2")
    with pytest.raises(ImmutabilityError):
        store.store_fact(dup)


def test_anchor_roundtrip_through_facade_under_obfuscation(obf_store):
    """store_anchor then get_anchor preserves cursors through the façade.

    NOTE: cursors carry only `data` here, NOT `attributes`. Cursor `attributes`
    under a NON-TRANSPARENT obfuscator is a PRE-EXISTING latent bug — store_anchor
    obfuscates nested cursor dicts (prefixing their own field keys) but
    get_anchor/_doc_to_anchor does not reverse the nested obfuscation, so
    AnchorCursor rejects the prefixed key. It is untested (the existing suite
    exercises attributes only under the transparent default) and OUT OF SCOPE for
    façade adoption — flagged for a separate goal, not fixed inside this migration.
    """
    store, _ = obf_store
    p1, p2 = uuid4(), uuid4()
    cursors = (
        AnchorCursor(provider=p1, reference=uuid4(), data="ref-1"),
        AnchorCursor(provider=p2, reference=uuid4(), data="ref-2"),
    )
    anchor = MemoryAnchor(
        handle=uuid4(), timestamp=datetime(2025, 6, 1, tzinfo=timezone.utc),
        cursors=cursors,
    )
    store.store_anchor(anchor)

    got = store.get_anchor(anchor.handle)
    assert got.handle == anchor.handle
    assert {c.provider for c in got.cursors} == {p1, p2}
    assert {c.data for c in got.cursors} == {"ref-1", "ref-2"}


def test_anchor_not_found_through_facade(obf_store):
    store, _ = obf_store
    with pytest.raises(NotFoundError):
        store.get_anchor(uuid4())
