"""Red-bar test: Immutability invariant.

A tensor, once written, is never modified. Attempting to store a tensor
with the same UUID must raise ImmutabilityError.
"""

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.interface.errors import ImmutabilityError
from yanantin.apacheta.models import (
    CompositionEdge,
    RelationType,
    TensorRecord,
)


def test_duplicate_tensor_raises():
    backend = InMemoryBackend()
    tensor = TensorRecord(preamble="First version")
    backend.store_tensor(tensor)

    # Same UUID = ImmutabilityError. Compose, don't overwrite.
    duplicate = TensorRecord(
        id=tensor.id,
        preamble="Attempted overwrite",
    )
    with pytest.raises(ImmutabilityError):
        backend.store_tensor(duplicate)


def test_duplicate_edge_raises():
    backend = InMemoryBackend()
    edge = CompositionEdge(
        from_tensor=TensorRecord().id,
        to_tensor=TensorRecord().id,
        relation_type=RelationType.COMPOSES_WITH,
    )
    backend.store_composition_edge(edge)
    with pytest.raises(ImmutabilityError):
        backend.store_composition_edge(edge)


def test_no_delete_method():
    """The interface has no delete method. This is by design."""
    backend = InMemoryBackend()
    assert not hasattr(backend, "delete_tensor")
    assert not hasattr(backend, "delete")
    assert not hasattr(backend, "remove")
    assert not hasattr(backend, "drop")


def test_no_update_method():
    """The interface has no update method. Tensors are immutable."""
    backend = InMemoryBackend()
    assert not hasattr(backend, "update_tensor")
    assert not hasattr(backend, "modify")
    assert not hasattr(backend, "patch")
