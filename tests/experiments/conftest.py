from __future__ import annotations

import os
import socket
from functools import cache

import pytest


@cache
def _openrouter_reachability_error() -> str | None:
    try:
        with socket.create_connection(("openrouter.ai", 443), timeout=2.0):
            return None
    except OSError as exc:
        return str(exc)


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("integration") is None:
        return

    if "OPENROUTER_API_KEY" not in os.environ:
        pytest.skip("no OPENROUTER_API_KEY")

    if error := _openrouter_reachability_error():
        pytest.skip(f"OpenRouter network unavailable: {error}")
