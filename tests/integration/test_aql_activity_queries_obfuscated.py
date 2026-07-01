"""The four remaining activity-backend AQL queries, under a NON-TRANSPARENT
obfuscator, on the live DB.

AQL field-mapping guardrail Phase-2 sweep (design §6.2): query_latest,
query_range, get_latest_anchor, list_providers migrated from Regime-2 (leaky
f-string) to Regime-1 (@@col bind, field_path). A green under the transparent
default proves nothing — it maps every name to itself. The prefix obfuscator
makes the physical collection AND field names observably different, so each query
returns correct results ONLY if every name routes through the primitive.

Plus a FORM check: none of the four methods still maps a query field via
field_name (the sanctioned primitive is field_path).

Credentials come from ApachetaDBConfig (the config-file path), NOT env vars —
the env path silently skips in a worktree with no copied .env.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.activity.models import FactRecord, MemoryAnchor
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
    obf = PrefixObfuscator(f"aqlsweep_{uuid4().hex}_")
    store = ArangoDBActivityStreamStore(
        host=host, db_name=_DB, username=user, password=pwd, obfuscator=obf,
    )
    yield store, obf
    for name in ("activity_facts", "activity_anchors"):
        physical = obf.collection_name(name)
        if store._db.has_collection(physical):
            store._db.delete_collection(physical)
    store.close()


def _fact(pid: UUID, ts: datetime, value: int) -> FactRecord:
    return FactRecord(
        id=uuid4(), provider_id=pid, timestamp=ts,
        data={"value": value}, content_hash=f"h-{value}",
    )


# -- query_latest ------------------------------------------------------


def test_query_latest_before_under_obfuscation(obf_store):
    store, _ = obf_store
    a = uuid4()
    base = datetime(2025, 6, 1, tzinfo=timezone.utc)
    store.store_fact(_fact(a, base, 1))
    store.store_fact(_fact(a, base + timedelta(hours=1), 2))
    store.store_fact(_fact(a, base + timedelta(hours=2), 3))

    result = store.query_latest(a, before=base + timedelta(hours=1, minutes=30))
    assert result is not None and result.data["value"] == 2


def test_query_latest_no_before_under_obfuscation(obf_store):
    store, _ = obf_store
    a = uuid4()
    base = datetime(2025, 6, 1, tzinfo=timezone.utc)
    store.store_fact(_fact(a, base, 1))
    store.store_fact(_fact(a, base + timedelta(hours=1), 2))

    result = store.query_latest(a)
    assert result is not None and result.data["value"] == 2


# -- query_range -------------------------------------------------------


def test_query_range_start_and_end_under_obfuscation(obf_store):
    store, _ = obf_store
    a = uuid4()
    base = datetime(2025, 6, 1, tzinfo=timezone.utc)
    for i in range(4):
        store.store_fact(_fact(a, base + timedelta(hours=i), i))

    results = store.query_range(
        a, start=base + timedelta(hours=1), end=base + timedelta(hours=2),
    )
    assert [r.data["value"] for r in results] == [1, 2]


def test_query_range_no_bounds_returns_all_sorted_under_obfuscation(obf_store):
    store, _ = obf_store
    a = uuid4()
    base = datetime(2025, 6, 1, tzinfo=timezone.utc)
    store.store_fact(_fact(a, base + timedelta(hours=2), 2))
    store.store_fact(_fact(a, base, 0))
    store.store_fact(_fact(a, base + timedelta(hours=1), 1))

    results = store.query_range(a)
    assert [r.data["value"] for r in results] == [0, 1, 2]


# -- get_latest_anchor -------------------------------------------------


def test_get_latest_anchor_under_obfuscation(obf_store):
    store, _ = obf_store
    base = datetime(2025, 6, 1, tzinfo=timezone.utc)
    store.store_anchor(MemoryAnchor(handle=uuid4(), timestamp=base, cursors=()))
    newest = uuid4()
    store.store_anchor(
        MemoryAnchor(handle=newest, timestamp=base + timedelta(hours=1), cursors=())
    )

    latest = store.get_latest_anchor()
    assert latest is not None and latest.handle == newest


# -- list_providers ----------------------------------------------------


def test_list_providers_under_obfuscation(obf_store):
    store, _ = obf_store
    a, b = uuid4(), uuid4()
    base = datetime(2025, 6, 1, tzinfo=timezone.utc)
    store.store_fact(_fact(a, base, 1))
    store.store_fact(_fact(b, base, 2))

    assert set(store.list_providers()) == {a, b}


# -- FORM check --------------------------------------------------------


def test_no_migrated_query_maps_its_field_via_field_name():
    """Each migrated method names query fields through field_path, not field_name."""
    for method in (
        ArangoDBActivityStreamStore.query_latest,
        ArangoDBActivityStreamStore.query_range,
        ArangoDBActivityStreamStore.get_latest_anchor,
        ArangoDBActivityStreamStore.list_providers,
    ):
        src = inspect.getsource(method)
        assert ".field_name(" not in src, (
            f"{method.__name__} still maps a query field via field_name — "
            "use field_path (design §3)"
        )
        assert "{col}" not in src, (
            f"{method.__name__} still text-interpolates the collection — bind @@col"
        )
