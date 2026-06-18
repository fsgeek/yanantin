from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def live_db():
    """A real StandardDatabase handle on apacheta_test (test-tier creds)."""
    from yanantin.infra.config import ApachetaDBConfig, get_database

    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )


def test_registrar_round_trips_contributes_to_unchanged(live_db):
    from yanantin.core.registration import Registrar

    suffix = uuid4().hex
    catalog = f"RegistrarOpacityCatalog_t{suffix}"
    registrant_id = uuid4()
    mapping = [
        {"name": "Objects", "kind": "doc", "naming": "well_known"},
        {"name": "Relationships", "kind": "edge", "naming": "well_known"},
    ]

    try:
        registrar = Registrar(
            db=live_db,
            catalog_collection=catalog,
            name="opacity-registrar",
            description="registrar opacity guard",
        )
        registrar.register(
            registrant_id=registrant_id,
            registrant_name="r",
            registrant_kind="provider",
            description="d",
            contributes_to=mapping,
        )

        record = registrar.lookup_by_identifier(registrant_id)

        assert record is not None
        try:
            contributes_to = record.contributes_to
        except AttributeError:
            contributes_to = record.model_extra["contributes_to"]
        assert contributes_to == mapping

        repo_root = Path(__file__).resolve().parents[2]
        source = (repo_root / "src" / "yanantin" / "core" / "registration.py").read_text(
            encoding="utf-8"
        )
        assert "contributes_to" not in source
        assert "well_known" not in source
        assert "dynamic" not in source
    finally:
        if live_db.has_collection(catalog):
            live_db.delete_collection(catalog)
