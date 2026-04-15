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
