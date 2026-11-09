"""The non-use instrument (predictions/2026-11-09-find-non-use-claude.md), on
synthetic transcripts only: building it must not mean looking at the data."""

import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "measure_find_non_use", Path(__file__).parents[2] / "scripts" / "measure_find_non_use.py")
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)


@pytest.mark.parametrize("cmd,expected", [
    ("find / -name pyproject.toml 2>/dev/null", True),
    ("find ~/projects -iname '*.md'", True),
    ("cd x && find . -path '*/tests/*'", True),
    ("locate openrouter", True),
    ("fd config ~", True),
    ("rg --files /home/tony | head", True),
    ("rg -g '*.toml' -l version", True),
    ("rg TODO src", False),          # content search is out of scope
    ("grep -rn foo .", False),
    ("find . -type f | wc -l", False),  # no name/path condition
    ("ls -la", False),
])
def test_file_location_calls(cmd, expected):
    assert m.is_file_location(cmd) is expected


@pytest.mark.parametrize("cmd,cwd,expected", [
    ("find / -name x", "/home/tony/projects/a", True),
    ("find ~ -name x", "/home/tony/projects/a", True),
    ("find $HOME/projects -name x", "/home/tony/projects/a", True),
    ("find /home/tony/projects/b -name x", "/home/tony/projects/a", True),
    ("find /home/tony/projects/a/src -name x", "/home/tony/projects/a", False),
    ("find . -name x", "/home/tony/projects/a", False),
    ("find src -name x", "/home/tony/projects/a", False),
    ("ssh wam-nuc 'find ~ -name x'", "/home/tony/projects/a", True),
    ("locate x", "/home/tony/projects/a", True),  # locate searches the whole machine
])
def test_outside_scope(cmd, cwd, expected):
    assert m.outside_scope(cmd, cwd) is expected


def _session(tmp_path, sid, ts, events, cwd="/home/tony/projects/a"):
    lines = []
    for i, (name, inp, result) in enumerate(events):
        tid = f"t{i}"
        lines.append({"type": "assistant", "sessionId": sid, "timestamp": ts, "cwd": cwd,
                      "isSidechain": False,
                      "message": {"role": "assistant", "content": [
                          {"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
        lines.append({"type": "user", "sessionId": sid, "timestamp": ts, "cwd": cwd,
                      "message": {"role": "user", "content": [
                          {"type": "tool_result", "tool_use_id": tid, "content": result}]}})
    p = tmp_path / f"{sid}.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in lines))
    return p


def test_measures_on_a_synthetic_after_window(tmp_path):
    hit = json.dumps({"total_matched": 1, "hits": [["m", "2025-11-25T12:06Z", 1, "/home/tony/x/sweep.jsonl"]]})
    # s1: find, then uses the returned path; later a habitual outside-scope find.
    _session(tmp_path, "s1", "2026-11-10T10:00:00Z", [
        ("mcp__yanantin__find_objects", {"name": "sweep.jsonl"}, hit),
        ("Read", {"file_path": "/home/tony/x/sweep.jsonl"}, "..."),
        *[("Edit", {"file_path": "/home/tony/projects/a/f.py"}, "") for _ in range(4)],
        # Six calls after the find: outside the 5-call window, so habit, not fallback.
        ("Bash", {"command": "find / -name other.txt"}, ""),
    ])
    # s2: find, then falls back to the shell for the same thing.
    _session(tmp_path, "s2", "2026-11-10T11:00:00Z", [
        ("mcp__yanantin__find_objects", {"name": "gone.txt"}, json.dumps({"total_matched": 0})),
        ("Bash", {"command": "find ~ -name gone.txt"}, ""),
    ])
    # Before the cutoff: counted only as context.
    _session(tmp_path, "s0", "2026-11-01T10:00:00Z", [("Bash", {"command": "find / -name a"}, "")])
    r = m.measure([tmp_path], cutoff="2026-11-09T19:34:00Z", before_start="2026-10-12T19:34:00Z",
                  exclude={"d02f77a0"})
    assert r["after"]["find_calls"] == 2 and r["after"]["shell_outside"] == 2
    assert r["after"]["M1_non_use"] == 0.5
    assert r["after"]["M2_fallback"] == 0.5
    assert r["after"]["M3_use"] == 1.0          # the one call with hits was used
    assert r["before"]["shell_outside"] == 1 and r["before"]["sessions"] == 1
