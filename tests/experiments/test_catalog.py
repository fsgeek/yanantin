import asyncio
import json
import os
from pathlib import Path

import pytest

from yanantin.experiments.catalog import catalog_snapshot_sha, fetch_openrouter_catalog


def _load_fixture_data() -> list[dict]:
    fixture_path = Path(__file__).parent / "fixtures" / "openrouter_models_sample.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return payload["data"]


def test_snapshot_sha_stable() -> None:
    data = _load_fixture_data()
    digest = catalog_snapshot_sha(data)

    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)
    assert catalog_snapshot_sha(data) == catalog_snapshot_sha(data)
    assert digest != catalog_snapshot_sha(list(reversed(data)))


def test_snapshot_sha_known_value() -> None:
    data = _load_fixture_data()
    assert (
        catalog_snapshot_sha(data)
        == "ce40c801729cb62641d42ca26f0fa5f4f273c8f7b64b6ac54d064f5a5f5ae263"
    )


@pytest.mark.integration
def test_fetch_catalog_live() -> None:
    if "OPENROUTER_API_KEY" not in os.environ:
        pytest.skip("no OPENROUTER_API_KEY")

    async def _check() -> None:
        result = await fetch_openrouter_catalog()
        assert isinstance(result, list)
        assert len(result) > 0
        assert all("id" in m for m in result)

    asyncio.run(_check())
