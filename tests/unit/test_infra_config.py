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
