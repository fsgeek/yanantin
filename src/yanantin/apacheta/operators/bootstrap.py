"""Bootstrap operator — selects tensors/strands for a new instance's budget."""

from __future__ import annotations

from uuid import UUID

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.models.composition import BootstrapRecord
from yanantin.apacheta.models.provenance import ProvenanceEnvelope
from yanantin.apacheta.models.tensor import TensorRecord


def bootstrap(
    interface: ApachetaInterface,
    instance_id: str,
    context_budget: float,
    *,
    task: str = "",
    tensor_ids: list[UUID] | None = None,
    strand_indices: list[int] | None = None,
    what_was_omitted: str = "",
    provenance: ProvenanceEnvelope | None = None,
) -> tuple[BootstrapRecord, list[TensorRecord]]:
    """Select tensors for a new instance's context budget.

    Always persisted. Storage cost ≈ 0. Provenance value > 0.

    Returns the bootstrap record and the selected tensors.
    """
    if tensor_ids is None:
        # Simple: select all available tensors
        selected = interface.list_tensors()
        tensor_ids = [t.id for t in selected]
    else:
        selected = [interface.get_tensor(tid) for tid in tensor_ids]

    record = BootstrapRecord(
        instance_id=instance_id,
        context_budget=context_budget,
        task=task,
        tensors_selected=tensor_ids,
        strands_selected=strand_indices or [],
        what_was_omitted=what_was_omitted,
        provenance=provenance or ProvenanceEnvelope(),
    )
    interface.store_bootstrap(record)

    return record, selected
