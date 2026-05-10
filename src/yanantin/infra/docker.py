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
