"""Apacheta: the tensor database. Each traveler adds a stone."""

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.storage_obfuscator import StorageObfuscator, TransparentObfuscator


def connect(tier: str = "app") -> ApachetaInterface:
    """Connect to Apacheta backed by the provisioned ArangoDB instance.

    Reads credentials from ~/.yanantin/config/db.ini. The database must
    already be provisioned via `python -m yanantin.infra setup`.

    Args:
        tier: "app" for application use, "test" for integration tests.
              Admin is not exposed here — it's for setup, not runtime.

    Returns:
        An ApachetaInterface backed by ArangoDB.

    Raises:
        FileNotFoundError: If db.ini doesn't exist (database not provisioned).
        ConnectionError: If ArangoDB is unreachable.
    """
    if tier not in ("app", "test"):
        raise ValueError(f"tier must be 'app' or 'test', got {tier!r}")

    from yanantin.apacheta.backends.arango import ArangoDBBackend
    from yanantin.infra.config import ApachetaDBConfig

    config = ApachetaDBConfig()
    creds = config.get_app_credentials() if tier == "app" else config.get_test_credentials()
    db_name = config.db["database"] if tier == "app" else "apacheta_test"

    return ArangoDBBackend(
        host=config.host_url,
        db_name=db_name,
        username=creds["username"],
        password=creds["password"],
    )


__all__ = ["ApachetaInterface", "StorageObfuscator", "TransparentObfuscator", "connect"]
