"""Red-bar test: Immutability invariant on the PERSISTENT backend.

"A tensor, once written, is never modified" is a substrate promise. Its
sibling test_immutability.py proves it against InMemoryBackend — a per-process
store that dies before a successive ghola can overwrite a predecessor's record.
But the overwrite-across-inheritance threat runs on the DURABLE backend, where
this invariant actually protects integrity. This bar proves it there.

Same seam as Guard 3, running the other direction: the property holds on
ArangoDBBackend (arango._store: collection.has(key) -> ImmutabilityError; the
backend exposes no delete/update method) but was unguarded there. A future edit
adding an overwrite=True insert path, or a delete_tensor method, would sail past
a green suite. This bar rings when it shouldn't.

Live DB, config-file creds (env path silently skips in a worktree).
"""

from __future__ import annotations

import pytest

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.interface.errors import ImmutabilityError
from yanantin.apacheta.models import TensorRecord
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
    db._db.collection(db._map.collection_name("tensors")).truncate()
    yield db
    db._db.collection(db._map.collection_name("tensors")).truncate()
    db.close()


def test_duplicate_tensor_raises_on_persistent_backend(backend):
    """Same UUID -> ImmutabilityError, on the backend where a successive ghola
    could actually attempt the overwrite. A store path that silently overwrote
    (the inheritance-integrity breach this invariant exists to stop) would not
    raise here and the bar goes red."""
    tensor = TensorRecord(preamble="First version")
    backend.store_tensor(tensor)

    duplicate = TensorRecord(id=tensor.id, preamble="Attempted overwrite")
    with pytest.raises(ImmutabilityError):
        backend.store_tensor(duplicate)


def test_persistent_backend_exposes_no_mutation_surface():
    """The durable backend has no delete/update method. test_immutability.py
    asserts this for the memory CLASS; that says nothing about this different
    class talking to a DB whose AQL layer *can* delete. Assert it here too."""
    for name in (
        "delete_tensor",
        "delete",
        "remove",
        "drop",
        "update_tensor",
        "modify",
        "patch",
    ):
        assert not hasattr(ArangoDBBackend, name), (
            f"ArangoDBBackend exposes {name!r} — the immutability invariant "
            "('compose, don't overwrite') is breached on the persistent substrate"
        )
