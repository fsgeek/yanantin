# src/yanantin/infra/config.py
"""Singleton database configuration with three-tier credentials.

Master credential store at ~/.yanantin/config/db.ini (0600).
Exposes admin, app, and test credentials separately.
Writes .env with test credentials only.

Reference: ~/projects/indaleko-test/db/db_config.py
"""

from __future__ import annotations

import configparser
import functools
import logging
import os
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path

from arango import ArangoClient
from arango.database import StandardDatabase

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_DIR = Path.home() / ".yanantin" / "config"
_DEFAULT_CONFIG_FILE = _DEFAULT_CONFIG_DIR / "db.ini"


class ApachetaDBConfig:
    """Singleton database configuration manager.

    Generates, loads, and exposes credentials for three tiers:
    admin (setup only), app (production via Pukara), test (.env).
    """

    default_config_file = _DEFAULT_CONFIG_FILE
    _instance: ApachetaDBConfig | None = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is not None:
            return cls._instance
        instance = super().__new__(cls)
        cls._instance = instance
        instance._initialized = False
        return instance

    def __init__(
        self,
        config_file: Path | None = None,
        host: str = "localhost",
        port: int = 8529,
        ssl: bool = False,
        admin_password: str | None = None,
        docker_managed: bool = True,
    ) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._config_file = Path(config_file) if config_file else self.default_config_file
        self._config = configparser.ConfigParser()

        if self._config_file.exists():
            self._load()
        else:
            self._generate(
                host=host,
                port=port,
                ssl=ssl,
                admin_password=admin_password,
                docker_managed=docker_managed,
            )

    @staticmethod
    def _random_password(length: int = 15) -> str:
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    @staticmethod
    def _random_username(length: int = 8) -> str:
        alphabet = string.ascii_lowercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _generate(
        self,
        host: str,
        port: int,
        ssl: bool,
        admin_password: str | None,
        docker_managed: bool,
    ) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        self._config["database"] = {
            "database": "apacheta",
            "timestamp": timestamp,
            "host": host,
            "port": str(port),
            "ssl": str(ssl).lower(),
            "admin_user": "root",
            "admin_passwd": admin_password or self._random_password(),
            "app_user": self._random_username(),
            "app_password": self._random_password(),
            "test_user": "apacheta_test",
            "test_password": self._random_password(),
        }
        if docker_managed:
            self._config["database"]["container"] = f"arango-yanantin-{timestamp}"
            self._config["database"]["volume"] = f"yanantin-db-{timestamp}"

        self._save()

    def _save(self) -> None:
        self._config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w") as f:
            self._config.write(f)
        os.chmod(self._config_file, 0o600)
        logger.info("Config saved to %s", self._config_file)

    def _load(self) -> None:
        self._config.read(self._config_file)
        if "database" not in self._config:
            raise ValueError(f"No [database] section in {self._config_file}")
        logger.info("Config loaded from %s", self._config_file)

    @property
    def db(self) -> configparser.SectionProxy:
        return self._config["database"]

    @property
    def is_docker_managed(self) -> bool:
        return "container" in self.db

    @property
    def host_url(self) -> str:
        scheme = "https" if self.db.get("ssl", "false") == "true" else "http"
        return f"{scheme}://{self.db['host']}:{self.db['port']}"

    def get_admin_credentials(self) -> dict:
        return {"username": self.db["admin_user"], "password": self.db["admin_passwd"]}

    def get_app_credentials(self) -> dict:
        return {"username": self.db["app_user"], "password": self.db["app_password"]}

    def get_test_credentials(self) -> dict:
        return {"username": self.db["test_user"], "password": self.db["test_password"]}

    def connect(self, tier: str = "test") -> StandardDatabase:
        """Connect to ArangoDB and return the shared database handle.

        Args:
            tier: "admin" (connects to _system), "app", or "test"

        Delegates to the module-level get_database singleton so all consumers
        share one connection per resolved target. Tier→target mapping stays here.
        """
        creds = {
            "admin": self.get_admin_credentials,
            "app": self.get_app_credentials,
            "test": self.get_test_credentials,
        }[tier]()

        db_name = "_system" if tier == "admin" else (
            self.db["database"] if tier == "app" else "apacheta_test"
        )

        return get_database(
            host=self.host_url,
            db_name=db_name,
            username=creds["username"],
            password=creds["password"],
        )

    def write_env(self, path: Path | None = None) -> None:
        """Write .env file with test credentials only."""
        if path is None:
            path = Path.cwd() / ".env"

        test = self.get_test_credentials()
        content = (
            f"YANANTIN_ARANGO_HOST={self.host_url}\n"
            f"YANANTIN_ARANGO_DB=apacheta_test\n"
            f"YANANTIN_ARANGO_USER={test['username']}\n"
            f"YANANTIN_ARANGO_PASSWORD={test['password']}\n"
        )
        path.write_text(content)
        logger.info("Wrote .env to %s (test credentials only).", path)

    def start(self, timeout: int = 120) -> bool:
        """Poll health endpoint until ArangoDB is ready."""
        import time
        import urllib.request
        import urllib.error

        url = f"{self.host_url}/_api/version"
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                req = urllib.request.urlopen(url, timeout=5)
                if req.status == 200:
                    logger.info("ArangoDB ready at %s", self.host_url)
                    return True
            except urllib.error.HTTPError as e:
                # 401 means ArangoDB is up but requires auth — that's ready
                if e.code == 401:
                    logger.info("ArangoDB ready at %s (auth required).", self.host_url)
                    return True
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(1)

        logger.warning("Timed out waiting for ArangoDB at %s", self.host_url)
        return False

    def delete_config(self) -> None:
        """Delete the config file."""
        if self._config_file.exists():
            self._config_file.unlink()
            logger.info("Deleted config %s", self._config_file)


