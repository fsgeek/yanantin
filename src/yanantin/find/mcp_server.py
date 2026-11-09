"""MCP server for the find tool (docs/design-find-tool.md).

It says one paragraph about itself at start, rebuilt from the store (scale,
machines, last walks, when to prefer it over find/rg), because AI customers
don't volunteer that a tool exists or is missing; the description has to win
against habit. Unlike khipumaq's content-free events, each call's arguments
and returned paths are recorded: they are Tony's own file names in yanantin's
own backed-up database, and the case log needs them.

Run:  yanantin-find-mcp   (stdio; needs the find-mcp extra)
"""

from __future__ import annotations

import json
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.core.storage_obfuscator import TransparentObfuscator
from yanantin.find import FIND_PROVIDER_ID, REGISTRANTS, CompiledQuery, _machine_names
from yanantin.find import find_objects as _find
from yanantin.find.render import describe_store, parse_when, render
from yanantin.infra.config import objects_database, objects_params
from yanantin.recorder.storage.local.linux.walks import latest_walk_start
from yanantin.recorder.storage.objects_definition import STORAGE_OBJECTS

_db = objects_database()
_activity = ArangoDBActivityStreamStore(**objects_params())
_obfuscator = TransparentObfuscator()  # arango-objects stores semantic names (2026-11-09)


def _self_description() -> str:
    names = _machine_names(_db, _obfuscator, REGISTRANTS)
    last = {}
    for source, machine in names.items():
        if source == str(FIND_PROVIDER_ID):
            continue
        try:
            last[machine] = latest_walk_start(f.data for f in _activity.query_range(UUID(source)))
        except ValueError:
            continue
    objects = _db.collection(STORAGE_OBJECTS).count()
    return describe_store(objects, last)


mcp = FastMCP("yanantin", instructions=_self_description())


@mcp.tool(annotations=ToolAnnotations(title="Find files across machines", openWorldHint=False))
def find_objects(
    name: str | None = None,
    name_contains: str | None = None,
    path_segments: list[str] | None = None,
    modified_after: str | None = None,
    modified_before: str | None = None,
    machines: list[str] | None = None,
    limit: int = 20,
) -> str:
    """Find files by name, directory and time on every indexed machine at once.

    Use it before find, rg or ls for anything outside the current repository, on
    another machine, or remembered by WHEN rather than WHERE. People misremember
    where a file lives far more often than when they worked on it.

    Give at least one condition; all given conditions must hold:
    - name: exact file name ("pyproject.toml").
    - name_contains: substring of the file name ("openrouter"). About 150 ms warm,
      up to a few seconds cold.
    - path_segments: directory names that must all appear in the path, matched
      exactly (".ssh" is not "ssh").
    - modified_after / modified_before: ISO date ("2025-11-24") or date-time with
      a zone. The cheapest narrowing there is; add it whenever the person
      remembers roughly when.
    - machines: hostnames from the coverage list (default: every machine). An
      unknown name is an error that lists the known ones.
    - limit: paths to return (default 20). limit=0 is NOT "return nothing": it
      returns the full summary without paths, the cheapest way to see how big
      a match is before asking for paths.

    The response leads with total_matched, by_machine, top_directories and
    coverage (each machine's last walk), then hits as [machine, modified, size,
    path], newest first. no-match responses keep coverage and not_indexed, so
    "not found" is never "doesn't exist": check not_indexed before concluding.
    """
    query = CompiledQuery(
        name=name, name_contains=name_contains, path_segments=tuple(path_segments or ()),
        modified_after=parse_when(modified_after), modified_before=parse_when(modified_before),
        machines=tuple(machines or ()), limit=limit)
    # Compact JSON: FastMCP would pretty-print a dict, and the indentation alone
    # cost ~40% of a summary's tokens.
    return json.dumps(render(_find(_db, query, activity=_activity, obfuscator=_obfuscator)),
                      separators=(",", ":"), ensure_ascii=False)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
