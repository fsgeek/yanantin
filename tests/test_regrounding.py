from __future__ import annotations

from uuid import uuid4

import pytest

from yanantin.infra.config import ApachetaDBConfig, get_database
from yanantin.memory.regrounding import (
    Regrounding,
    UnsupportedClaimKind,
    reground,
)


pytestmark = pytest.mark.integration


@pytest.fixture
def live_db():
    """A real StandardDatabase handle on apacheta_test (test-tier creds)."""
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )


def test_reground_collection_count_reports_stored_and_live_values(live_db):
    collection_name = f"test_regrounding_{uuid4().hex}"

    try:
        collection = live_db.create_collection(collection_name)
        for index in range(3):
            collection.insert({"_key": f"doc{index}", "index": index})

        claim = {
            "kind": "collection_count",
            "db": "apacheta_test",
            "collection": collection_name,
            "value": 1,
            "as_of": "2026-06-28",
        }

        result = reground(claim)

        assert isinstance(result, Regrounding)
        assert result.live == 3
        assert result.stored == 1
        assert result.stale is True

        rendered = result.render() if hasattr(result, "render") else str(result)
        assert "3" in rendered
        assert "1" in rendered
    finally:
        if live_db.has_collection(collection_name):
            live_db.delete_collection(collection_name)


def test_reground_unsupported_kind_raises():
    claim = {
        "kind": "something_else",
        "db": "apacheta_test",
        "collection": "unused",
        "value": 1,
        "as_of": "2026-06-28",
    }

    with pytest.raises(UnsupportedClaimKind):
        reground(claim)
