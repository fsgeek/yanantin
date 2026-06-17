"""Red bar: provider registration is per-StandardDatabase (the ayllu posture
made honest, not pinky-sworn).

The C0 design runs a SINGLE StandardDatabase in the normal case and trusts kin
to respect each other — but that is *deferring the USE of isolation, not its
EXISTENCE*. The system supports multiple StandardDatabase instances; it simply
maintains one in the normal case. What keeps that honest rather than a promise
is this test: a registrant written in DB-A must be **invisible** to a query
against DB-B. The registrar boundary and the privacy boundary are the SAME
boundary, and that boundary is the StandardDatabase.

  Green ⇒ isolation is a validated capability we chose not to deploy.
  Red   ⇒ we do not get to claim isolation.

ArangoDB native edges cannot span StandardDatabase objects, and neither can a
registrar — it physically can't, and must not pretend to. This proves the
structural fact, not an asserted one. No mocks: a real second database is
admin-created, granted to the test user, and torn down.

Design source: docs/superpowers/specs/2026-06-16-c0-registration-design.md
(the "build for N, run 1, TEST BOTH" discipline).
"""

from __future__ import annotations

import uuid

import pytest

from yanantin.core.registration import Registrar
from yanantin.infra.config import ApachetaDBConfig, get_database


pytestmark = pytest.mark.integration


@pytest.fixture
def two_real_databases():
    """DB-A is the live apacheta_test; DB-B is a freshly admin-created second
    StandardDatabase granted to the same test user. Both handles come from the
    connection singleton (test-tier principal). DB-B is dropped on teardown.
    """
    cfg = ApachetaDBConfig()
    test_creds = cfg.get_test_credentials()
    second_db_name = f"apacheta_iso_test_{uuid.uuid4().hex}"

    sys_db = cfg.connect("admin")
    sys_db.create_database(second_db_name)
    sys_db.update_permission(test_creds["username"], "rw", second_db_name)

    get_database.cache_clear()
    db_a = get_database(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=test_creds["username"],
        password=test_creds["password"],
    )
    db_b = get_database(
        host=cfg.host_url,
        db_name=second_db_name,
        username=test_creds["username"],
        password=test_creds["password"],
    )
    try:
        yield db_a, db_b
    finally:
        if sys_db.has_database(second_db_name):
            sys_db.delete_database(second_db_name)
        get_database.cache_clear()


def test_registrant_in_db_a_is_invisible_to_db_b(two_real_databases):
    """A registrant written through a registrar on DB-A is NOT visible to a
    registrar on DB-B using the same catalog collection name. The structural
    boundary is real; it fails CLOSED (the registrant simply isn't there),
    not open."""
    db_a, db_b = two_real_databases
    catalog = f"iso_catalog_{uuid.uuid4().hex}"
    rid = uuid.uuid4()

    reg_a = Registrar(
        db=db_a,
        catalog_collection=catalog,
        name="registrar-in-A",
        description="owns its catalog in DB-A only",
    )
    reg_a.register(
        registrant_id=rid,
        registrant_name="secret-to-A",
        registrant_kind="provider",
        description="must not leak across the StandardDatabase boundary",
    )

    try:
        # Sanity: visible in its OWN database (the single-DB half).
        assert reg_a.lookup_by_identifier(rid) is not None

        # The red bar: a registrar on DB-B with the same catalog name does not
        # see A's registrant. DB-B's catalog is a different physical collection
        # in a different StandardDatabase — the registrant is invisible.
        reg_b = Registrar(
            db=db_b,
            catalog_collection=catalog,
            name="registrar-in-B",
            description="separate StandardDatabase, separate catalog",
        )
        assert reg_b.lookup_by_identifier(rid) is None
        assert reg_b.list_registrants() == []
    finally:
        if db_a.has_collection(catalog):
            db_a.delete_collection(catalog)
        # DB-B is dropped wholesale by the fixture teardown.
