# src/yanantin/infra/orchestrator.py
"""Orchestrator for ArangoDB setup, check, and lifecycle.

Wires ApachetaDocker and ApachetaDBConfig into operational sequences.

Reference: ~/projects/indaleko-test/db/db_setup.py
"""

from __future__ import annotations

import configparser
import logging
import os
from pathlib import Path

from yanantin.infra.config import ApachetaDBConfig
from yanantin.infra.docker import ApachetaDocker, ContainerStatus

logger = logging.getLogger(__name__)


class ApachetaDBSetup:
    """Orchestrate database setup and lifecycle operations."""

    def __init__(
        self,
        config: ApachetaDBConfig,
        env_path: Path | None = None,
    ) -> None:
        self._config = config
        self._env_path = env_path or Path.cwd() / ".env"

    def setup(self) -> bool:
        """Full setup: container + databases + users + .env."""
        cfg = self._config

        # Docker container (if docker-managed)
        if cfg.is_docker_managed:
            docker = ApachetaDocker()
            docker.create_container(
                name=cfg.db["container"],
                volume=cfg.db["volume"],
                password=cfg.get_admin_credentials()["password"],
                port=int(cfg.db["port"]),
            )
            docker.start_container(cfg.db["container"])

        # Wait for ArangoDB
        if not cfg.start():
            logger.error("ArangoDB did not become ready.")
            return False

        # Connect as admin
        sys_db = cfg.connect("admin")

        # Create production database and user
        app = cfg.get_app_credentials()
        if not sys_db.has_database(cfg.db["database"]):
            sys_db.create_database(cfg.db["database"])
            logger.info("Created database %s.", cfg.db["database"])

        if not any(u["username"] == app["username"] for u in sys_db.users()):
            sys_db.create_user(
                username=app["username"],
                password=app["password"],
                active=True,
            )
        sys_db.update_permission(app["username"], "rw", cfg.db["database"])
        logger.info("App user %s configured.", app["username"])

        # Create test database and user
        test = cfg.get_test_credentials()
        if not sys_db.has_database("apacheta_test"):
            sys_db.create_database("apacheta_test")
            logger.info("Created database apacheta_test.")

        if not any(u["username"] == test["username"] for u in sys_db.users()):
            sys_db.create_user(
                username=test["username"],
                password=test["password"],
                active=True,
            )
        sys_db.update_permission(test["username"], "rw", "apacheta_test")
        logger.info("Test user %s configured.", test["username"])

        # Verify connections
        try:
            test_db = cfg.connect("test")
            test_db.properties()
            logger.info("Test connection verified.")
        except Exception as e:
            logger.error("Test connection failed: %s", e)
            return False

        try:
            app_db = cfg.connect("app")
            app_db.properties()
            logger.info("App connection verified.")
        except Exception as e:
            logger.error("App connection failed: %s", e)
            return False

        # Write .env
        cfg.write_env(self._env_path)

        logger.info("Setup complete.")
        return True

    def ensure_reader(
        self,
        databases: list[str],
        reader_file: Path | None = None,
        username: str = "yanantin_reader",
    ) -> Path:
        """A read-only account for consumers that only count or read (qhaway's reground).

        Grants "ro" on exactly ``databases`` and nothing else, and writes its
        credentials to ``reader_file`` (default: reader.ini beside db.ini, 0600),
        which holds no admin key, so a consumer never has to read db.ini.
        Idempotent: an existing reader.ini keeps its password.
        """
        cfg = self._config
        reader_file = reader_file or cfg._config_file.parent / "reader.ini"
        stored = configparser.ConfigParser()
        stored.read(reader_file)
        known = stored.has_section("database") and stored["database"].get("user") == username
        password = stored["database"]["password"] if known else ApachetaDBConfig._random_password(24)

        sys_db = cfg.connect("admin")
        if any(u["username"] == username for u in sys_db.users()):
            if not known:
                sys_db.update_user(username=username, password=password, active=True)
        else:
            sys_db.create_user(username=username, password=password, active=True)
        for db_name in databases:
            sys_db.update_permission(username, "ro", db_name)

        out = configparser.ConfigParser()
        out["database"] = {
            "host": cfg.db["host"],
            "port": cfg.db["port"],
            "ssl": cfg.db.get("ssl", "false"),
            "user": username,
            "password": password,
            "databases": ",".join(databases),
        }
        reader_file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(reader_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            out.write(f)
        os.chmod(reader_file, 0o600)
        logger.info("Reader %s: ro on %s; credentials in %s", username, databases, reader_file)
        return reader_file

    def check(self) -> bool:
        """Verify container, database, and credentials."""
        cfg = self._config

        if cfg.is_docker_managed:
            docker = ApachetaDocker()
            status = docker.container_status(cfg.db["container"])
            if status != ContainerStatus.RUNNING:
                logger.warning("Container %s is %s.", cfg.db["container"], status.value)
                return False

        try:
            db = cfg.connect("test")
            db.properties()
            logger.info("Check passed: database reachable, credentials valid.")
            return True
        except Exception as e:
            logger.error("Check failed: %s", e)
            return False

    def start(self) -> None:
        """Start the Docker container."""
        cfg = self._config
        if not cfg.is_docker_managed:
            logger.info("Remote instance — no container to start.")
            return
        docker = ApachetaDocker()
        docker.start_container(cfg.db["container"])

    def stop(self) -> None:
        """Stop the Docker container."""
        cfg = self._config
        if not cfg.is_docker_managed:
            logger.info("Remote instance — no container to stop.")
            return
        docker = ApachetaDocker()
        docker.stop_container(cfg.db["container"])

    def status(self) -> dict:
        """Return current status information."""
        cfg = self._config
        result = {"host": cfg.host_url, "docker_managed": cfg.is_docker_managed}

        if cfg.is_docker_managed:
            docker = ApachetaDocker()
            result["container"] = cfg.db["container"]
            result["container_status"] = docker.container_status(cfg.db["container"]).value

        try:
            db = cfg.connect("test")
            db.properties()
            result["test_db"] = "reachable"
        except Exception:
            result["test_db"] = "unreachable"

        return result

    def reset(self) -> bool:
        """Wipe volume, regenerate credentials, re-setup."""
        cfg = self._config
        if not cfg.is_docker_managed:
            logger.error("Cannot reset a remote instance.")
            return False

        docker = ApachetaDocker()
        docker.delete_container(cfg.db["container"], force=True)
        docker.reset_volume(cfg.db["volume"])

        # Regenerate config
        cfg.delete_config()
        ApachetaDBConfig._instance = None

        new_cfg = ApachetaDBConfig()
        self._config = new_cfg
        return self.setup()
