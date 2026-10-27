"""Which time an incremental walk starts from: the latest completed walk's start.

A landing writes its fact only after it succeeds, so a failed landing never sets
a cutoff. Only walks under the same policy (all names) count: a default-policy
walk skipped .git/.venv/..., so changes there after it would be missed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from yanantin.recorder.storage.local.linux.walks import latest_walk_start


def fact(walk=None, jsonl=None):
    data = {}
    if walk is not None:
        data["walk"] = walk
    if jsonl is not None:
        data["jsonl"] = jsonl
    return data


def test_latest_all_names_walk_wins():
    facts = [
        fact({"all_names": True, "started": "2026-10-26T17:32:49+00:00"}),
        fact({"all_names": True, "started": "2026-10-27T03:00:00+00:00"}),
        fact({"all_names": False, "started": "2026-10-27T09:00:00+00:00"}),
    ]
    assert latest_walk_start(facts) == datetime(2026, 10, 27, 3, 0, tzinfo=timezone.utc)


def test_no_qualifying_walk_means_full_walk():
    assert latest_walk_start([fact({"all_names": False, "started": "2026-10-27T09:00:00+00:00"})]) is None
    assert latest_walk_start([]) is None


def test_facts_without_a_walk_record_do_not_count():
    """Landings before 2026-10-27 recorded no policy; their cutoff cannot be trusted."""
    assert latest_walk_start([fact(jsonl="/x/walk-20261026T173252Z.jsonl.gz")]) is None


def test_incremental_walks_count_too():
    facts = [
        fact({"all_names": True, "incremental": False, "started": "2026-10-26T17:32:49+00:00"}),
        fact({"all_names": True, "incremental": True, "started": "2026-10-28T03:00:00+00:00"}),
    ]
    assert latest_walk_start(facts) == datetime(2026, 10, 28, 3, 0, tzinfo=timezone.utc)
