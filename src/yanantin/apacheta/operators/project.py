"""Project operator — filters strands from a tensor."""

from __future__ import annotations

from uuid import UUID

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.models.tensor import StrandRecord


def project(
    interface: ApachetaInterface,
    tensor_id: UUID,
    *,
    strand_indices: list[int] | None = None,
    topics: list[str] | None = None,
) -> list[StrandRecord]:
    """Return filtered strands from a tensor.

    Filter by strand_indices, topics, or both. If both are provided,
    strands matching either criterion are included.
    """
    tensor = interface.get_tensor(tensor_id)
    if strand_indices is None and topics is None:
        return list(tensor.strands)

    results = []
    for strand in tensor.strands:
        if strand_indices and strand.strand_index in strand_indices:
            results.append(strand)
        elif topics and any(t in strand.topics for t in topics):
            if strand not in results:
                results.append(strand)
    return results
