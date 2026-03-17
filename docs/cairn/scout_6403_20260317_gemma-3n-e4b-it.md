<!-- Chasqui Scout Tensor
     Run: 6403
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 750, 'completion_tokens': 444, 'total_tokens': 1194, 'cost': 3.276e-05, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 3.276e-05, 'upstream_inference_prompt_cost': 1.5e-05, 'upstream_inference_completions_cost': 1.776e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-17T02:41:37.322510+00:00
     Dispatch: verify
     Claim: The next scout should:   - **Read `provenance.py` and `tensor.py` first** — they are the core.
     ClaimFile: src/yanantin/apacheta/models/provenance.py
     ClaimBy: qwen/qwen3-235b-a22b-2507
     SourceTensor: /home/tony/projects/yanantin/docs/cairn/scout_0528_20260214_qwen3-235b-a22b-2507.md
-->

### Verdict
CONFIRMED

### Evidence
```
"""Provenance models — who made this, when, from what context."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pydantic import Field
from yanantin.apacheta.models.base import ApachetaBaseModel


class SourceIdentifier(ApachetaBaseModel):
    """Identifies the source of a record."""

    identifier: UUID = Field(default_factory=uuid4)
    version: str = "v1"
    description: str = ""


class ProvenanceEnvelope(ApachetaBaseModel):
    """Wraps every record with provenance metadata.

    Every artifact answers: who made this, when, from what context.
    """

    source: SourceIdentifier = Field(default_factory=SourceIdentifier)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    author_model_family: str = ""
    author_instance_id: str = ""
    context_budget_at_write: float | None = None
    predecessors_in_scope: tuple[UUID, ...] = Field(default_factory=tuple)
    interface_version: str = "v1"
```
### Reasoning
The claim states "Read `provenance.py` and `tensor.py` first — they are the core." The file provided is `provenance.py`. The file's docstring begins with "Provenance models — who made this, when, from what context." This indicates that `provenance.py` defines models related to provenance, which aligns with the claim that it is a core file. While `tensor.py` is not provided, the claim only asks to verify the statement about `provenance.py`. Therefore, based on the content of the provided file, the claim about reading `provenance.py` first is confirmed.

### Declared Losses
I cannot check the claim about `tensor.py` as the content of that file was not provided.