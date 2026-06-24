"""The contribution-mapping vocabulary: how a recorder declares WHERE its
output lands (ContributionTarget). The thin ContributedRecord scaffold has
been RETIRED — the storage recorder now constructs the uniform StorageObject
(#17, Pour B; succession, not duplication). Field names are deliberately
minimal; the spec does not freeze them
(2026-06-17-recorder-collection-mapping-design.md)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class ContributionTarget(BaseModel):
    """One entry in a recorder's `contributes_to` declaration: a collection
    its output lands in. `kind` doc vs edge; `naming` well_known (attach to a
    shared owned collection) vs dynamic (mint own). The registrar stores this
    OPAQUELY in its open tail; only the recorder acts on it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    kind: Literal["doc", "edge"]
    naming: Literal["well_known", "dynamic"]
