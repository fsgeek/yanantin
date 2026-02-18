"""Memory anchor service — the bridge between facts and tensors.

Issues handles, tracks cursors, manages the two-flag write gate
(updated AND referenced). Implements Indaleko's ActivityContextService
pattern: write only when something changed AND someone asked for it.

The service owns the lifecycle:
- update_cursor() — provider reports new data (sets updated)
- get_handle() — caller requests current position (sets referenced)
- flush() — write gate check, persist if both flags set
- materialize() — resolve an anchor against current streams (always fresh)
- freeze() — pin a temporal view into a permanent tensor (authored act)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from yanantin.activity.models import AnchorCursor, AnchorView, FactRecord, MemoryAnchor
from yanantin.activity.store import ActivityStreamStore
from yanantin.apacheta.interface import ApachetaInterface
from yanantin.apacheta.models import (
    ProvenanceEnvelope,
    SourceIdentifier,
    StrandRecord,
    TensorRecord,
)


class MemoryAnchorService:
    """Issues handles, tracks cursors, manages the write gate.

    The service is the bridge between the fact store and the tensor store.
    It implements Indaleko's two-flag write gate: updated AND referenced.
    """

    def __init__(self, store: ActivityStreamStore) -> None:
        self._store = store
        self._handle: UUID = uuid4()
        self._timestamp: datetime = datetime.now(timezone.utc)
        self._cursors: dict[UUID, AnchorCursor] = {}
        self._updated: bool = False
        self._referenced: bool = False

    @property
    def store(self) -> ActivityStreamStore:
        """The underlying activity stream store."""
        return self._store

    def update_cursor(
        self,
        provider: UUID,
        reference: UUID,
        data: str | None = None,
        attributes: dict[str, str] | None = None,
    ) -> bool:
        """Update a provider's cursor position.

        If the provider exists and reference is unchanged, returns False
        (no-op). Otherwise updates/adds the cursor and sets updated=True.
        """
        existing = self._cursors.get(provider)
        if existing is not None and existing.reference == reference:
            return False

        self._cursors[provider] = AnchorCursor(
            provider=provider,
            reference=reference,
            data=data,
            attributes=attributes,
        )
        self._updated = True
        return True

    def get_handle(self) -> UUID:
        """Get the current anchor handle, setting referenced=True."""
        self._referenced = True
        return self._handle

    def flush(self) -> bool:
        """Persist anchor if both flags are set (updated AND referenced).

        If the write gate is closed, returns False without writing.
        If both flags are set: builds MemoryAnchor, stores it, advances
        handle and timestamp, resets flags. Returns True.
        """
        if not (self._updated and self._referenced):
            return False

        anchor = MemoryAnchor(
            handle=self._handle,
            timestamp=self._timestamp,
            cursors=tuple(self._cursors.values()),
        )
        self._store.store_anchor(anchor)

        # Advance: new handle, new timestamp, reset flags
        self._handle = uuid4()
        self._timestamp = datetime.now(timezone.utc)
        self._updated = False
        self._referenced = False

        return True

    def materialize(self, handle: UUID) -> AnchorView:
        """Resolve an anchor against current streams.

        Always fresh — queries list_providers() at resolution time
        (late binding), not just the providers in the anchor's cursor
        list. A new provider registered after the anchor was created
        will appear in the view if it has facts before the anchor's
        timestamp.
        """
        anchor = self._store.get_anchor(handle)

        # Late binding: discover ALL current providers
        all_providers = self._store.list_providers()

        # For each provider, find the latest fact at or before anchor time
        facts: dict[UUID, FactRecord] = {}
        for provider_id in all_providers:
            fact = self._store.query_latest(provider_id, before=anchor.timestamp)
            if fact is not None:
                facts[provider_id] = fact

        return AnchorView(
            handle=anchor.handle,
            timestamp=anchor.timestamp,
            facts=facts,
            providers=tuple(all_providers),
            anchor=anchor,
        )

    def freeze(self, handle: UUID, interface: ApachetaInterface) -> UUID:
        """Pin a temporal view into a permanent tensor.

        This is an authored act — it decides to freeze a temporal view.
        The resulting tensor has provenance and structured content.
        """
        view = self.materialize(handle)

        # Strand 0: Anchor summary
        summary_lines = [
            f"handle: {view.handle}",
            f"timestamp: {view.timestamp.isoformat()}",
            f"provider_count: {len(view.providers)}",
            f"fact_count: {len(view.facts)}",
        ]
        summary_strand = StrandRecord(
            strand_index=0,
            title="Anchor Summary",
            content="\n".join(summary_lines),
            topics=("anchor", "summary"),
        )

        # Strand 1: Anchor data — cursor state + resolved facts
        anchor_data = {
            "cursors": [c.model_dump(mode="json") for c in view.anchor.cursors],
            "resolved_facts": {
                str(pid): f.model_dump(mode="json")
                for pid, f in view.facts.items()
            },
        }
        data_strand = StrandRecord(
            strand_index=1,
            title="Anchor Data",
            content=json.dumps(anchor_data, sort_keys=True, separators=(",", ":")),
            topics=("anchor", "data", "facts"),
        )

        tensor = TensorRecord(
            provenance=ProvenanceEnvelope(
                source=SourceIdentifier(
                    identifier=view.handle,
                    description="Memory anchor freeze",
                ),
                author_model_family="anchor-service",
            ),
            preamble=(
                f"Frozen anchor {view.handle} at {view.timestamp.isoformat()} "
                f"({len(view.providers)} providers, {len(view.facts)} facts)"
            ),
            strands=(summary_strand, data_strand),
            lineage_tags=("anchor", "frozen-view"),
        )

        interface.store_tensor(tensor)
        return tensor.id
