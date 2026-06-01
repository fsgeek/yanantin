from __future__ import annotations

from collections.abc import Iterator

import pytest

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.interface.errors import (
    BackendAuthError,
    BackendUnreachableError,
    DatabaseNotProvisionedError,
)
from yanantin.infra.config import ApachetaDBConfig, get_database


DB_NAME = "apacheta_test"
DEAD_HOST = "http://127.0.0.1:9"
MISSING_DB_NAME = "apacheta_missing_conn_error_test"
XFAIL_REASON = (
    "discrimination bug, see "
    "docs/plans/2026-06-01-arango-conn-error-discrimination-is-wrong.md"
)


@pytest.fixture(autouse=True)
def clear_database_cache() -> Iterator[None]:
    get_database.cache_clear()
    yield
    get_database.cache_clear()


def _live_target() -> tuple[str, str, str, str]:
    cfg = ApachetaDBConfig()
    tc = cfg.get_test_credentials()
    return cfg.host_url, DB_NAME, tc["username"], tc["password"]


def _construct_backend(
    *,
    host: str,
    db_name: str,
    username: str,
    password: str,
) -> None:
    get_database.cache_clear()
    ArangoDBBackend(
        host=host,
        db_name=db_name,
        username=username,
        password=password,
    )


def _require_live_apacheta_test() -> None:
    host, db_name, username, password = _live_target()
    try:
        _construct_backend(
            host=host,
            db_name=db_name,
            username=username,
            password=password,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Live ArangoDB {db_name!r} at {host} is unavailable"
        ) from exc
    finally:
        get_database.cache_clear()


def test_rejected_credentials_raise_auth_error_with_auth_remediation() -> None:
    host, db_name, username, _password = _live_target()

    with pytest.raises(BackendAuthError) as raised:
        _construct_backend(
            host=host,
            db_name=db_name,
            username=f"{username}_wrong",
            password="definitely-wrong-for-live-auth-test",
        )

    message = str(raised.value).lower()
    assert isinstance(raised.value, ConnectionError)
    assert "authentication" in message
    assert "credentials" in message
    assert "access" in message
    assert "provisioned by an admin" not in message
    assert "host, port, and network" not in message


@pytest.mark.xfail(reason=XFAIL_REASON, strict=True, raises=ConnectionError)
def test_transport_connection_failure_raises_unreachable_error_with_network_remediation() -> None:
    _require_live_apacheta_test()
    _host, db_name, username, password = _live_target()

    with pytest.raises(BackendUnreachableError) as raised:
        _construct_backend(
            host=DEAD_HOST,
            db_name=db_name,
            username=username,
            password=password,
        )

    message = str(raised.value).lower()
    assert isinstance(raised.value, ConnectionError)
    assert "cannot reach" in message
    assert "host, port, and network" in message
    assert DEAD_HOST.lower() in message
    assert "provisioned by an admin" not in message
    assert "credentials" not in message


@pytest.mark.xfail(reason=XFAIL_REASON, strict=True, raises=BackendAuthError)
def test_missing_database_raises_not_provisioned_error_with_admin_remediation() -> None:
    _require_live_apacheta_test()
    host, _db_name, username, password = _live_target()

    with pytest.raises(DatabaseNotProvisionedError) as raised:
        _construct_backend(
            host=host,
            db_name=MISSING_DB_NAME,
            username=username,
            password=password,
        )

    message = str(raised.value).lower()
    assert isinstance(raised.value, ConnectionError)
    assert "database" in message
    assert "provisioned by an admin" in message
    assert MISSING_DB_NAME in message
    assert "credentials" not in message
    assert "host, port, and network" not in message
