"""The find tool's MCP responses: compact, summary first, coverage always.

Tool output is context an instance pays for (Tony: "anything we can do that
reduces tool output is a win"), so the response drops what carries nothing
(the file:// prefix, sub-minute walk times) and keeps what keeps "no matches"
honest (coverage, and what is not indexed at all).
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from yanantin.find import FindResult
from yanantin.find.render import NOT_INDEXED, describe_store, parse_when, render

UTC = timezone.utc


def _result(**overrides):
    base = dict(
        total_matched=3, by_machine={"wam-desktop": 3},
        top_directories=[("file:///home/tony/projects/x", 3)],
        coverage=[{"machine": "wam-desktop", "last_walk": datetime(2026, 11, 9, 11, 37, 12, 5, tzinfo=UTC)},
                  {"machine": "9cb28995", "last_walk": None}],
        hits=[{"uri": "file:///home/tony/projects/x/a.jsonl", "machine": "wam-desktop",
               "modified": "2025-11-25T12:06:38.164824Z", "size": 4459458}],
        fact_id=uuid4(), duplicate_of=None,
    )
    return FindResult(**{**base, **overrides})


def test_summary_comes_before_hits_and_paths_lose_the_scheme():
    out = render(_result())
    assert list(out)[:4] == ["total_matched", "by_machine", "top_directories", "coverage"]
    assert out["top_directories"] == [["/home/tony/projects/x", 3]]
    assert out["hits"] == [["wam-desktop", "2025-11-25T12:06Z", 4459458, "/home/tony/projects/x/a.jsonl"]]


def test_coverage_is_minute_precision_and_names_what_is_not_indexed():
    out = render(_result())
    assert out["coverage"] == {"wam-desktop": "2026-11-09T11:37Z", "9cb28995": "never walked"}
    assert out["not_indexed"] == NOT_INDEXED


def test_zero_results_keep_coverage_and_say_what_to_try():
    out = render(_result(total_matched=0, by_machine={}, top_directories=[], hits=[]))
    assert out["coverage"] and out["not_indexed"] == NOT_INDEXED
    assert "hint" in out and "modified" in out["hint"]


def test_a_repeat_says_so():
    first = uuid4()
    assert render(_result(duplicate_of=first))["repeat_of"] == str(first)
    assert "repeat_of" not in render(_result())


def test_parse_when_accepts_dates_and_requires_a_zone_only_when_given_a_time():
    assert parse_when("2025-11-24") == datetime(2025, 11, 24, tzinfo=UTC)
    assert parse_when("2025-11-24T10:00:00+00:00") == datetime(2025, 11, 24, 10, tzinfo=UTC)
    assert parse_when(None) is None
    with pytest.raises(ValueError, match="time zone"):
        parse_when("2025-11-24T10:00:00")


def test_describe_store_names_the_scale_the_machines_and_when_to_reach_for_it():
    text = describe_store(19_136_843, {"wam-desktop": datetime(2026, 11, 9, 11, 37, tzinfo=UTC),
                                       "pop-os": None})
    assert "19,136,843" in text and "wam-desktop" in text and "pop-os" in text
    assert "find" in text and "rg" in text  # it says when to prefer it over the shell
