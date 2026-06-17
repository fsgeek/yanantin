"""RegistrationService — the catalog seam the CLI reads through (gh #1, C0)."""

import uuid

import pytest

from yanantin.core.registration import (
    BASE_REGISTRANT_CATALOG,
    RegistrationService,
)
from yanantin.infra.config import ApachetaDBConfig, get_database
from tests.integration._obfuscators import PrefixObfuscator

pytestmark = pytest.mark.integration


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
def service(live_db):
    """A RegistrationService whose base catalog is an isolated obfuscated
    collection, torn down after."""
    obf = PrefixObfuscator(f"svc_{uuid.uuid4().hex}_")
    svc = RegistrationService(db=live_db, obfuscator=obf)
    yield svc
    stored = obf.collection_name(BASE_REGISTRANT_CATALOG)
    if live_db.has_collection(stored):
        live_db.delete_collection(stored)


def test_base_catalog_created_on_construction(service, live_db):
    obf = service.base_registrar._obfuscator
    stored = obf.collection_name(BASE_REGISTRANT_CATALOG)
    assert live_db.has_collection(stored)


def test_round_trips_a_registrant_through_all_three_verbs(service):
    rid = uuid.uuid4()
    service.base_registrar.register(
        registrant_id=rid,
        registrant_name="linux-local-fs",
        registrant_kind="provider",
        description="local filesystem storage provider",
    )
    listed = service.get_registrant_list()
    assert [r.registrant_id for r in listed] == [rid]
    assert service.lookup_by_identifier(rid).registrant_name == "linux-local-fs"
    assert service.lookup_by_name("linux-local-fs").registrant_id == rid


def test_lookup_by_name_unknown_returns_none_not_raise(service):
    assert service.lookup_by_name("no-such-provider") is None


def test_contribution_count_reflects_contributions(service):
    rid = uuid.uuid4()
    service.base_registrar.register(
        registrant_id=rid,
        registrant_name="counter",
        registrant_kind="provider",
        description="contributes twice",
    )
    assert service.contribution_count(rid) == 0
    service.base_registrar.contribute(contributor_id=rid, path="/a")
    service.base_registrar.contribute(contributor_id=rid, path="/b")
    assert service.contribution_count(rid) == 2
