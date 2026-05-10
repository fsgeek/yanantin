# Database Setup Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `yanantin.infra` module that automates ArangoDB container lifecycle, database/user creation, and credential management with three-tier security.

**Architecture:** Singleton config manages credentials in INI file outside the project tree. Docker SDK wrapper handles container/volume lifecycle. Orchestrator wires them together with a CLI. Integration tests are refactored to use least-privilege credentials from `.env` with no admin access.

**Tech Stack:** Python 3.14, `docker` SDK 7.1.0, `python-arango` 8.2.6, `configparser`, `argparse`

**Spec:** `docs/specs/2026-04-15-db-setup-tooling-design.md`

**Reference code:**
- `~/projects/indaleko-test/utils/misc/i_docker.py` — Docker SDK patterns
- `~/projects/indaleko-test/db/db_config.py` — Singleton config, credential generation, health polling
- `~/projects/indaleko-test/db/db_setup.py` — Orchestrator wiring

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/yanantin/infra/__init__.py` | Package init, public exports |
| Create | `src/yanantin/infra/docker.py` | Docker SDK wrapper for container/volume ops |
| Create | `src/yanantin/infra/config.py` | Singleton config, credential tiers, INI I/O |
| Create | `src/yanantin/infra/orchestrator.py` | Setup/check/status/reset sequences |
| Create | `src/yanantin/infra/__main__.py` | CLI with argparse subcommands |
| Create | `tests/unit/test_infra_docker.py` | Docker wrapper tests (mocked SDK) |
| Create | `tests/unit/test_infra_config.py` | Config singleton tests |
| Create | `tests/unit/test_infra_orchestrator.py` | Orchestrator tests (mocked docker + config) |
| Modify | `tests/integration/test_arango_real.py` | Remove admin credentials, use `.env` |
| Modify | `tests/integration/test_arango_activity.py` | Same changes |

---

### Task 1: Package skeleton and Docker wrapper

**Files:**
- Create: `src/yanantin/infra/__init__.py`
- Create: `src/yanantin/infra/docker.py`
- Create: `tests/unit/test_infra_docker.py`

- [ ] **Step 1: Write failing test for Docker client initialization**

```python
# tests/unit/test_infra_docker.py
"""Tests for ApachetaDocker — Docker SDK wrapper.

All tests mock the docker SDK. No real Docker required.
"""
from unittest.mock import MagicMock, patch

import docker
import docker.errors
import pytest


