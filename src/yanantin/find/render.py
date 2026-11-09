"""Turn a FindResult into the compact response an instance reads.

Every token here is context the caller pays for, so the response drops what
carries nothing (the file:// scheme, sub-minute walk times, field names on each
hit) and keeps what makes "no matches" believable: coverage and what is not
indexed at all.
"""

from __future__ import annotations

from datetime import datetime, timezone

from yanantin.find import FindResult

# Update when a source is walked. Silence about a silo would read as "searched".
NOT_INDEXED = (
    "Not indexed yet: Windows drives (wam-vector; WAM-THREADRIPPER's C: to G:), the Mac (wam-mac, "
    "including iCloud Drive), and cloud accounts (OneDrive, Dropbox, Sync.com, Google Drive). "
    "No match here says nothing about those.")

_ZERO_HINT = (
    "No match on the machines in coverage. Try fewer conditions, name_contains instead of name, "
    "or a wider modified_after/modified_before window; if it may live in a silo listed in "
    "not_indexed, this tool cannot see it.")


def _path(uri: str) -> str:
    return uri[len("file://"):] if uri.startswith("file://") else uri


def _minute(t) -> str | None:
    if t is None:
        return None
    if isinstance(t, str):
        t = datetime.fromisoformat(t)
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def render(result: FindResult) -> dict:
    """Summary first; hits as [machine, modified, size, path]."""
    out: dict = {
        "total_matched": result.total_matched,
        "by_machine": result.by_machine,
        "top_directories": [[_path(d), n] for d, n in result.top_directories],
        "coverage": {c["machine"]: _minute(c["last_walk"]) or "never walked" for c in result.coverage},
        "not_indexed": NOT_INDEXED,
    }
    if result.duplicate_of is not None:
        out["repeat_of"] = str(result.duplicate_of)
    if result.hits:
        out["hits"] = [[h["machine"], _minute(h["modified"]), h["size"], _path(h["uri"])]
                       for h in result.hits]
    elif result.total_matched == 0:
        out["hint"] = _ZERO_HINT
    return out


def parse_when(value: str | None) -> datetime | None:
    """An ISO date (midnight UTC) or an ISO date-time with a time zone."""
    if value is None:
        return None
    t = datetime.fromisoformat(value)
    if "T" not in value and " " not in value:
        return t.replace(tzinfo=timezone.utc)
    if t.tzinfo is None:
        raise ValueError(f"{value!r} has a time but no time zone; add Z or an offset like +00:00")
    return t


def describe_store(objects: int, last_walks: dict[str, datetime | None]) -> str:
    """The server's one paragraph about itself, rebuilt from the store at start."""
    walks = ", ".join(f"{m} walked {_minute(t)}" if t else f"{m} never walked"
                      for m, t in sorted(last_walks.items()))
    return (
        f"yanantin indexes {objects:,} files on {len(last_walks)} machines ({walks}). "
        "For a file outside the current repository, on another machine, or remembered by when it "
        "changed rather than where it is, call find_objects before find, rg or ls: it searches every "
        "machine at once and answers summary first (counts per machine and directory) in "
        f"milliseconds to a few seconds. {NOT_INDEXED}")
