from __future__ import annotations

import uuid

import pytest

from yanantin.infra.config import ApachetaDBConfig, get_database


ARANGO_ENV_KEYS = (
    "YANANTIN_ARANGO_HOST",
    "YANANTIN_ARANGO_DB",
    "YANANTIN_ARANGO_USER",
    "YANANTIN_ARANGO_PASSWORD",
)
WITNESS_COLLECTION = "get_database_singleton_witness"


@pytest.fixture(autouse=True)
def isolate_process_global_database_cache(monkeypatch: pytest.MonkeyPatch):
    get_database.cache_clear()
    for key in ARANGO_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    yield

    get_database.cache_clear()


@pytest.fixture
def live_test_target() -> tuple[str, str, str, str]:
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return cfg.host_url, "apacheta_test", creds["username"], creds["password"]


def _set_arango_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    host: str,
    db_name: str,
    username: str,
    password: str,
) -> None:
    monkeypatch.setenv("YANANTIN_ARANGO_HOST", host)
    monkeypatch.setenv("YANANTIN_ARANGO_DB", db_name)
    monkeypatch.setenv("YANANTIN_ARANGO_USER", username)
    monkeypatch.setenv("YANANTIN_ARANGO_PASSWORD", password)


def _witness_collection(db):
    if not db.has_collection(WITNESS_COLLECTION):
        return db.create_collection(WITNESS_COLLECTION)
    return db.collection(WITNESS_COLLECTION)


def _assert_live_round_trip(writer_db, reader_db) -> None:
    key = f"singleton_{uuid.uuid4().hex}"
    marker = f"marker_{uuid.uuid4().hex}"
    writer_collection = _witness_collection(writer_db)
    reader_collection = reader_db.collection(WITNESS_COLLECTION)

    try:
        writer_collection.insert({"_key": key, "marker": marker}, sync=True)
        assert reader_collection.get(key)["marker"] == marker
    finally:
        writer_collection.delete(key, ignore_missing=True)


@pytest.mark.integration
def test_same_resolved_target_reuses_handle_and_sees_live_document(
    monkeypatch: pytest.MonkeyPatch,
    live_test_target: tuple[str, str, str, str],
) -> None:
    host, db_name, username, password = live_test_target
    _set_arango_env(
        monkeypatch,
        host=host,
        db_name=db_name,
        username=username,
        password=password,
    )

    explicit = get_database(
        host=host,
        db_name=db_name,
        username=username,
        password=password,
    )
    from_env = get_database()

    assert from_env is explicit
    _assert_live_round_trip(explicit, from_env)


@pytest.mark.integration
def test_password_change_does_not_split_singleton_for_same_identity(
    live_test_target: tuple[str, str, str, str],
) -> None:
    host, db_name, username, password = live_test_target
    original = get_database(
        host=host,
        db_name=db_name,
        username=username,
        password=password,
    )
    same_identity_different_password = get_database(
        host=host,
        db_name=db_name,
        username=username,
        password=f"wrong-{uuid.uuid4().hex}",
    )

    assert same_identity_different_password is original
    _assert_live_round_trip(original, same_identity_different_password)


@pytest.mark.integration
def test_different_db_names_get_distinct_handles(
    live_test_target: tuple[str, str, str, str],
) -> None:
    host, _, username, password = live_test_target

    test_db = get_database(
        host=host,
        db_name="apacheta_test",
        username=username,
        password=password,
    )
    system_db = get_database(
        host=host,
        db_name="_system",
        username=username,
        password=password,
    )

    assert system_db is not test_db
    assert test_db.name == "apacheta_test"
    assert system_db.name == "_system"


@pytest.mark.integration
def test_different_usernames_get_distinct_handles_at_key_boundary(
    live_test_target: tuple[str, str, str, str],
) -> None:
    host, db_name, username, password = live_test_target

    test_user = get_database(
        host=host,
        db_name=db_name,
        username=username,
        password=password,
    )
    other_user = get_database(
        host=host,
        db_name=db_name,
        username=f"{username}_not_a_real_test_user",
        password=password,
    )

    assert other_user is not test_user
    assert test_user.username == username
    assert other_user.username != username


@pytest.mark.integration
def test_explicit_args_beat_poisoned_environment(
    monkeypatch: pytest.MonkeyPatch,
    live_test_target: tuple[str, str, str, str],
) -> None:
    host, db_name, username, password = live_test_target
    _set_arango_env(
        monkeypatch,
        host="http://203.0.113.1:1",
        db_name=f"wrong_db_{uuid.uuid4().hex}",
        username=f"wrong_user_{uuid.uuid4().hex}",
        password=f"wrong_password_{uuid.uuid4().hex}",
    )

    db = get_database(
        host=host,
        db_name=db_name,
        username=username,
        password=password,
    )

    assert db.name == db_name
    assert db.username == username
    _assert_live_round_trip(db, db)


@pytest.mark.integration
def test_environment_beats_poisoned_config_defaults(
    monkeypatch: pytest.MonkeyPatch,
    live_test_target: tuple[str, str, str, str],
) -> None:
    host, db_name, username, password = live_test_target
    cfg = ApachetaDBConfig()
    monkeypatch.setitem(cfg.db, "host", "203.0.113.1")
    monkeypatch.setitem(cfg.db, "port", "1")
    monkeypatch.setitem(cfg.db, "database", f"wrong_db_{uuid.uuid4().hex}")
    monkeypatch.setitem(cfg.db, "app_user", f"wrong_user_{uuid.uuid4().hex}")
    monkeypatch.setitem(cfg.db, "app_password", f"wrong_password_{uuid.uuid4().hex}")
    _set_arango_env(
        monkeypatch,
        host=host,
        db_name=db_name,
        username=username,
        password=password,
    )

    db = get_database()

    assert db.name == db_name
    assert db.username == username
    _assert_live_round_trip(db, db)
