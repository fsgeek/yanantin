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
    "Not indexed yet: Windows drives (wam-vector; WAM-THREADRIPPER's C: to G:) and cloud accounts "
    "(OneDrive, Dropbox, Sync.com, Google Drive; iCloud Drive only as the Mac's walk sees it). "
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


# Nightly backups land ~13:28Z, so a healthy one is at most ~24h old.
_BACKUP_STALE_HOURS = 30
_TELL_TONY_HOURS = 72


def health_notice(*, now: datetime, db_error: str | None, refresh_failed_at: datetime | None,
                  last_ok_backup: datetime | None) -> str:
    """What is wrong with yanantin right now, for the server's instructions; "" when nothing is."""
    problems, age = [], 0.0
    if db_error:
        problems.append(f"arango-objects (port 8532) is not answering ({db_error}); find_objects will fail")
    if refresh_failed_at:
        problems.append(f"the nightly refresh failed {_minute(refresh_failed_at)}")
    if last_ok_backup and (age := (now - last_ok_backup).total_seconds() / 3600) > _BACKUP_STALE_HOURS:
        problems.append(f"the newest good backup is {age:.0f}h old")
    if not problems:
        return ""
    # Tony's attention is the scarce thing: he is named only when the index's only
    # second copy is at risk (no good backup for 3 nights). Everything else waits
    # for the steward.
    tell = "Tell Tony now, and leave" if age > _TELL_TONY_HOURS else "Leave"
    return ("YANANTIN IS UNWELL: " + "; ".join(problems) + f". {tell} a note in "
            "/home/tony/projects/yanantin/docs/requests/ for yanantin's steward.")
