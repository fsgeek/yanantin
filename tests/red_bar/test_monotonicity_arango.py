"""Red-bar test: Monotonicity invariant on the PERSISTENT backend.

"The database is append-only. No operation reduces the total." Its sibling
test_monotonicity.py proves this against InMemoryBackend, where concurrency is
an in-process lock. But lost-write bugs live in the DURABLE store under real
concurrency — that is where append-only is hard and where it matters for
integrity across successive gholas. Probe (scratchpad) confirmed the property
holds on arango: 10 threads x 20 writes = 200, none lost. This guards it there.

Same seam as Guard 3 and the immutability bar: property holds on
ArangoDBBackend, was unguarded there.

Live DB, config-file creds (env path silently skips in a worktree).
"""

from __future__ import annotations

import threading
from uuid import uuid4

import pytest

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.models import (
    CompositionEdge,
    RelationType,
    TensorRecord,
)
from yanantin.infra.config import ApachetaDBConfig

pytestmark = pytest.mark.integration

_DB = "apacheta_test"


def _conn():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return cfg.host_url, creds["username"], creds["password"]


def _available() -> bool:
    try:
        host, user, pwd = _conn()
        ArangoDBBackend(host=host, db_name=_DB, username=user, password=pwd)._db.collections()
        return True
    except Exception:
        return False


@pytest.fixture
def backend():
    if not _available():
        pytest.skip("ArangoDB test database not available")
    host, user, pwd = _conn()
    db = ArangoDBBackend(host=host, db_name=_DB, username=user, password=pwd)
    for tbl in ("tensors", "composition_edges"):
        db._db.collection(db._map.collection_name(tbl)).truncate()
    yield db
    for tbl in ("tensors", "composition_edges"):
        db._db.collection(db._map.collection_name(tbl)).truncate()
    db.close()


def test_record_count_never_decreases_on_persistent_backend(backend):
    """Each store increases the total; nothing reduces it."""
    total_before = sum(backend.count_records().values())
    assert total_before == 0

    backend.store_tensor(TensorRecord())
    total_1 = sum(backend.count_records().values())
    assert total_1 > total_before

    backend.store_composition_edge(
        CompositionEdge(
            from_tensor=uuid4(),
            to_tensor=uuid4(),
            relation_type=RelationType.COMPOSES_WITH,
        )
    )
    total_2 = sum(backend.count_records().values())
    assert total_2 > total_1


def test_concurrent_writes_dont_lose_records_on_persistent_backend(backend):
    """Concurrent durable writes lose nothing. This is the property's hard case:
    on the persistent store under real threads, not an in-process lock. A store
    path that dropped or clobbered under contention goes red here."""
    n_threads, per = 10, 20
    barrier = threading.Barrier(n_threads)

    def writer():
        barrier.wait()
        for _ in range(per):
            backend.store_tensor(TensorRecord())

    threads = [threading.Thread(target=writer) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = n_threads * per
    actual = backend.count_records()["tensors"]
    assert actual == expected, f"Expected {expected} tensors, got {actual}"
