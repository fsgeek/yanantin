"""Where an incremental walk starts: the latest completed walk under the same policy.

Each landing writes a fact recording what its walk covered (land_full_corpus.py:
root, all_names, incremental, cutoff, started), and only after the landing
succeeds, so a failed landing never sets a cutoff. Walks that skipped names
(.git, .venv, ...) don't count: changes under those names after such a walk
would be missed. No qualifying walk means a full walk.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime


def latest_walk_start(fact_data: Iterable[dict]) -> datetime | None:
    """The latest `started` among all-names walks in these landing facts' data."""
    starts = [
        datetime.fromisoformat(walk["started"])
        for data in fact_data
        if isinstance(walk := data.get("walk"), dict) and walk.get("all_names") and walk.get("started")
    ]
    return max(starts, default=None)
