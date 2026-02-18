"""Activity stream layer — temporal fact storage and memory anchors.

Two stores, two concerns:
- **ActivityStreamStore** — temporal fact storage. High volume, append-only,
  indexed by (provider_id, timestamp). Schema-agnostic.
- **ApachetaInterface** — authored tensor storage. Low volume, immutable,
  queryable by epistemic metadata. Existing, unchanged.

The **MemoryAnchorService** bridges them: it tracks which providers have
new data (cursors), issues handles to callers, and only persists when
the write gate opens (updated AND referenced).
"""

from yanantin.activity.anchor import MemoryAnchorService
from yanantin.activity.models import (
    AnchorCursor,
    AnchorView,
    FactRecord,
    MemoryAnchor,
)
from yanantin.activity.store import ActivityStreamStore

__all__ = [
    "ActivityStreamStore",
    "AnchorCursor",
    "AnchorView",
    "FactRecord",
    "MemoryAnchor",
    "MemoryAnchorService",
]