def test_docker_init_connects():
    """ApachetaDocker connects to Docker on init."""
    with patch("yanantin.infra.docker.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client

        from yanantin.infra.docker import ApachetaDocker
        d = ApachetaDocker()

        mock_docker.from_env.assert_called_once()
        mock_client.ping.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_infra_docker.py::test_docker_init_connects -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yanantin.infra'`

- [ ] **Step 3: Create package init and Docker wrapper with init**

```python
# src/yanantin/infra/__init__.py
"""Infrastructure tooling for Yanantin.

Container lifecycle, database setup, credential management.
"""
```

```python
# src/yanantin/infra/docker.py
"""Docker SDK wrapper for ArangoDB container and volume lifecycle.

Thin layer over the docker Python SDK. Manages containers and volumes
with yanantin-prefixed names. No database logic — that belongs in
config.py and orchestrator.py.

Reference: ~/projects/indaleko-test/utils/misc/i_docker.py
"""

from __future__ import annotations

import logging
from enum import Enum

import docker
import docker.errors

logger = logging.getLogger(__name__)

_PREFIX = "yanantin"
_IMAGE = "arangodb/arangodb:latest"


class ContainerStatus(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    NOT_FOUND = "not_found"


class ApachetaDocker:
    """Manage ArangoDB Docker containers and volumes for Yanantin."""

    def __init__(self) -> None:
        try:
            self._client = docker.from_env()
        except docker.errors.DockerException as e:
            logger.error("Failed to connect to Docker: %s", e)
            raise
        self._client.ping()
        logger.info("Docker connection established.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_infra_docker.py::test_docker_init_connects -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for pull_image and create_container**

```python
# append to tests/unit/test_infra_docker.py

def test_pull_image_returns_true_when_changed():
    """pull_image returns True when the image ID changes."""
    with patch("yanantin.infra.docker.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = docker.errors

        old_img = MagicMock()
        old_img.id = "sha256:old"
        new_img = MagicMock()
        new_img.id = "sha256:new"

        mock_client.images.get.side_effect = [old_img, new_img]
        mock_client.images.pull.return_value = None

        from yanantin.infra.docker import ApachetaDocker
        d = ApachetaDocker()
        assert d.pull_image() is True


def test_pull_image_returns_false_when_unchanged():
    """pull_image returns False when image ID is the same."""
    with patch("yanantin.infra.docker.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = docker.errors

        img = MagicMock()
        img.id = "sha256:same"

        mock_client.images.get.side_effect = [img, img]

        from yanantin.infra.docker import ApachetaDocker
        d = ApachetaDocker()
        assert d.pull_image() is False


def test_create_container_with_correct_params():
    """create_container passes correct args to Docker SDK."""
    with patch("yanantin.infra.docker.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = docker.errors

        # Volume doesn't exist yet
        mock_client.volumes.list.return_value = []

        # Mock for pull_image (called internally by create_container)
        mock_img = MagicMock()
        mock_img.id = "sha256:test"
        mock_client.images.get.return_value = mock_img
        mock_docker.errors.ImageNotFound = docker.errors.ImageNotFound

        # Container doesn't exist yet
        mock_client.containers.get.side_effect = docker.errors.NotFound("nope")
        mock_docker.errors.NotFound = docker.errors.NotFound

        from yanantin.infra.docker import ApachetaDocker
        d = ApachetaDocker()
        d.create_container("arango-yanantin-test", "yanantin-db-test", "secret", port=8529)

        mock_client.containers.create.assert_called_once()
        call_kwargs = mock_client.containers.create.call_args
        assert call_kwargs.kwargs["name"] == "arango-yanantin-test"
        assert call_kwargs.kwargs["environment"] == {"ARANGO_ROOT_PASSWORD": "secret"}
        assert call_kwargs.kwargs["restart_policy"] == {"Name": "unless-stopped"}
        assert call_kwargs.kwargs["ports"] == {"8529/tcp": 8529}


def test_container_status_running():
    """container_status returns RUNNING for a running container."""
    with patch("yanantin.infra.docker.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = docker.errors

        mock_container = MagicMock()
        mock_container.status = "running"
        mock_client.containers.get.return_value = mock_container

        from yanantin.infra.docker import ApachetaDocker, ContainerStatus
        d = ApachetaDocker()
        assert d.container_status("test") == ContainerStatus.RUNNING


def test_container_status_not_found():
    """container_status returns NOT_FOUND when container doesn't exist."""
    with patch("yanantin.infra.docker.docker") as mock_docker:
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_docker.errors = docker.errors

        mock_client.containers.get.side_effect = docker.errors.NotFound("nope")

        from yanantin.infra.docker import ApachetaDocker, ContainerStatus
        d = ApachetaDocker()
        assert d.container_status("gone") == ContainerStatus.NOT_FOUND
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_infra_docker.py -v`
Expected: FAIL — `AttributeError: 'ApachetaDocker' object has no attribute 'pull_image'`

- [ ] **Step 7: Implement remaining Docker wrapper methods**

Add to `src/yanantin/infra/docker.py`:

```python
    def pull_image(self) -> bool:
        """Pull latest ArangoDB image. Returns True if image changed."""
        logger.info("Pulling %s", _IMAGE)
        try:
            current = self._client.images.get(_IMAGE)
            current_id = current.id
        except docker.errors.ImageNotFound:
            current_id = None

        self._client.images.pull(_IMAGE)
        new = self._client.images.get(_IMAGE)
        changed = current_id != new.id
        logger.info("Image %s.", "updated" if changed else "unchanged")
        return changed

    def create_volume(self, name: str) -> None:
        """Create a named volume if it doesn't exist."""
        existing = [v.name for v in self._client.volumes.list()]
        if name in existing:
            logger.warning("Volume %s already exists.", name)
            return
        self._client.volumes.create(name)
        logger.info("Created volume %s.", name)

    def delete_volume(self, name: str) -> None:
        """Delete a named volume."""
        try:
            self._client.volumes.get(name).remove()
            logger.info("Deleted volume %s.", name)
        except docker.errors.NotFound:
            logger.warning("Volume %s not found.", name)

    def create_container(
        self,
        name: str,
        volume: str,
        password: str,
        port: int = 8529,
    ) -> None:
        """Create an ArangoDB container with a named volume."""
        # Ensure volume exists
        self.create_volume(volume)

        # Check if container already exists
        try:
            self._client.containers.get(name)
            logger.warning("Container %s already exists.", name)
            return
        except docker.errors.NotFound:
            pass

        self.pull_image()
        self._client.containers.create(
            image=_IMAGE,
            name=name,
            ports={"8529/tcp": port},
            volumes={volume: {"bind": "/var/lib/arangodb3", "mode": "rw"}},
            environment={"ARANGO_ROOT_PASSWORD": password},
            restart_policy={"Name": "unless-stopped"},
            detach=True,
        )
        logger.info("Created container %s with volume %s on port %d.", name, volume, port)

    def start_container(self, name: str) -> None:
        """Start a container by name."""
        self._client.containers.get(name).start()
        logger.info("Started container %s.", name)

    def stop_container(self, name: str) -> None:
        """Stop a container by name."""
        self._client.containers.get(name).stop()
        logger.info("Stopped container %s.", name)

    def container_status(self, name: str) -> ContainerStatus:
        """Get the status of a container."""
        try:
            container = self._client.containers.get(name)
            if container.status == "running":
                return ContainerStatus.RUNNING
            return ContainerStatus.STOPPED
        except docker.errors.NotFound:
            return ContainerStatus.NOT_FOUND

    def delete_container(self, name: str, force: bool = False) -> None:
        """Delete a container. If force=True, stop it first."""
        try:
            container = self._client.containers.get(name)
        except docker.errors.NotFound:
            logger.warning("Container %s not found.", name)
            return

        if container.status == "running":
            if force:
                self.stop_container(name)
            else:
                logger.error("Container %s is running. Use force=True to stop first.", name)
                return

        container.remove()
        logger.info("Deleted container %s.", name)

    def list_containers(self, all: bool = False) -> list[str]:
        """List yanantin-prefixed containers."""
        return [
            c.name for c in self._client.containers.list(all=all)
            if _PREFIX in c.name
        ]

    def list_volumes(self) -> list[str]:
        """List yanantin-prefixed volumes."""
        return [
            v.name for v in self._client.volumes.list()
            if _PREFIX in v.name
        ]

    def update_container(self, name: str) -> None:
        """Update container to latest image, preserving volume and password."""
        if not self.pull_image():
            logger.info("Image unchanged, skipping container update.")
            return

        container = self._client.containers.get(name)
        mounts = container.attrs.get("HostConfig", {}).get("Mounts", [])
        volume = None
        for mount in mounts:
            if mount.get("Type") == "volume" and _PREFIX in mount.get("Source", ""):
                volume = mount["Source"]
                break

        if volume is None:
            raise ValueError(f"Could not find yanantin volume mount on container {name}")

        env_list = container.attrs.get("Config", {}).get("Env", [])
        password = None
        for entry in env_list:
            if entry.startswith("ARANGO_ROOT_PASSWORD="):
                password = entry.split("=", 1)[1]
                break

        if password is None:
            raise ValueError(f"Could not extract root password from container {name}")

        self.delete_container(name, force=True)
        self.create_container(name, volume, password)

    def reset_volume(self, name: str) -> None:
        """Delete and recreate a volume (wipes all data)."""
        self.delete_volume(name)
        self.create_volume(name)
        logger.info("Reset volume %s.", name)
```

- [ ] **Step 8: Run all Docker tests**

Run: `uv run pytest tests/unit/test_infra_docker.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add src/yanantin/infra/ tests/unit/test_infra_docker.py
git commit -m "feat(infra): add Docker SDK wrapper for ArangoDB container lifecycle"
```

---

### Task 2: Config singleton with credential tiers

**Files:**
- Create: `src/yanantin/infra/config.py`
- Create: `tests/unit/test_infra_config.py`

- [ ] **Step 1: Write failing tests for config generation and loading**

```python
# tests/unit/test_infra_config.py
"""Tests for ApachetaDBConfig — singleton config with credential tiers.

Tests use tmp_path to avoid touching real ~/.yanantin/config/.
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest


def test_generate_new_config_creates_file(tmp_path):
    """New config generates INI file with all credential tiers."""
    config_file = tmp_path / "db.ini"

    from yanantin.infra.config import ApachetaDBConfig
    # Reset singleton for testing
    ApachetaDBConfig._instance = None

    with patch.object(ApachetaDBConfig, "default_config_file", config_file):
        cfg = ApachetaDBConfig(config_file=config_file)

    assert config_file.exists()
    content = config_file.read_text()
    assert "admin_user" in content
    assert "admin_passwd" in content
    assert "app_user" in content
    assert "app_password" in content
    assert "test_user" in content
    assert "test_password" in content
    # Clean up singleton
    ApachetaDBConfig._instance = None


def test_config_has_random_passwords(tmp_path):
    """Generated passwords are random, not empty."""
    config_file = tmp_path / "db.ini"

    from yanantin.infra.config import ApachetaDBConfig
    ApachetaDBConfig._instance = None

    with patch.object(ApachetaDBConfig, "default_config_file", config_file):
        cfg = ApachetaDBConfig(config_file=config_file)

    creds = cfg.get_admin_credentials()
    assert len(creds["password"]) >= 15

    app = cfg.get_app_credentials()
    assert len(app["password"]) >= 15
    assert len(app["username"]) >= 8  # randomized username

    test = cfg.get_test_credentials()
    assert test["username"] == "apacheta_test"  # fixed, not random
    assert len(test["password"]) >= 15

    ApachetaDBConfig._instance = None


def test_config_roundtrip(tmp_path):
    """Config saved to file can be loaded back identically."""
    config_file = tmp_path / "db.ini"

    from yanantin.infra.config import ApachetaDBConfig
    ApachetaDBConfig._instance = None

    with patch.object(ApachetaDBConfig, "default_config_file", config_file):
        cfg1 = ApachetaDBConfig(config_file=config_file)
        admin1 = cfg1.get_admin_credentials()

    ApachetaDBConfig._instance = None

    with patch.object(ApachetaDBConfig, "default_config_file", config_file):
        cfg2 = ApachetaDBConfig(config_file=config_file)
        admin2 = cfg2.get_admin_credentials()

    assert admin1 == admin2
    ApachetaDBConfig._instance = None


def test_singleton_returns_same_instance(tmp_path):
    """Singleton pattern returns the same object."""
    config_file = tmp_path / "db.ini"

    from yanantin.infra.config import ApachetaDBConfig
    ApachetaDBConfig._instance = None

    with patch.object(ApachetaDBConfig, "default_config_file", config_file):
        cfg1 = ApachetaDBConfig(config_file=config_file)
        cfg2 = ApachetaDBConfig(config_file=config_file)

    assert cfg1 is cfg2
    ApachetaDBConfig._instance = None


def test_write_env_file(tmp_path):
    """write_env produces correct YANANTIN_ARANGO_* variables."""
    config_file = tmp_path / "db.ini"
    env_file = tmp_path / ".env"

    from yanantin.infra.config import ApachetaDBConfig
    ApachetaDBConfig._instance = None

    with patch.object(ApachetaDBConfig, "default_config_file", config_file):
        cfg = ApachetaDBConfig(config_file=config_file)
        cfg.write_env(env_file)

    content = env_file.read_text()
    assert "YANANTIN_ARANGO_HOST=" in content
    assert "YANANTIN_ARANGO_DB=apacheta_test" in content
    assert "YANANTIN_ARANGO_USER=apacheta_test" in content
    assert "YANANTIN_ARANGO_PASSWORD=" in content
    # Must NOT contain admin or app credentials
    assert "admin" not in content.lower().split("password")[0] if "password" in content.lower() else True
    assert "ARANGO_ADMIN" not in content

    ApachetaDBConfig._instance = None


def test_remote_config_has_no_container_fields(tmp_path):
    """Remote config omits container and volume."""
    config_file = tmp_path / "db.ini"

    from yanantin.infra.config import ApachetaDBConfig
    ApachetaDBConfig._instance = None

    with patch.object(ApachetaDBConfig, "default_config_file", config_file):
        cfg = ApachetaDBConfig(
            config_file=config_file,
            host="remote.example.com",
            port=8529,
            ssl=True,
            admin_password="given",
            docker_managed=False,
        )

    content = config_file.read_text()
    assert "container" not in content
    assert "volume" not in content
    assert "ssl = true" in content

    ApachetaDBConfig._instance = None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_infra_config.py -v`
Expected: FAIL — `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement config singleton**

```python
# src/yanantin/infra/config.py
"""Singleton database configuration with three-tier credentials.

Master credential store at ~/.yanantin/config/db.ini (0600).
Exposes admin, app, and test credentials separately.
Writes .env with test credentials only.

Reference: ~/projects/indaleko-test/db/db_config.py
"""

from __future__ import annotations

import configparser
import logging
import os
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path

from arango import ArangoClient

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

    def connect(self, tier: str = "test") -> object:
        """Connect to ArangoDB and return a database object.

        Args:
            tier: "admin" (connects to _system), "app", or "test"
        """
        creds = {
            "admin": self.get_admin_credentials,
            "app": self.get_app_credentials,
            "test": self.get_test_credentials,
        }[tier]()

        db_name = "_system" if tier == "admin" else (
            self.db["database"] if tier == "app" else "apacheta_test"
        )

        client = ArangoClient(hosts=self.host_url)
        return client.db(db_name, username=creds["username"], password=creds["password"])

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

    def start(self, timeout: int = 60) -> bool:
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
```

- [ ] **Step 4: Run all config tests**

Run: `uv run pytest tests/unit/test_infra_config.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/infra/config.py tests/unit/test_infra_config.py
git commit -m "feat(infra): add singleton config with three-tier credentials"
```

---

### Task 3: Orchestrator

**Files:**
- Create: `src/yanantin/infra/orchestrator.py`
- Create: `tests/unit/test_infra_orchestrator.py`

- [ ] **Step 1: Write failing tests for setup and check sequences**

```python
# tests/unit/test_infra_orchestrator.py
"""Tests for ApachetaDBSetup — orchestrator.

Mocks Docker and ArangoDB. Tests the sequence, not the infrastructure.
"""
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


def test_setup_creates_database_and_users(tmp_path):
    """setup() creates databases, users, and writes .env."""
    config_file = tmp_path / "db.ini"
    env_file = tmp_path / ".env"

    from yanantin.infra.config import ApachetaDBConfig
    ApachetaDBConfig._instance = None

    with patch.object(ApachetaDBConfig, "default_config_file", config_file):
        cfg = ApachetaDBConfig(config_file=config_file)

    mock_docker = MagicMock()
    mock_sys_db = MagicMock()
    mock_sys_db.has_database.return_value = False
    mock_sys_db.users.return_value = []

    with patch("yanantin.infra.orchestrator.ApachetaDocker", return_value=mock_docker), \
         patch.object(cfg, "start", return_value=True), \
         patch.object(cfg, "connect") as mock_connect:
        mock_connect.return_value = mock_sys_db

        from yanantin.infra.orchestrator import ApachetaDBSetup
        setup = ApachetaDBSetup(cfg, env_path=env_file)
        setup.setup()

    # Should create both databases
    assert mock_sys_db.create_database.call_count == 2
    # Should create both users
    assert mock_sys_db.create_user.call_count == 2
    # Should write .env
    assert env_file.exists()
    content = env_file.read_text()
    assert "YANANTIN_ARANGO_DB=apacheta_test" in content

    ApachetaDBConfig._instance = None


def test_check_succeeds_when_db_reachable(tmp_path):
    """check() returns True when database is reachable."""
    config_file = tmp_path / "db.ini"

    from yanantin.infra.config import ApachetaDBConfig
    ApachetaDBConfig._instance = None

    with patch.object(ApachetaDBConfig, "default_config_file", config_file):
        cfg = ApachetaDBConfig(config_file=config_file)

    mock_docker = MagicMock()

    from yanantin.infra.docker import ContainerStatus
    mock_docker.container_status.return_value = ContainerStatus.RUNNING

    mock_db = MagicMock()
    mock_db.properties.return_value = {"name": "apacheta_test"}

    with patch("yanantin.infra.orchestrator.ApachetaDocker", return_value=mock_docker), \
         patch.object(cfg, "connect", return_value=mock_db):
        from yanantin.infra.orchestrator import ApachetaDBSetup
        setup = ApachetaDBSetup(cfg)
        result = setup.check()

    assert result is True
    ApachetaDBConfig._instance = None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_infra_orchestrator.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Implement orchestrator**

```python
# src/yanantin/infra/orchestrator.py
"""Orchestrator for ArangoDB setup, check, and lifecycle.

Wires ApachetaDocker and ApachetaDBConfig into operational sequences.

Reference: ~/projects/indaleko-test/db/db_setup.py
"""

from __future__ import annotations

import logging
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
```

- [ ] **Step 4: Run orchestrator tests**

Run: `uv run pytest tests/unit/test_infra_orchestrator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/infra/orchestrator.py tests/unit/test_infra_orchestrator.py
git commit -m "feat(infra): add orchestrator for setup/check/start/stop/reset"
```

---

### Task 4: CLI

**Files:**
- Create: `src/yanantin/infra/__main__.py`

- [ ] **Step 1: Write failing test for CLI invocation**

```python
# append to tests/unit/test_infra_orchestrator.py

import subprocess
import sys

def test_cli_help():
    """CLI --help exits cleanly."""
    result = subprocess.run(
        [sys.executable, "-m", "yanantin.infra", "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "setup" in result.stdout
    assert "check" in result.stdout
    assert "status" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_infra_orchestrator.py::test_cli_help -v`
Expected: FAIL — no `__main__.py`

- [ ] **Step 3: Implement CLI**

```python
# src/yanantin/infra/__main__.py
"""CLI for Yanantin database infrastructure.

Usage: uv run python -m yanantin.infra [command]

Default behavior: check if config exists, setup if not.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import sys
from pathlib import Path

from yanantin.infra.config import ApachetaDBConfig
from yanantin.infra.orchestrator import ApachetaDBSetup


def cmd_setup(args: argparse.Namespace) -> None:
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    if setup.setup():
        print("Setup complete.")
    else:
        print("Setup failed.", file=sys.stderr)
        sys.exit(1)


def cmd_check(args: argparse.Namespace) -> None:
    if not ApachetaDBConfig.default_config_file.exists():
        print("No config found. Run: uv run python -m yanantin.infra setup")
        sys.exit(1)
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    if setup.check():
        print("All checks passed.")
    else:
        print("Check failed.", file=sys.stderr)
        sys.exit(1)


def cmd_start(args: argparse.Namespace) -> None:
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    setup.start()
    print(f"Started {config.db.get('container', 'remote instance')}.")


def cmd_stop(args: argparse.Namespace) -> None:
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    setup.stop()
    print(f"Stopped {config.db.get('container', 'remote instance')}.")


def cmd_status(args: argparse.Namespace) -> None:
    if not ApachetaDBConfig.default_config_file.exists():
        print("No config found. Run: uv run python -m yanantin.infra setup")
        return
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    info = setup.status()
    for k, v in info.items():
        print(f"  {k}: {v}")


def cmd_reset(args: argparse.Namespace) -> None:
    confirm = input("This will DELETE all data. Type 'yes' to confirm: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        return
    config = ApachetaDBConfig()
    setup = ApachetaDBSetup(config)
    if setup.reset():
        print("Reset complete.")
    else:
        print("Reset failed.", file=sys.stderr)
        sys.exit(1)


def cmd_connect(args: argparse.Namespace) -> None:
    password = args.admin_password
    if not password:
        password = getpass.getpass("Admin password for remote instance: ")

    ApachetaDBConfig._instance = None
    config = ApachetaDBConfig(
        host=args.host,
        port=args.port,
        ssl=args.ssl,
        admin_password=password,
        docker_managed=False,
    )
    setup = ApachetaDBSetup(config)
    if setup.setup():
        print("Remote connection configured.")
    else:
        print("Setup failed.", file=sys.stderr)
        sys.exit(1)


def cmd_default(args: argparse.Namespace) -> None:
    if ApachetaDBConfig.default_config_file.exists():
        cmd_check(args)
    else:
        cmd_setup(args)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Yanantin database infrastructure",
        prog="python -m yanantin.infra",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.set_defaults(func=cmd_default)

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="Stand up ArangoDB from nothing").set_defaults(func=cmd_setup)
    sub.add_parser("check", help="Verify everything is working").set_defaults(func=cmd_check)
    sub.add_parser("start", help="Start the container").set_defaults(func=cmd_start)
    sub.add_parser("stop", help="Stop the container").set_defaults(func=cmd_stop)
    sub.add_parser("status", help="Show container and database state").set_defaults(func=cmd_status)

    reset_p = sub.add_parser("reset", help="Wipe and recreate")
    reset_p.add_argument("--rebuild", action="store_true")
    reset_p.set_defaults(func=cmd_reset)

    connect_p = sub.add_parser("connect", help="Configure for remote instance")
    connect_p.add_argument("--host", required=True)
    connect_p.add_argument("--port", type=int, default=8529)
    connect_p.add_argument("--ssl", action="store_true")
    connect_p.add_argument("--admin-password", default=None)
    connect_p.set_defaults(func=cmd_connect)

    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run CLI test**

Run: `uv run pytest tests/unit/test_infra_orchestrator.py::test_cli_help -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/yanantin/infra/__main__.py
git commit -m "feat(infra): add CLI for database lifecycle management"
```

---

### Task 5: Update public exports

**Files:**
- Modify: `src/yanantin/infra/__init__.py`

- [ ] **Step 1: Update __init__.py with public exports**

```python
# src/yanantin/infra/__init__.py
"""Infrastructure tooling for Yanantin.

Container lifecycle, database setup, credential management.
"""

from yanantin.infra.config import ApachetaDBConfig
from yanantin.infra.docker import ApachetaDocker, ContainerStatus
from yanantin.infra.orchestrator import ApachetaDBSetup

__all__ = [
    "ApachetaDBConfig",
    "ApachetaDocker",
    "ApachetaDBSetup",
    "ContainerStatus",
]
```

- [ ] **Step 2: Run full test suite for infra module**

Run: `uv run pytest tests/unit/test_infra_*.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add src/yanantin/infra/__init__.py
git commit -m "feat(infra): add public exports"
```

---

### Task 6: Refactor integration tests to remove admin credentials

**Files:**
- Modify: `tests/integration/test_arango_real.py:49-59` (credential section)
- Modify: `tests/integration/test_arango_real.py:62-72` (availability check)
- Modify: `tests/integration/test_arango_real.py:75-116` (session fixture)
- Modify: `tests/integration/test_arango_activity.py:37-47` (credential section)
- Modify: `tests/integration/test_arango_activity.py:50-60` (availability check)
- Modify: `tests/integration/test_arango_activity.py:63-80+` (session fixture)

- [ ] **Step 1: Refactor test_arango_real.py credentials and fixture**

Replace the credential block (lines 49-59) with:

```python
# Connection parameters — from .env via root conftest.py
ARANGO_HOST = os.environ.get("YANANTIN_ARANGO_HOST", "http://localhost:8529")
ARANGO_DB = os.environ.get("YANANTIN_ARANGO_DB", "apacheta_test")
ARANGO_USER = os.environ.get("YANANTIN_ARANGO_USER", "apacheta_test")
ARANGO_PASSWORD = os.environ.get("YANANTIN_ARANGO_PASSWORD", "")
```

Replace `check_arango_available()` with:

```python
def check_arango_available() -> bool:
    """Check if ArangoDB test database is reachable with test credentials."""
    try:
        from arango import ArangoClient
        client = ArangoClient(hosts=ARANGO_HOST)
        db = client.db(ARANGO_DB, username=ARANGO_USER, password=ARANGO_PASSWORD)
        db.collections()
        client.close()
        return True
    except Exception:
        return False
```

Replace the `arango_session` fixture with:

```python
@pytest.fixture(scope="session")
def arango_session():
    """Session-scoped fixture: verify test database is reachable.

    Precondition: database and user created by infra setup tool.
    Run `uv run python -m yanantin.infra setup` before running
    integration tests. This fixture only checks connectivity —
    no admin operations, no database creation, no user management.
    """
    if not check_arango_available():
        pytest.skip(
            f"ArangoDB test database not available at {ARANGO_HOST}. "
            "Run: uv run python -m yanantin.infra setup"
        )
    yield
```

Update the `backend` fixture to use the new variable names:

```python
@pytest.fixture
def backend(arango_session):
    """Function-scoped fixture: fresh backend with clean collections."""
    db = ArangoDBBackend(
        host=ARANGO_HOST,
        db_name=ARANGO_DB,
        username=ARANGO_USER,
        password=ARANGO_PASSWORD,
    )
    # Truncate all collections for clean state
    ...  # keep existing truncation logic
```

Also update the docstring at the top of the file to remove references to admin credentials and hardcoded IPs.

- [ ] **Step 2: Make the same changes in test_arango_activity.py**

Same credential block replacement, same `check_arango_available()` replacement, same fixture simplification. Update variable references from `ARANGO_TEST_USER`/`ARANGO_TEST_PASSWORD` to `ARANGO_USER`/`ARANGO_PASSWORD` throughout.

- [ ] **Step 3: Run existing unit tests to verify no breakage**

Run: `uv run pytest tests/unit/ -v --timeout=60`
Expected: All existing tests PASS (integration tests will skip without DB)

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_arango_real.py tests/integration/test_arango_activity.py
git commit -m "refactor(tests): remove admin credentials from integration tests

Integration tests now use YANANTIN_ARANGO_* env vars from .env.
No admin access required — database setup handled by infra tool.
Tests skip gracefully when database is unavailable."
```

---

### Task 7: End-to-end smoke test

This task verifies the full pipeline works on a machine with Docker.

- [ ] **Step 1: Run the setup tool**

```bash
uv run python -m yanantin.infra setup
```

Expected: Container created, databases initialized, `.env` written, summary printed.

- [ ] **Step 2: Verify .env was written correctly**

```bash
cat .env
```

Expected: Four `YANANTIN_ARANGO_*` lines with test credentials.

- [ ] **Step 3: Run the check command**

```bash
uv run python -m yanantin.infra check
```

Expected: "All checks passed."

- [ ] **Step 4: Run the status command**

```bash
uv run python -m yanantin.infra status
```

Expected: Container running, test_db reachable.

- [ ] **Step 5: Run integration tests**

```bash
uv run pytest tests/integration/ -v --timeout=120
```

Expected: Integration tests run against the local Docker ArangoDB, all PASS.

- [ ] **Step 6: Run full test suite**

```bash
uv run pytest --timeout=120
```

Expected: All tests PASS (unit + integration).

- [ ] **Step 7: Stop and restart**

```bash
uv run python -m yanantin.infra stop
uv run python -m yanantin.infra status
uv run python -m yanantin.infra start
uv run python -m yanantin.infra check
```

Expected: Stop succeeds, status shows stopped, start succeeds, check passes.

- [ ] **Step 8: Commit any fixes discovered during smoke test**
