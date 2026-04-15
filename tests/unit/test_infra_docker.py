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
