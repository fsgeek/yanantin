"""StorageActivityMonitor — the feedback-edge + fan-out driver.

This is the node where the topology that linear ETL cannot express becomes visible:

    collector.collect(cursor)            # the source emission (a finite delta)
        ├─► fact_recorder.record_change  # ACTIVITY leg  (fan-out)
        └─► for each changed file:       # FEEDBACK edge
              collector.recollect_one    #   re-enter the collector (depth-1)
                └─► storage_recorder.update_object  # STORAGE leg → Objects

`poll()` runs ONE delta cycle and returns a PollResult. It does NOT spin a thread or
sleep — the polling loop is the caller's (and the test's) to drive, which keeps the
whole thing deterministic and lets the termination test count cycles exactly.
Webhook-vs-polling is the delivery strategy of this edge, not a topology change;
one-shot recollect is its depth. The graph shape is invariant under both.

Termination is structural: the delta set is finite (the collector's cursor
exhausts), and recollect_one emits no new delta, so the feedback edge has depth 1.
`poll_until_quiet()` loops poll() until an empty delta and is GUARANTEED to halt for
any finite-delta collector — the test asserts the cycle count is bounded.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from yanantin.collector.storage.cloud.synthetic.collector import (
    SyntheticCloudCollector,
)
from yanantin.recorder.storage.cloud.synthetic.fact_recorder import CloudFactRecorder
from yanantin.recorder.storage.cloud.synthetic.storage_recorder import (
    CloudStorageRecorder,
)


@dataclass(frozen=True)
class PollResult:
    """What one poll() cycle did. `changes_seen` is the delta size; `objects_updated`
    is the storage-leg writes (re-collected, excludes deletes); `facts_recorded` is
    the activity-leg writes; `recollects` is the feedback-edge re-enter count."""

    changes_seen: int
    objects_updated: int
    facts_recorded: int
    recollects: int
    has_more: bool


class StorageActivityMonitor:
    """Drives one cloud provider's fan-out + feedback edge."""

    def __init__(
        self,
        collector: SyntheticCloudCollector,
        storage_recorder: CloudStorageRecorder,
        fact_recorder: CloudFactRecorder,
        account_id: str = "synthetic-cloud-account",
    ) -> None:
        self._collector = collector
        self._storage = storage_recorder
        self._facts = fact_recorder
        self._account_id = account_id
        self._provider_id: UUID = collector.get_provider_id()
        self._cursor: str | None = None

    def census(self) -> int:
        """Phase 1: full listing → storage leg only (the initial Objects census).
        Establishes the cursor for subsequent delta polls. Returns objects written."""
        listing = self._collector.collect(cursor=None)
        for entry in listing.entries:
            self._storage.update_object(
                entry, source=self._provider_id, account_id=self._account_id
            )
        self._cursor = listing.cursor
        return len(listing.entries)

    def poll(self) -> PollResult:
        """Phase 2: ONE delta cycle. Fan-out (fact leg) + feedback edge (re-collect
        → storage leg) for each changed file. Deletes hit the storage leg but are
        NOT re-collected (nothing to fetch). Deterministic, no sleep."""
        if self._cursor is None:
            # No census yet — treat the first poll as establishing the cursor.
            self._cursor = self._collector.collect(cursor=None).cursor

        delta = self._collector.collect(cursor=self._cursor)
        self._cursor = delta.cursor

        objects_updated = 0
        facts_recorded = 0
        recollects = 0

        for entry in delta.entries:
            # ACTIVITY leg — every change becomes a fact (fan-out).
            self._facts.record_change(entry, provider_id=self._provider_id)
            facts_recorded += 1

            if entry.change_type == "deleted":
                # Storage leg records the delete; no re-collect (depth-0 for deletes).
                self._storage.update_object(
                    entry, source=self._provider_id, account_id=self._account_id
                )
                objects_updated += 1
                continue

            # FEEDBACK edge — re-enter the collector for the CURRENT state, depth-1.
            fresh = self._collector.recollect_one(entry.path)
            recollects += 1
            if fresh is not None:
                self._storage.update_object(
                    fresh, source=self._provider_id, account_id=self._account_id
                )
                objects_updated += 1

        return PollResult(
            changes_seen=len(delta.entries),
            objects_updated=objects_updated,
            facts_recorded=facts_recorded,
            recollects=recollects,
            has_more=delta.has_more,
        )

    def poll_until_quiet(self, max_cycles: int = 1000) -> list[PollResult]:
        """Poll until a cycle sees zero changes. GUARANTEED to halt for a
        finite-delta collector — but max_cycles is a hard backstop so a buggy
        (non-terminating) collector fails LOUDLY rather than hanging. The
        termination test asserts the real cycle count is far below this."""
        results: list[PollResult] = []
        for _ in range(max_cycles):
            result = self.poll()
            results.append(result)
            if result.changes_seen == 0:
                return results
        raise RuntimeError(
            f"poll_until_quiet did not converge in {max_cycles} cycles — the "
            "feedback edge is not terminating (a collector that never exhausts "
            "its delta). This is the bug the depth-1 design exists to prevent."
        )
