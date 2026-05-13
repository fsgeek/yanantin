"""Fetch and fingerprint the OpenRouter model catalog.

The catalog (`GET /models`) is the source of truth for which models
exist, their pricing, and their context limits. A pre-registration
records both the resolved panel and a sha256 fingerprint of the exact
catalog body it was resolved against, so "were these models current?"
has a verifiable answer.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import httpx

CATALOG_URL = "https://openrouter.ai/api/v1/models"


def catalog_snapshot_sha(catalog: list[dict[str, Any]]) -> str:
    """Hex sha256 of the catalog's canonical JSON. Order-sensitive."""
    blob = json.dumps(catalog, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


async def fetch_openrouter_catalog(api_key: str | None = None) -> list[dict[str, Any]]:
    """Return the `data` list from OpenRouter's `/models` endpoint.

    Raises ValueError if no API key is available; httpx errors propagate.
    """
    key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY not set; pass api_key= or export it")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(CATALOG_URL, headers={"Authorization": f"Bearer {key}"})
        resp.raise_for_status()
        body = resp.json()
    data = body.get("data")
    if not isinstance(data, list):
        raise ValueError(f"unexpected /models response shape: {type(data)}")
    return data
