"""Red-bar test: Monotonicity invariant.

Operations only add records, never decrease record count.
The database is append-only. No operation reduces the total.
"""

import threading

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.models import (
    CompositionEdge,
    CorrectionRecord,
    RelationType,
    TensorRecord,
)
from uuid import uuid4


def test_record_count_never_decreases():
    backend = InMemoryBackend()

    counts_before = backend.count_records()
    total_before = sum(counts_before.values())
    assert total_before == 0

    # Store tensor
    backend.store_tensor(TensorRecord())
    counts_after_1 = backend.count_records()
    total_after_1 = sum(counts_after_1.values())
    assert total_after_1 > total_before

    # Store edge
    backend.store_composition_edge(CompositionEdge(
        from_tensor=uuid4(),
        to_tensor=uuid4(),
        relation_type=RelationType.COMPOSES_WITH,
    ))
    counts_after_2 = backend.count_records()
    total_after_2 = sum(counts_after_2.values())
    assert total_after_2 > total_after_1

    # Store correction
    backend.store_correction(CorrectionRecord(
        target_tensor=uuid4(),
        original_claim="old",
        corrected_claim="new",
    ))
    counts_after_3 = backend.count_records()
    total_after_3 = sum(counts_after_3.values())
    assert total_after_3 > total_after_2


def test_concurrent_writes_dont_lose_records():
    """Multiple threads writing concurrently should not lose any records."""
    backend = InMemoryBackend()
    n_threads = 10
    n_tensors_per_thread = 20
    barrier = threading.Barrier(n_threads)

    def writer():
        barrier.wait()
        for _ in range(n_tensors_per_thread):
            backend.store_tensor(TensorRecord())

    threads = [threading.Thread(target=writer) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = n_threads * n_tensors_per_thread
    actual = backend.count_records()["tensors"]
    assert actual == expected, f"Expected {expected} tensors, got {actual}"
