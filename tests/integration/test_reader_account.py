"""The read-only account, against the live server: it can count where granted,
cannot write there, and cannot read anywhere else. reader.ini holds no admin key."""

import configparser
import stat

import pytest
from arango.exceptions import ArangoServerError

from yanantin.infra.config import ApachetaDBConfig, get_database
from yanantin.infra.orchestrator import ApachetaDBSetup

pytestmark = pytest.mark.integration

USER = "yanantin_reader_test"


@pytest.fixture
def setup():
    cfg = ApachetaDBConfig()
    try:
        cfg.connect("admin").properties()
    except Exception as exc:  # no live server here
        pytest.skip(f"no live ArangoDB: {exc}")
    test_db = cfg.connect("test")
    name = "reader_probe"
    if not test_db.has_collection(name):
        test_db.create_collection(name)
    test_db.collection(name).insert({"x": 1})
    yield ApachetaDBSetup(cfg), cfg, name
    test_db.delete_collection(name, ignore_missing=True)
    sys_db = cfg.connect("admin")
    if any(u["username"] == USER for u in sys_db.users()):
        sys_db.delete_user(USER)
    get_database.cache_clear()  # the deleted user's handle must not outlive it


def _as_reader(cfg, reader_file, db_name):
    r = configparser.ConfigParser(); r.read(reader_file)
    return get_database(host=cfg.host_url, db_name=db_name,
                        username=r["database"]["user"], password=r["database"]["password"])


def test_reader_counts_where_granted_and_nowhere_else(setup, tmp_path):
    setup_, cfg, name = setup
    reader_file = setup_.ensure_reader(["apacheta_test"], tmp_path / "reader.ini", username=USER)

    assert stat.S_IMODE(reader_file.stat().st_mode) == 0o600
    text = reader_file.read_text()
    parsed = configparser.ConfigParser(); parsed.read(reader_file)
    # qhaway's reground reads exactly these (tests/red_bar/test_qhaway_reground_contract.py)
    assert set(parsed["database"]) == {"host", "port", "ssl", "user", "password", "databases"}
    assert "admin" not in text and cfg.get_admin_credentials()["password"] not in text

    db = _as_reader(cfg, reader_file, "apacheta_test")
    assert db.collection(name).count() == 1
    with pytest.raises(ArangoServerError):
        db.collection(name).insert({"x": 2})
    with pytest.raises(ArangoServerError):
        _as_reader(cfg, reader_file, cfg.db["database"]).collection("records").count()


def test_reader_is_idempotent(setup, tmp_path):
    setup_, cfg, name = setup
    first = setup_.ensure_reader(["apacheta_test"], tmp_path / "reader.ini", username=USER).read_text()
    second = setup_.ensure_reader(["apacheta_test"], tmp_path / "reader.ini", username=USER).read_text()
    assert first == second
    assert _as_reader(cfg, tmp_path / "reader.ini", "apacheta_test").collection(name).count() == 1
