"""The find CLI: one loop over lines, whether they come from a file or a person.

Tony (2026-11-09): AI coders fought him over a CLI that could read its queries
from a file or go interactive; "a line of text from an interactive CLI and a line
of text from a file are easily achieved using the same basic loop". The batch
form is also the regression harness: a file of real queries, replayed.
"""

import io
from datetime import datetime, timezone

import pytest

from yanantin.find.cli import parse_line, run

UTC = timezone.utc


def test_key_value_pairs_with_quotes_and_short_names():
    q = parse_line('name_contains=openrouter after=2025-11-18 before=2025-12-03 limit=5')
    assert q.name_contains == "openrouter" and q.limit == 5
    assert q.modified_after == datetime(2025, 11, 18, tzinfo=UTC)
    assert q.modified_before == datetime(2025, 12, 3, tzinfo=UTC)
    q = parse_line('name="my file.txt" segment=.ssh segment=projects machine=gazelle')
    assert q.name == "my file.txt"
    assert q.path_segments == (".ssh", "projects") and q.machines == ("gazelle",)


def test_json_lines_use_the_tool_argument_names():
    q = parse_line('{"name": "pyproject.toml", "limit": 0, "machines": ["wam-nuc"]}')
    assert q.name == "pyproject.toml" and q.limit == 0 and q.machines == ("wam-nuc",)


def test_blank_lines_and_comments_are_not_queries():
    assert parse_line("") is None and parse_line("   ") is None and parse_line("# a note") is None


def test_unknown_keys_are_errors_not_silently_dropped():
    with pytest.raises(ValueError, match="nme"):
        parse_line("nme=config")


def test_the_same_loop_serves_a_file_and_a_person():
    seen = []

    def finder(query):
        seen.append(query.name)
        return {"total_matched": 1}

    lines = ["name=a", "# skipped", "", "name=b", "nme=c", "name=d"]
    out = io.StringIO()
    run(iter(lines), finder, out, render=lambda r: f"total {r['total_matched']}")
    assert seen == ["a", "b", "d"]  # a bad line is reported and the loop goes on
    text = out.getvalue()
    assert text.count("total 1") == 3 and "nme" in text