# ── Shared database handle (the connection singleton) ─────────────────
#
# The ApachetaDBConfig object above is a singleton over *credentials*. What was
# historically missing — and what every ArangoClient construction site faked
# independently — is a singleton over the *database handle* itself. get_database
# is that: one client + db handle per distinct resolved (host, db_name,
# username). Resolution (explicit arg > env > config) happens BEFORE the memo,
# so two callers that mean the same target share one connection however they
# spelled the call.


def _resolve_db_params(
    host: str | None,
    db_name: str | None,
    username: str | None,
    password: str | None,
) -> tuple[str, str, str, str]:
    """Resolve each connection field: explicit arg > env var > config file.

    Resolution happens HERE, before memoization, so that two calls that mean
    the same target (e.g. get_database() and get_database(db_name='apacheta'))
    resolve to the same (host, db_name, username) key and do NOT split into two
    connections. The cache in get_database() sits BEHIND this function.
    """
    cfg = ApachetaDBConfig()  # the credential singleton (load-or-create)
    app_creds = cfg.get_app_credentials()

    host = host or os.environ.get("YANANTIN_ARANGO_HOST") or cfg.host_url
    db_name = db_name or os.environ.get("YANANTIN_ARANGO_DB") or cfg.db["database"]
    username = username or os.environ.get("YANANTIN_ARANGO_USER") or app_creds["username"]
    password = password or os.environ.get("YANANTIN_ARANGO_PASSWORD") or app_creds["password"]
    return host, db_name, username, password


# Identity is (host, db_name, username) ONLY — password is deliberately NOT in
# the cache key. Keying on password would split the singleton when the same
# user reconnects with a re-resolved-but-equal credential, which is exactly the
# failure the singleton exists to prevent. The password is used to establish the
# handle on first connect and then carried by the handle itself.
_HANDLE_CACHE: dict[tuple[str, str, str], StandardDatabase] = {}


def _connect_memoized(host: str, db_name: str, username: str, password: str) -> StandardDatabase:
    """One ArangoClient + db handle per distinct (host, db_name, username).

    Memoized on identity only; password establishes the handle but is not part
    of the key — see the cache comment above.
    """
    key = (host, db_name, username)
    handle = _HANDLE_CACHE.get(key)
    if handle is None:
        client = ArangoClient(hosts=host)
        handle = client.db(db_name, username=username, password=password)
        _HANDLE_CACHE[key] = handle
    return handle


def get_database(
    host: str | None = None,
    db_name: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> StandardDatabase:
    """Return the shared ArangoDB handle for a connection target.

    Resolve-then-memoize: fields resolve (explicit > env > config), then the
    resolved (host, db_name, username) determines identity. Two callers meaning
    the same target share one handle; different usernames (the tier boundary,
    enforced by the DB grant) or db_names get distinct handles. The password is
    NOT part of identity — re-resolving the same user does not split the handle.

    To reset (tests): get_database.cache_clear().
    """
    resolved = _resolve_db_params(host, db_name, username, password)
    return _connect_memoized(*resolved)


# expose cache_clear on the public name for test isolation
get_database.cache_clear = _HANDLE_CACHE.clear
