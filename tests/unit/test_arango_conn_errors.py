from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from arango.exceptions import ArangoClientError, ArangoServerError, ServerConnectionError
from arango.request import Request
from arango.response import Response

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.interface.errors import (
    BackendAuthError,
    BackendUnreachableError,
    DatabaseNotProvisionedError,
)


HOST = "http://db.example.test:8529"
DB_NAME = "apacheta_test"
USERNAME = "app_user"
PASSWORD = "bad-secret"


def _driver_server_error(
    status_code: int,
    status_text: str,
    *,
    error_message: str | None = None,
    error_code: int | None = None,
    error_type: type[ArangoServerError] = ArangoServerError,
) -> ArangoServerError:
    response = Response(
        method="get",
        url=f"{HOST}/_db/{DB_NAME}/_api/collection",
        headers={},
        status_code=status_code,
        status_text=status_text,
        raw_body="",
    )
    response.error_message = error_message
    response.error_code = error_code
    request = Request(method="get", endpoint="/_api/collection")
    return error_type(response, request)


def _construct_backend_with_probe_failure(error: Exception):
    fake_db = MagicMock()
    fake_db.collections.side_effect = error

    fake_client = MagicMock()
    fake_client.db.return_value = fake_db

    with patch("yanantin.apacheta.backends.arango.ArangoClient", return_value=fake_client):
        ArangoDBBackend(
            host=HOST,
            db_name=DB_NAME,
            username=USERNAME,
            password=PASSWORD,
        )

    return fake_client, fake_db


def test_all_discriminated_errors_remain_connectionerror_subclasses() -> None:
    """Backward-compat contract: every discriminated subclass is still a
    ConnectionError, so existing `except ConnectionError` call sites keep
    working. Asserted on the classes directly, independent of construction."""
    for cls in (BackendAuthError, BackendUnreachableError, DatabaseNotProvisionedError):
        assert issubclass(cls, ConnectionError), f"{cls.__name__} must subclass ConnectionError"


@pytest.mark.parametrize("status_code", [401, 403])
def test_rejected_credentials_raise_auth_error_with_auth_remediation(status_code: int) -> None:
    error = _driver_server_error(
        status_code,
        "Unauthorized" if status_code == 401 else "Forbidden",
        error_message="not authorized to execute this request",
        error_code=11,
    )

    with pytest.raises(BackendAuthError) as raised:
        _construct_backend_with_probe_failure(error)

    message = str(raised.value).lower()
    assert isinstance(raised.value, ConnectionError)
    assert "authentication" in message
    assert "credentials" in message
    assert "access" in message
    assert "provisioned by an admin" not in message
    assert "host, port, and network" not in message


def test_transport_connection_failure_raises_unreachable_error_with_network_remediation() -> None:
    error = _driver_server_error(
        0,
        "Connection refused",
        error_message="failed to establish a new connection",
        error_type=ServerConnectionError,
    )

    with pytest.raises(BackendUnreachableError) as raised:
        _construct_backend_with_probe_failure(error)

    message = str(raised.value).lower()
    assert isinstance(raised.value, ConnectionError)
    assert "cannot reach" in message
    assert "host, port, and network" in message
    assert HOST.lower() in message
    assert "provisioned by an admin" not in message
    assert "credentials" not in message


def test_client_side_transport_failure_raises_unreachable_error() -> None:
    error = ArangoClientError("DNS lookup failed for db.example.test")

    with pytest.raises(BackendUnreachableError) as raised:
        _construct_backend_with_probe_failure(error)

    message = str(raised.value).lower()
    assert isinstance(raised.value, ConnectionError)
    assert "cannot reach" in message
    assert "host, port, and network" in message
    assert "dns lookup failed" in message
    assert "provisioned by an admin" not in message


def test_missing_database_raises_not_provisioned_error_with_admin_remediation() -> None:
    error = _driver_server_error(
        404,
        "Not Found",
        error_message="database not found",
        error_code=1228,
    )

    with pytest.raises(DatabaseNotProvisionedError) as raised:
        _construct_backend_with_probe_failure(error)

    message = str(raised.value).lower()
    assert isinstance(raised.value, ConnectionError)
    assert "database" in message
    assert "provisioned by an admin" in message
    assert DB_NAME in message
    assert "credentials" not in message
    assert "host, port, and network" not in message


def test_unknown_probe_failure_remains_plain_connection_error_without_specific_diagnosis() -> None:
    error = _driver_server_error(
        500,
        "Internal Server Error",
        error_message="temporary coordinator failure",
        error_code=500,
    )

    with pytest.raises(ConnectionError) as raised:
        _construct_backend_with_probe_failure(error)

    message = str(raised.value).lower()
    assert type(raised.value) is ConnectionError
    assert not isinstance(
        raised.value,
        (BackendAuthError, BackendUnreachableError, DatabaseNotProvisionedError),
    )
    assert "unexpected failure" in message
    assert "temporary coordinator failure" in message
    assert "provisioned by an admin" not in message
    assert "credentials" not in message
    assert "host, port, and network" not in message


def test_failed_probe_stops_before_collection_provisioning() -> None:
    error = _driver_server_error(
        404,
        "Not Found",
        error_message="database not found",
        error_code=1228,
    )
    fake_db = MagicMock()
    fake_db.collections.side_effect = error

    fake_client = MagicMock()
    fake_client.db.return_value = fake_db

    with patch("yanantin.apacheta.backends.arango.ArangoClient", return_value=fake_client):
        with pytest.raises(DatabaseNotProvisionedError):
            ArangoDBBackend(
                host=HOST,
                db_name=DB_NAME,
                username=USERNAME,
                password=PASSWORD,
            )

    fake_client.db.assert_called_once_with(DB_NAME, username=USERNAME, password=PASSWORD)
    fake_db.collections.assert_called_once_with()
    fake_db.has_collection.assert_not_called()
    fake_db.create_collection.assert_not_called()
