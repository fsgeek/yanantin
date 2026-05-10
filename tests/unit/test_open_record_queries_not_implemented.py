from __future__ import annotations

import pytest

from yanantin.apacheta.backends.duckdb import DuckDBBackend
from yanantin.apacheta.clients.gateway import ApachetaGatewayClient


@pytest.mark.parametrize(
    "method_name, args",
    [
        ("list_open_records", ()),
        ("query_open_by_author_instance", ("s1",)),
        ("query_open_by_lineage_tag", ("cycle-5",)),
        ("query_open_has_field", ("theme",)),
        ("list_author_instances", ()),
    ],
)
def test_duckdb_open_record_queries_raise_not_implemented(method_name, args):
    with DuckDBBackend(":memory:") as backend:
        method = getattr(backend, method_name)
        with pytest.raises(NotImplementedError):
            method(*args)


@pytest.mark.parametrize(
    "method_name, args",
    [
        ("list_open_records", ()),
        ("query_open_by_author_instance", ("s1",)),
        ("query_open_by_lineage_tag", ("cycle-5",)),
        ("query_open_has_field", ("theme",)),
        ("list_author_instances", ()),
    ],
)
def test_gateway_open_record_queries_raise_not_implemented(method_name, args):
    client = ApachetaGatewayClient(base_url="http://example.invalid")
    try:
        method = getattr(client, method_name)
        with pytest.raises(NotImplementedError):
            method(*args)
    finally:
        client.close()

