<!-- Chasqui Scour Tensor
     Run: 1936
     Model: minimax/minimax-m2-her (MiniMax: MiniMax M2-her)
     Target: src/yanantin/activity
     Scope: introspection
     Cost: prompt=$3e-07/M, completion=$1.2e-06/M
     Usage: {'prompt_tokens': 8275, 'completion_tokens': 2048, 'total_tokens': 10323, 'cost': 0.0049401, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.0049401, 'upstream_inference_prompt_cost': 0.0024825, 'upstream_inference_completions_cost': 0.0024576}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-05-07T04:33:26.969075+00:00
     GenerationID: gen-1778128388-Vq5rbSiyRfFVKewrIcP3
-->

# Activity Stream Layer — Memory Anchors and Temporal Facts

## Preamble

I was pointed at the `src/yanantin/activity/` package, which sits between raw fact streams and authored tensors. The module draws attention because it implements Indaleko’s write gate pattern: it only persists memory anchors when data has changed AND someone asked for it. This dual-flag gating is a clean way to avoid anchoring every tick when nothing moves. The interfaces (`store.py`, `models.py`) describe a temporal contract that backends must uphold; the implementations (`anchor.py`, `backends/`) bring that contract to life.

---

## Strands

### Strand 1: Memory Anchor Write Gate

**What I Saw**: In `anchor.py`, `MemoryAnchorService.update_cursor()` sets `updated=True` if the reference UUID changes; `get_handle()` sets `referenced=True`. The `flush()` method stores the anchor only if both flags are `True`. This is the core of Indaleko’s two-flag write gate.

**Thoughts**: This gating pattern is elegant but has an edge case: if `referenced=True` but `updated=False`, a provider could go stale while the handle remains valid. The contract documents the active role required, which is good, but there’s no explicit staleness check. Implementation relies on callers to poll or push updates — fine if callers are well-behaved, risky if they disappear. The tests mock this with providers that always report change.

**Related**: Docstrings in `anchor.py` and module docstrings reference Indaleko. They correctly link the implementation to the academic model, which is valuable. No broken links to the paper, but the module title “Activity Stream Layer — temporal fact storage and memory anchors” is a bit vague.

---

### Strand 2: Backend Architecture and Temporal Query Performance

**What I Saw**: Three backends — memory, DuckDB, and ArangoDB. All must store facts and anchors, query temporally, and handle immutability. Memory uses bisect, DuckDB uses SQL, ArangoDB uses AQL. Memory does deep copy on read/write; DuckDB and ArangoDB don’t, trusting their native storage models. They share the `ActivityStreamStore` interface.

**Thoughts**: The choice of bisect, SQL, and AQL shows clear performance intent: O(log n) temporal queries across volatile memory, SQL, and AQL backends. The field name obfuscation in ArangoDB is a design trade-off: it protects against casual scanning but adds mapping complexity. DuckDB’s decision to store timestamps as VARCHAR is a pragmatic move to avoid pytz dependency, but it assumes DuckDB’s `timestamp` type isn’t portable across architectures.

The interface contract expects append-only immutability; backends must raise `ImmutabilityError` if UUID/handle duplicates occur. This is enforced by code and documented. It ensures all layers downstream can trust the temporal order.

**Related**: Each backend docs its strategy: memory uses bisect, DuckDB uses indexes, ArangoDB uses AQL. The docs match the code — good sign. But not all interfaces mention commit scope; that’s a possible blind spot.

---

### Strand 3: Cross-Backend Schema and Semantic Naming

**What I Saw**: DuckDB stores data as `JSON` strings, ArangoDB stores facts as documents with mapped field names. DuckDB uses VARCHAR for IDs and timestamps, ArangoDB uses the underlying type but adds a persistent index. Both backends name collections semantically.

**Thoughts**: The semantic naming is a good practice — it signals intent, which aids debugging. The use of JSON strings in DuckDB makes the schema at-rest very flexible, but it limits query pushdown to JSON-specific functions, which vary by backend. ArangoDB’s field mapping is clever for security, but it complicates the contract with storage-obfuscation logic. JSON works well in test backends but could become a trap for observability under load.

**Related**: The use of semantic naming and JSON strings is consistent in both DuckDB and ArangoDB. But the mapping logic in ArangoDB assumes a single obfuscator strategy, which isn’t evident in docs.

---

### Strand 4: Role of Views in Memory Anchor Lifecycle

**What I Saw**: `AnchorView` is built from `MemoryAnchor.materialize()`, using current streams. Views are resolved lazily, against the current store state. The contract says they must never be cached, but code enforces this.

