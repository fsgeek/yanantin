"""count_facts under a NON-TRANSPARENT obfuscator, on the live DB.

The AQL field-mapping guardrail migration (design §6): count_facts is the first
Regime-2 site converted to the Regime-1 target (@@col bind, field_path for the
field, value bound). A green under the TRANSPARENT default proves nothing — it
maps every name to itself, so a broken field mapping would still pass. This test
runs under a prefix obfuscator, so the collection AND the provider_id field must
be correctly mapped through the sanctioned primitive or the count is wrong.

Also asserts the FORM: the red-bar (test_no_literal_aql_field_refs) must no
longer flag count_facts's FILTER line — field_path bound, not field_name
interpolated.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.activity.models import FactRecord
from yanantin.infra.config import ApachetaDBConfig, get_database

from tests.integration._obfuscators import PrefixObfuscator

pytestmark = pytest.mark.integration

_DB_NAME = "apacheta_test"


def _conn():
    """Credentials from the config file (the path that works without a copied
    .env) — same pattern as tests/test_regrounding.py."""
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return cfg.host_url, creds["username"], creds["password"]


def _available() -> bool:
    try:
        host, user, pwd = _conn()
        get_database(host=host, db_name=_DB_NAME, username=user, password=pwd).collections()
        return True
    except Exception:
        return False


@pytest.fixture
def obf_store():
    if not _available():
        pytest.skip("ArangoDB test database not available")
    host, user, pwd = _conn()
    # Unique prefix per test → isolated obfuscated collections, no cross-test bleed.
    obf = PrefixObfuscator(f"aqlmig_{uuid4().hex}_")
    store = ArangoDBActivityStreamStore(
        host=host, db_name=_DB_NAME, username=user, password=pwd,
        obfuscator=obf,
    )
    yield store, obf
    # Clean up the obfuscated collections this test created.
    for name in ("activity_facts", "activity_anchors"):
        physical = obf.collection_name(name)
        if store._db.has_collection(physical):
            store._db.delete_collection(physical)
    store.close()


def _fact(provider_id: UUID, ts: datetime, value: int) -> FactRecord:
    return FactRecord(
        id=uuid4(), provider_id=provider_id, timestamp=ts,
        data={"value": value}, content_hash=f"h-{value}",
    )


def test_count_facts_by_provider_correct_under_obfuscation(obf_store):
    """The provider filter counts correctly only if provider_id is mapped
    through the obfuscator — proven by the non-identity prefix."""
    store, _ = obf_store
    a, b = uuid4(), uuid4()
    base = datetime(2025, 6, 1, tzinfo=timezone.utc)

    store.store_fact(_fact(a, base, 1))
    store.store_fact(_fact(a, base + timedelta(hours=1), 2))
    store.store_fact(_fact(b, base, 3))

    assert store.count_facts(a) == 2
    assert store.count_facts(b) == 1


def test_count_facts_total_under_obfuscation(obf_store):
    """The unfiltered branch (RETURN LENGTH(@@col)) counts the whole
    obfuscated collection."""
    store, _ = obf_store
    a = uuid4()
    base = datetime(2025, 6, 1, tzinfo=timezone.utc)
    store.store_fact(_fact(a, base, 1))
    store.store_fact(_fact(a, base + timedelta(hours=1), 2))

    assert store.count_facts() == 2


def test_count_facts_source_uses_field_path_not_leaky_interpolation():
    """FORM check: count_facts's body must name its field via field_path (the
    sanctioned primitive) and must NOT interpolate a field_name var into a
    `doc.{...}` position. This is the Regime-2 → Regime-1 form conversion the
    guardrail exists to enforce."""
    import inspect

    from yanantin.activity.backends.arango import ArangoDBActivityStreamStore

    src = inspect.getsource(ArangoDBActivityStreamStore.count_facts)
    # The sanctioned primitive is used for the field...
    assert "field_path" in src, "count_facts must name its field via field_path"
    # ...and the leaky Regime-2 form is gone: no var assigned from field_name(...)
    # is interpolated into a doc.{...} position. (Interpolating a field_path RESULT
    # is allowed — design §6.1 — so the check is provenance-based, not "no doc.{").
    assert ".field_name(" not in src, (
        "count_facts still maps its field via field_name — use field_path, the "
        "sanctioned query-field primitive (design §3)"
    )
    assert "{col}" not in src, (
        "count_facts still text-interpolates the collection name — bind it as @@col"
    )
