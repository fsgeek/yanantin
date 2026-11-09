#!/usr/bin/env python3
"""Measure whether instances use the find tool or keep reaching for the shell.

The instrument for predictions/2026-11-09-find-non-use-claude.md; its
definitions are that page's, and it was tested on synthetic transcripts only
before any real window was measured. Run it when the pre-registration's due
condition holds (100 find calls in the after window, or 2026-12-07):

    uv run python scripts/measure_find_non_use.py            # JSON on stdout
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

FIND_TOOL = "mcp__yanantin__find_objects"
CUTOFF = "2026-11-09T19:34:00Z"
BEFORE_START = "2026-10-12T19:34:00Z"
EXCLUDE = {"d02f77a0"}  # the steward's own session that built the tool
FOLLOW = 5  # tool calls after a find call that count as "next"

_FILE_LOCATION = [
    re.compile(r"\bfind\b[^|;&]*\s-(?:i?name|i?path|regex)\b"),
    re.compile(r"(?:^|[\s;&|(])p?locate\s"),
    re.compile(r"(?:^|[\s;&|(])(?:fd|fdfind)\s"),
    re.compile(r"\brg\b[^|;&]*\s(?:--files\b|-g\b|--glob\b)"),
]
_REDIRECT = re.compile(r"\d*>>?\s*\S+")


def is_file_location(command: str) -> bool:
    return any(p.search(command) for p in _FILE_LOCATION)


def _segments(command: str) -> list[list[str]]:
    out = []
    for piece in re.split(r"&&|\|\||[;|]", _REDIRECT.sub(" ", command)):
        try:
            out.append(shlex.split(piece))
        except ValueError:
            out.append(piece.split())
    return [s for s in out if s]


def _roots(tokens: list[str]) -> list[str] | None:
    """Search roots of one command segment, or None when it is not a file-location tool."""
    cmd = tokens[0].rsplit("/", 1)[-1]
    rest = tokens[1:]
    if cmd == "find":
        roots = []
        for t in rest:
            if t.startswith("-") or t in ("(", "!"):
                break
            roots.append(t)
        return roots or ["."]
    if cmd in ("fd", "fdfind"):
        positional = [t for t in rest if not t.startswith("-")]
        return positional[1:] or ["."]
    if cmd == "rg":
        positional, skip = [], False
        for t in rest:
            if skip:
                skip = False
                continue
            if t in ("-g", "--glob", "-t", "--type", "-e", "--regexp"):
                skip = True
                continue
            if not t.startswith("-"):
                positional.append(t)
        listing = "--files" in rest
        return (positional if listing else positional[1:]) or ["."]
    return None


def outside_scope(command: str, cwd: str) -> bool:
    if re.search(r"(?:^|\s)ssh\s", command) or re.search(r"(?:^|[\s;&|(])p?locate\s", command):
        return True
    home = os.path.expanduser("~")
    for tokens in _segments(command):
        roots = _roots(tokens)
        if roots is None:
            continue
        for root in roots:
            expanded = re.sub(r"^(?:~|\$HOME|\$\{HOME\})", home, root)
            if not expanded.startswith("/"):
                continue  # relative: under the cwd
            path = os.path.normpath(expanded)
            if not (path == cwd or path.startswith(cwd.rstrip("/") + "/")):
                return True
    return False


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(c.get("text", "") for c in content if isinstance(c, dict))
    return ""


def _read_session(path: Path) -> dict | None:
    calls, results, seen = [], {}, set()
    first = last = cwd = sid = None
    sidechain = "subagents" in path.parts
    for line in path.open(errors="replace"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = e.get("timestamp")
        if ts:
            first = first or ts
            last = ts
        cwd = cwd or e.get("cwd")
        sid = sid or e.get("sessionId")
        sidechain = sidechain or bool(e.get("isSidechain"))
        for c in (e.get("message") or {}).get("content") or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "tool_use" and c.get("id") not in seen:
                seen.add(c.get("id"))
                calls.append((c.get("id"), c.get("name"), c.get("input") or {}))
            elif c.get("type") == "tool_result":
                results[c.get("tool_use_id")] = _text(c.get("content"))
    if first is None:
        return None
    return {"id": sid or path.stem, "first": first, "last": last, "cwd": cwd or "/",
            "sidechain": sidechain, "calls": calls, "results": results}


def _shell_outside(call, cwd) -> bool:
    _, name, inp = call
    command = inp.get("command", "") if name == "Bash" else ""
    return bool(command) and is_file_location(command) and outside_scope(command, cwd)


def measure(dirs, *, cutoff=CUTOFF, before_start=BEFORE_START, exclude=EXCLUDE) -> dict:
    windows = {"after": [], "before": []}
    for d in dirs:
        for path in Path(d).rglob("*.jsonl"):
            s = _read_session(path)
            if s is None or any(str(s["id"]).startswith(x) for x in exclude):
                continue
            if s["first"] >= cutoff:
                windows["after"].append(s)
            elif s["first"] >= before_start and s["last"] < cutoff:
                windows["before"].append(s)
    out = {}
    for name, sessions in windows.items():
        finds = shell = fallback = with_hits = used = 0
        for s in sessions:
            calls = s["calls"]
            for i, call in enumerate(calls):
                if _shell_outside(call, s["cwd"]):
                    shell += 1
                if call[1] != FIND_TOOL:
                    continue
                finds += 1
                nxt = calls[i + 1:i + 1 + FOLLOW]
                if any(_shell_outside(c, s["cwd"]) for c in nxt):
                    fallback += 1
                try:
                    hits = json.loads(s["results"].get(call[0], "") or "{}").get("hits") or []
                except json.JSONDecodeError:
                    hits = []
                if hits:
                    with_hits += 1
                    paths = {h[3] for h in hits} | {os.path.dirname(h[3]) for h in hits}
                    if any(p and p in json.dumps(c[2]) for c in nxt for p in paths):
                        used += 1
        out[name] = {
            "sessions": len(sessions),
            "subagent_sessions": sum(s["sidechain"] for s in sessions),
            "find_calls": finds,
            "shell_outside": shell,
            "M1_non_use": round(shell / (shell + finds), 3) if shell + finds else None,
            "M2_fallback": round(fallback / finds, 3) if finds else None,
            "M3_use": round(used / with_hits, 3) if with_hits else None,
        }
    return out


if __name__ == "__main__":
    roots = sys.argv[1:] or [os.path.expanduser("~/.claude/projects")]
    print(json.dumps(measure(roots), indent=1))
