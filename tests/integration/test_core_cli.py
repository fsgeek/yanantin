"""core CLI — the first ledger-shaped read tool (gh #1, C0)."""

import json
import uuid

import pytest

from tests.integration._obfuscators import PrefixObfuscator
from yanantin.core.__main__ import main
from yanantin.core.registration import BASE_REGISTRANT_CATALOG, RegistrationService
from yanantin.infra.config import ApachetaDBConfig, get_database

pytestmark = pytest.mark.integration


@pytest.fixture
def populated_service():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    db = get_database(
        host=cfg.host_url, db_name="apacheta_test",
        username=creds["username"], password=creds["password"],
    )
    obf = PrefixObfuscator(f"cli_{uuid.uuid4().hex}_")
    svc = RegistrationService(db=db, obfuscator=obf)
    rid = uuid.uuid4()
    svc.base_registrar.register(
        registrant_id=rid, registrant_name="linux-local-fs",
        registrant_kind="provider", description="local fs provider",
    )
    yield svc, rid
    stored = obf.collection_name(BASE_REGISTRANT_CATALOG)
    if db.has_collection(stored):
        db.delete_collection(stored)


def test_list_prints_registrant_name(populated_service, capsys):
    svc, _ = populated_service
    main(["list"], service=svc)
    out = capsys.readouterr().out
    assert "linux-local-fs" in out


def test_list_is_default_command(populated_service, capsys):
    svc, _ = populated_service
    main([], service=svc)
    assert "linux-local-fs" in capsys.readouterr().out


def test_list_json_parses_and_carries_fields(populated_service, capsys):
    svc, rid = populated_service
    main(["--json", "list"], service=svc)
    rows = json.loads(capsys.readouterr().out)
    assert rows[0]["registrant_name"] == "linux-local-fs"
    assert rows[0]["registrant_id"] == str(rid)
    assert rows[0]["contributions"] == 0


def test_show_prints_full_record(populated_service, capsys):
    svc, rid = populated_service
    main(["show", str(rid)], service=svc)
    out = capsys.readouterr().out
    assert "linux-local-fs" in out
    assert "local fs provider" in out


def test_show_unknown_id_exits_nonzero(populated_service):
    svc, _ = populated_service
    with pytest.raises(SystemExit) as exc:
        main(["show", str(uuid.uuid4())], service=svc)
    assert exc.value.code == 1
