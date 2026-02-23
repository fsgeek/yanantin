"""Root conftest: loads .env into os.environ at test startup.

Uses stdlib only. Environment variables already set take precedence
(setdefault, not overwrite). This replaces hardcoded credentials
in integration test files.
"""

from __future__ import annotations

import os
from pathlib import Path


def pytest_configure(config) -> None:
    """Load .env file if it exists."""
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        return

    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
