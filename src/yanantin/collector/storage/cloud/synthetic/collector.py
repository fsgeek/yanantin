"""Synthetic cloud storage collector — deterministic ground-truth twin.

Subclasses CollectorBase directly (like the real DropboxCollector), not
SyntheticCollectorBase, because the cloud interface is richer than generate()→DataT:
it has a cursor-delta protocol (collect(cursor)) and a one-shot re-collect verb
(recollect_one) — the two verbs the feedback edge needs. The "synthetic" part is
the seeded determinism, not the base class.

Ground truth is fixed by the seed: the same seed yields the same full listing, the
same finite sequence of deltas, and the same per-path current metadata. This is
what makes the topology's termination test PROVABLE rather than merely observed.

Protocol:
- collect(cursor=None) -> CloudListing : the full initial census (phase 1).
- collect(cursor=<token>) -> CloudDelta : the changes since that cursor (phase 2).
  The delta is FINITE: after the seeded changes are emitted, the cursor advances to
  a terminal token and further polls return an empty, has_more=False delta.
- recollect_one(path) -> CloudEntry | None : the current metadata for one path
  (None if it no longer exists). One-shot, bounded — emits NO new delta, which is
  what makes the feedback edge depth-1 and structurally terminating.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_DNS, UUID, uuid5

from yanantin.collector._collector_base import CollectorBase
from yanantin.collector.storage.cloud.synthetic.models import (
    CloudDelta,
    CloudEntry,
    CloudListing,
)

_INITIAL_CURSOR = "cursor:0"
_TERMINAL_CURSOR = "cursor:done"

_FILE_STEMS = (
    "report", "budget", "proposal", "notes", "summary",
    "draft", "export", "analysis", "readme", "invoice",
)
_EXTENSIONS = (".md", ".txt", ".pdf", ".docx", ".csv", ".json")


class SyntheticCloudCollector(CollectorBase[CloudListing]):
    """Deterministic synthetic cloud provider with a cursor-delta protocol.

    Args:
        seed: fixes all ground truth.
        total_entries: size of the initial census.
        change_count: how many changes the (single) delta emits before the cursor
            terminates. The feedback edge processes exactly this many re-collects.
        account_id: synthetic account identity.
    """

    def __init__(
        self,
        seed: int = 0,
        total_entries: int = 12,
        change_count: int = 3,
        account_id: str = "synthetic-cloud-account",
    ) -> None:
        self._seed = seed
        self._total_entries = total_entries
        self._change_count = change_count
        self._account_id = account_id
        self._base_time = datetime(2026, 6, 1, tzinfo=timezone.utc)
        self._provider_id = uuid5(
            NAMESPACE_DNS,
            f"yanantin.collector.cloud.synthetic.{account_id}.{seed}",
        )
        # The fixed universe of files, by path -> current CloudEntry. Built once,
        # deterministically. Deltas MUTATE this map (so recollect_one sees the new
        # state) but only along the seeded script.
        self._files: dict[str, CloudEntry] = self._build_initial_files()
        self._delta_emitted = False

    # -- ground-truth construction -------------------------------------------

    def _build_initial_files(self) -> dict[str, CloudEntry]:
        rng = random.Random(self._seed)
        files: dict[str, CloudEntry] = {}
        for i in range(self._total_entries):
            stem = rng.choice(_FILE_STEMS)
            ext = rng.choice(_EXTENSIONS)
            name = f"{stem}_{i}{ext}"
            path = f"/{name}"
            files[path] = CloudEntry(
                path=path,
                name=name,
                is_directory=False,
                size=rng.randint(1, 100_000),
                content_hash=f"{rng.getrandbits(64):016x}",
                modified=self._base_time + timedelta(hours=i),
                change_type="unchanged",
            )
        return files

    def _scripted_changes(self) -> list[CloudEntry]:
        """The deterministic set of changes the single delta emits. Modifies the
        first `change_count` files (bumping size + content_hash + modified). Uses a
        seed offset so the changes differ from the initial build but stay fixed."""
        rng = random.Random(self._seed + 1)
        paths = sorted(self._files)[: self._change_count]
        changed: list[CloudEntry] = []
        for n, path in enumerate(paths):
            old = self._files[path]
            new = CloudEntry(
                path=old.path,
                name=old.name,
                is_directory=False,
                size=old.size + rng.randint(1, 1000),
                content_hash=f"{rng.getrandbits(64):016x}",
                modified=self._base_time + timedelta(days=10, hours=n),
                change_type="modified",
            )
            changed.append(new)
        return changed

    # -- collector protocol ---------------------------------------------------

    def collect(self, cursor: str | None = None) -> CloudListing | CloudDelta:  # type: ignore[override]
        """cursor=None → full CloudListing (phase 1). cursor=<token> → CloudDelta
        (phase 2). The delta is finite: emitted once, then empty + has_more=False."""
        if cursor is None:
            return CloudListing(
                account_id=self._account_id,
                entries=tuple(self._files[p] for p in sorted(self._files)),
                cursor=_INITIAL_CURSOR,
            )
        # Delta poll.
        if cursor != _TERMINAL_CURSOR and not self._delta_emitted:
            changes = self._scripted_changes()
            # Apply the changes to ground truth so recollect_one sees new state.
            for entry in changes:
                self._files[entry.path] = entry
            self._delta_emitted = True
            return CloudDelta(
                account_id=self._account_id,
                entries=tuple(changes),
                cursor=_TERMINAL_CURSOR,
                has_more=False,
            )
        # Exhausted — no further changes.
        return CloudDelta(
            account_id=self._account_id,
            entries=(),
            cursor=_TERMINAL_CURSOR,
            has_more=False,
        )

    def recollect_one(self, path: str) -> CloudEntry | None:
        """One-shot bounded fetch of a single path's CURRENT metadata. Returns None
        if the path no longer exists. Emits no delta — depth-1 by construction."""
        entry = self._files.get(path)
        if entry is None:
            return None
        # Return as 'unchanged' — a point-in-time read, not a change event.
        return entry.model_copy(update={"change_type": "unchanged"})

    def get_provider_id(self) -> UUID:
        return self._provider_id

    def get_description(self) -> str:
        return (
            f"Synthetic cloud collector — {self._total_entries} files, "
            f"{self._change_count} scripted changes (seed={self._seed})"
        )
