"""Abstract base for machine identity collectors."""

from __future__ import annotations


def _get_machine_id() -> str:
    """Read /etc/machine-id or generate a deterministic fallback.

    Linux systems provide /etc/machine-id as a stable per-installation
    identifier. When that file is absent (macOS, Windows, containers
    without it), we generate a deterministic UUID5 from hostname + OS +
    architecture so the same machine produces the same ID across runs.
    """
    import platform
    import socket
    from pathlib import Path
    from uuid import NAMESPACE_DNS, uuid5

    try:
        return Path("/etc/machine-id").read_text().strip()
    except (OSError, PermissionError):
        hostname = socket.gethostname()
        os_name = platform.system()
        architecture = platform.machine()
        return str(uuid5(NAMESPACE_DNS, f"{hostname}.{os_name}.{architecture}"))
