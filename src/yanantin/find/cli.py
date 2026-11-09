"""find from the command line: one loop over query lines, from a file or a person.

    yanantin-find                     # interactive: one query per line
    yanantin-find queries.txt         # the same loop over a file (the regression harness)
    yanantin-find --json queries.txt  # the MCP tool's compact JSON instead of text

A line is key=value pairs (shell quoting), or a JSON object using the tool's
argument names. Short keys: contains, segment, after, before, machine; segment
and machine may repeat. Blank lines and lines starting with # are skipped.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from collections.abc import Callable, Iterable
from typing import TextIO

from yanantin.find import CompiledQuery
from yanantin.find.render import parse_when
from yanantin.find.render import render as render_json

_KEYS = {
    "name": "name", "name_contains": "name_contains", "contains": "name_contains",
    "path_segments": "path_segments", "segment": "path_segments",
    "modified_after": "modified_after", "after": "modified_after",
    "modified_before": "modified_before", "before": "modified_before",
    "machines": "machines", "machine": "machines", "limit": "limit",
}
_REPEATING = {"path_segments", "machines"}


def parse_line(line: str) -> CompiledQuery | None:
    """One query, or None for a blank line or a comment."""
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("{"):
        args = json.loads(text)
    else:
        args: dict = {}
        for token in shlex.split(text):
            key, sep, value = token.partition("=")
            if not sep:
                raise ValueError(f"{token!r} is not key=value")
            if key not in _KEYS:
                raise ValueError(f"unknown key {key!r}; known keys: {', '.join(sorted(_KEYS))}")
            field = _KEYS[key]
            if field in _REPEATING:
                args.setdefault(field, []).append(value)
            else:
                args[field] = int(value) if field == "limit" else value
    for field in ("modified_after", "modified_before"):
        if field in args:
            args[field] = parse_when(args[field])
    for field in _REPEATING:
        if field in args:
            args[field] = tuple(args[field])
    return CompiledQuery(**args)


def human(response: dict) -> str:
    """The MCP tool's response, as lines a person reads."""
    def home(path: str) -> str:
        return path.replace("/home/tony", "~", 1)
    total = response["total_matched"]
    lines = [f"{total:,} {'match' if total == 1 else 'matches'}: "
             + (", ".join(f"{n:,} {m}" for m, n in sorted(response["by_machine"].items(), key=lambda kv: -kv[1]))
                or "none")]
    if response["top_directories"]:
        lines.append("  under: " + "; ".join(f"{n:,} {home(d)}" for d, n in response["top_directories"][:5]))
    lines += [f"  {m:<20} {when:<17} {size:>12,}  {home(path)}" for m, when, size, path in response.get("hits", [])]
    if "repeat_of" in response:
        lines.append(f"  (same search as {response['repeat_of']})")
    if "hint" in response:
        lines.append("  " + response["hint"])
    lines.append("  searched: " + ", ".join(f"{m} ({w})" for m, w in response["coverage"].items()))
    return "\n".join(lines)


def run(lines: Iterable[str], finder: Callable, out: TextIO, render: Callable = human) -> None:
    """The loop: parse, find, print; a bad line is reported and the loop goes on."""
    for line in lines:
        try:
            query = parse_line(line)
            if query is None:
                continue
            print(render(finder(query)), file=out, flush=True)
        except ValueError as e:
            print(f"error: {e}", file=out, flush=True)


def _prompted() -> Iterable[str]:
    while True:
        try:
            yield input("find> ")
        except EOFError:
            return


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", help="query lines (default: interactive, or stdin when piped)")
    ap.add_argument("--json", action="store_true", help="print the tool's compact JSON instead of text")
    args = ap.parse_args(argv)

    from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
    from yanantin.core.storage_obfuscator import TransparentObfuscator
    from yanantin.find import find_objects
    from yanantin.infra.config import objects_database, objects_params

    db, activity, obf = objects_database(), ArangoDBActivityStreamStore(**objects_params()), TransparentObfuscator()

    def finder(query: CompiledQuery) -> dict:
        return render_json(find_objects(db, query, activity=activity, obfuscator=obf))

    render = (lambda r: json.dumps(r, separators=(",", ":"))) if args.json else human
    if args.file:
        with open(args.file) as f:
            run(f, finder, sys.stdout, render)
    else:
        run(_prompted() if sys.stdin.isatty() else sys.stdin, finder, sys.stdout, render)


if __name__ == "__main__":
    main()
