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
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
from yanantin.core.storage_obfuscator import TransparentObfuscator
from yanantin.find import FIND_PROVIDER_ID, REGISTRANTS, CompiledQuery, _machine_names
from yanantin.find import find_objects as _find
from yanantin.find.questions import COLLECTION as QUESTIONS, question_doc
from yanantin.find.render import describe_store, health_notice, parse_when, render
from yanantin.infra.config import objects_database, objects_params
from yanantin.recorder.storage.local.linux.walks import latest_walk_start
from yanantin.recorder.storage.objects_definition import STORAGE_OBJECTS

_obfuscator = TransparentObfuscator()  # arango-objects stores semantic names (2026-11-09)
_db = _activity = None
_db_error: str | None = None
_BACKUP_LOG = Path.home() / "backups/arango-objects/backup-log.jsonl"


def _connect() -> None:
    """Connect if not yet connected. A down server must not stop this one from
    starting: on 2026-11-15 it did, and sessions saw a timeout instead of a reason."""
    global _db, _activity, _db_error
    if _db is not None:
        return
    try:
        _db = objects_database()
        _activity = ArangoDBActivityStreamStore(**objects_params())
        _db_error = None
    except Exception as e:  # any failure here means the same thing to the caller
        _db = _activity = None
        _db_error = str(e).splitlines()[0][:200]


def _refresh_failed_at() -> datetime | None:
    """When yanantin-refresh last failed, if its latest run failed (only where the unit exists)."""
    try:
        out = subprocess.run(
            ["systemctl", "--user", "show", "yanantin-refresh.service", "--timestamp=utc",
             "-p", "LoadState", "-p", "Result", "-p", "InactiveEnterTimestamp"],
            capture_output=True, text=True, timeout=5).stdout.splitlines()
        props = dict(line.split("=", 1) for line in out if "=" in line)  # systemd picks the order
        if props.get("LoadState") != "loaded" or props.get("Result", "success") == "success":
            return None
        return datetime.strptime(props["InactiveEnterTimestamp"],
                                 "%a %Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _last_ok_backup() -> datetime | None:
    try:
        lines = _BACKUP_LOG.read_text().splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        rec = json.loads(line)
        if rec.get("status") == "ok":
            return datetime.fromisoformat(rec["finished"].replace("Z", "+00:00"))
    return None


def _health() -> str:
    return health_notice(now=datetime.now(timezone.utc), db_error=_db_error,
                         refresh_failed_at=_refresh_failed_at(), last_ok_backup=_last_ok_backup())


def _self_description() -> str:
    _connect()
    if _db is None:
        return _health()
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
    health = _health()
    return (health + " " if health else "") + describe_store(objects, last)


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
    _connect()
    if _db is None:
        return json.dumps({"error": _health()}, ensure_ascii=False)
    query = CompiledQuery(
        name=name, name_contains=name_contains, path_segments=tuple(path_segments or ()),
        modified_after=parse_when(modified_after), modified_before=parse_when(modified_before),
        machines=tuple(machines or ()), limit=limit)
    # Compact JSON: FastMCP would pretty-print a dict, and the indentation alone
    # cost ~40% of a summary's tokens.
    return json.dumps(render(_find(_db, query, activity=_activity, obfuscator=_obfuscator)),
                      separators=(",", ":"), ensure_ascii=False)


@mcp.tool(annotations=ToolAnnotations(title="Record a question for yanantin's register", openWorldHint=False))
def record_question(
    text: str,
    asked_by: str = "human",
    verbatim: bool = True,
    context: str | None = None,
    outcome: str | None = None,
) -> str:
    """File a real question in yanantin's question register, the moment it comes up.

    Call it whenever the person mentions looking for something, in any project:
    a file, photo, document, email, message, or a past decision. Cues: "I was
    looking for...", "I couldn't find...", "where did I put...", "which copy...",
    "do you remember when...". Also call it for your own questions as an
    instance ("where did this belief come from?"), with asked_by="instance".
    Tony, 2026-11-20: "The real discipline is capturing these questions
    regularly." The register is yanantin's requirements and evaluation set, so a
    real question is worth more than any invented one.

    - text: the question, in their words when you have them (verbatim=True);
      otherwise your faithful paraphrase (verbatim=False). Never quote a
      paraphrase as their words.
    - asked_by: "human", "instance", or "commons".
    - context: why they were looking, if known (e.g. "for an RTB filing").
    - outcome: how the search went, if known ("found in Google Photos after
      10 min", "gave up"). The route and the outcome are the useful data.

    It records only what you pass. Returns the new entry's key.
    """
    _connect()
    if _db is None:
        return json.dumps({"error": _health()}, ensure_ascii=False)
    doc = question_doc(text, asked_by=asked_by, verbatim=verbatim, context=context,
                       outcome=outcome, project=Path.cwd().name)
    if not _db.has_collection(QUESTIONS):
        _db.create_collection(QUESTIONS)
    _db.collection(QUESTIONS).insert(doc)
    return json.dumps({"recorded": doc["_key"]})


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