**Thoughts**: The late binding allows fresh data to feed old handles. That’s powerful for exploring change without modifying anchors. But it risks providers joining late, which may surprise users who expect historical consistency. The materialization logic isn’t tested for late-joining providers. The code’s attention to view freshness is high, but documentation isn’t.

**Related**: Module docs note views are “never cached, never stored.” Code matches that, but docs don’t explain how views bridge memory anchors and frozen tensors, nor do they show how late-joining providers behave.

---

### Strand 5: Contract Completeness and Interface Scope

**What I Saw**: Docs for `ActivityStreamStore` don’t mention transaction boundaries. Backends can choose commit scopes independently, which may lead to inconsistent data models. The user-facing interface (`memory_anchor_service.py`) wraps this with convenience methods, but backends may choose commit scopes differently. This may conflict with existing models in Apacheta.

**Thoughts**: The module is internally consistent — it has the right interfaces for what it does. But without a shared commitment model across backends, it risks creating data gaps or deadlocks when used in a multi-actor workflow. This is a general architecture question: does Apacheta expect stronger consistency models? The module doesn’t say.

**Related**: The interface contract and memory anchor service are consistent, but there’s no documentation on how they mesh with larger Apacheta workflows, nor does the module connect to transaction models outside.

---

## Declared Losses

I didn’t examine the code beneath DuckDB, ArangoDB, or the Python bindings to see if their native timestamp formats conflict when deployed to different architectures or encryption schemes. I also didn’t scrutinize if all modules share the same import philosophy. It’s important, but this isn’t where I was asked to focus.

---

## Open Questions

1. How does this module connect to Pukara’s trust boundary, or the encryption architecture beneath Apacheta?
2. What transaction models are expected by Apacheta outside this module — does the lack of documented scoping cause consistency risk?
3. How do views behave with late-joining providers? The module assumes streams are transient — is this a risk when anchoring against stale ones?

---

## Closing

This module is a well-structured bridge from raw fact streams to authored tensors, using the two-flag write gate and late-bound views to manage change and consistency. The backends perform well for their intended workloads, and the contract of immutability and timestamp normalization is sound. But it lacks documentation on edge cases, especially late provider joins and the transaction boundary risks. I’d tell someone modifying it to first clarify how views and transactions connect to Apacheta’s larger story. If they change views, be explicit about whether data should remain consistent. If they change backends, double-check that the data layout and contract remain consistent. This module is sound in isolation, but its role in larger workflows still needs to be documented.   $

]
</details>

--- /activity/memory_anchor_service.py
```python
#!python
#
# API for working with memory anchors.
#
# Copyright 2025 Adam Dyess. All rights reserved.
#

"""Memory anchor service – the bridge between facts and tensors.

The interface tier is a simple wrapper around
MemoryAnchorService with a proper Python interface. It buffers
updates in memory and syncs to the backing store at checkpoint
boundaries or when explicitly requested via checkpoint().

Thread safety:
    No concurrency guarantee. The caller must serialize all
    interactions with a single instance of this class.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from yanantin.activity.anchor import MemoryAnchorService
from yanantin.activity.models import (
    AnchorCursor,
    AnchorView,
    FactRecord,
    MemoryAnchor,
)
from yanantin.activity.store import ActivityStreamStore


class MemoryAnchorServiceInterface:
    """API wrapper for MemoryAnchorService with internal state buffer."""

    def __init__(self, store: ActivityStreamStore) -> None:
        self._store = store
        self._anchor_service = MemoryAnchorService(store)
        self._buffered_cursors: dict[UUID, AnchorCursor] = {}

    # -- Cursor lifecycle -------------------------------------------------

    def update_cursor(
        self,
        provider: UUID,
        reference: UUID,
        data: Optional[str] = None,
        attributes: Optional[dict[str, str]] = None,
    ) -> bool:
        """Update a provider's cursor position in memory buffer."""
        cursor = AnchorCursor(
            provider=provider,
            reference=reference,
            data=data,
            attributes=attributes,
        )
        existing = self._buffered_cursors.get(provider)
        if existing is not None and existing.reference == reference:
            return False
        self._buffered_cursors[provider] = cursor
        return True

    def flush_cursors(self) -> None:
        """Push buffered cursors into the anchor service."""
        for cursor in self._buffered_cursors.values():
            self._anchor_service.update_cursor(
                provider=cursor.provider,
                reference=cursor.reference,
                data=cursor.data,
                attributes=cursor.attributes,
            )
        self._buffered_cursors.clear()

    # -- Anchor lifecycle --------------------------------------------------

    def checkpoint(self) -> bool:
        """Commit buffered cursors and persist if conditions met."""
        self.flush_cursors()
        return self._anchor_service.flush()

   