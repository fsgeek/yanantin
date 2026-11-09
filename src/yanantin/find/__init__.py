"""Find files across machines: the find tool's core (docs/design-find-tool.md).

The response leads with a summary (how many, on which machines, under which
directories, and what the search covered) before any paths, because the first
real find (2026-10-29) was lost to an unsummarized, truncated list. Every call
is recorded as an activity fact, so the case log and "have I searched this
before?" are queries over find's own history.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import NAMESPACE_DNS, UUID, uuid5

from pydantic import BaseModel, ConfigDict, model_validator

from yanantin.activity.models import FactRecord
from yanantin.core.aql import run as run_aql
from yanantin.core.storage_obfuscator import StorageObfuscator
from yanantin.recorder.storage.local.linux.walks import latest_walk_start
from yanantin.recorder.storage.objects_definition import (
    OBJECTS_FIND_VIEW,
    PATH_SEGMENTS_ANALYZER,
    STORAGE_OBJECTS,
)

FIND_PROVIDER_ID = uuid5(NAMESPACE_DNS, "yanantin.find")
REGISTRANTS = "StorageRegistrants"
_TOP_DIRECTORIES = 10
_HOST_SUFFIX = re.compile(r"\(([^()]+)\)\s*$")


class CompiledQuery(BaseModel):
    """What to find. Unknown arguments are rejected rather than ignored: a
    misspelled condition silently dropped would widen the search and look
    like an answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str | None = None
    name_contains: str | None = None
    path_segments: tuple[str, ...] = ()
    modified_after: datetime | None = None
    modified_before: datetime | None = None
    machines: tuple[str, ...] = ()
    limit: int = 20

    @model_validator(mode="after")
    def _check(self) -> CompiledQuery:
        if self.limit < 0:
            raise ValueError("limit must be 0 (summary only) or more")
        for bound in (self.modified_after, self.modified_before):
            if bound is not None and bound.tzinfo is None:
                raise ValueError("modified_after/modified_before must be timezone-aware")
        if not self.conditions():
            raise ValueError(
                "find needs at least one condition: name, name_contains, path_segments, "
                "modified_after/modified_before, or machines")
        return self

    def conditions(self) -> dict:
        """The conditions given, normalized; limit is not a condition."""
        out: dict = {}
        if self.name is not None:
            out["name"] = self.name
        if self.name_contains is not None:
            out["name_contains"] = self.name_contains
        if self.path_segments:
            out["path_segments"] = sorted(self.path_segments)
        if self.modified_after is not None:
            out["modified_after"] = _iso(self.modified_after)
        if self.modified_before is not None:
            out["modified_before"] = _iso(self.modified_before)
        if self.machines:
            out["machines"] = sorted(self.machines)
        return out

    def shape(self) -> str:
        """Equal for queries with equal conditions, whatever their limit or order."""
        return json.dumps(self.conditions(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class FindResult:
    total_matched: int
    by_machine: dict[str, int]
    top_directories: list[tuple[str, int]]
    coverage: list[dict]
    hits: list[dict]
    fact_id: UUID
    duplicate_of: UUID | None


def _iso(t: datetime) -> str:
    # Stored times look like 2026-06-27T22:17:42.698289Z; matching that form
    # keeps string comparison in time order.
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _like_literal(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _machine_names(db, obfuscator: StorageObfuscator, registrants: str) -> dict[str, str]:
    """source id -> machine name, from the registrant's name suffix "(host)"."""
    name = obfuscator.field_path(("registrant_name",))
    rows = run_aql(db, f"FOR r IN @@reg RETURN [r._key, r.{name}]",
                   bind_vars={"@reg": obfuscator.collection_name(registrants)})
    names = {}
    for key, registrant_name in rows:
        match = _HOST_SUFFIX.search(registrant_name or "")
        names[key] = match.group(1) if match else key[:8]
    return names


def find_objects(
    db,
    query: CompiledQuery,
    *,
    activity,
    obfuscator: StorageObfuscator,
    collection: str = STORAGE_OBJECTS,
    view: str = OBJECTS_FIND_VIEW,
    registrants: str = REGISTRANTS,
) -> FindResult:
    """Find objects matching every condition in query, summary first.

    Coverage lists every machine with a recorded walk (and any machine in this
    result without one), so "no matches" is never mistaken for "doesn't exist".
    A missing view raises; there is no fallback to a scan.
    """
    del collection  # the view is the only path; kept in the signature for symmetry
    started = time.perf_counter()
    if not any(v["name"] == view for v in db.views()):
        raise LookupError(f"find view {view!r} does not exist; create it with ensure_objects_find_view")

    f = {k: obfuscator.field_path((k,)) for k in ("uri", "label", "modified", "source", "size")}
    names = _machine_names(db, obfuscator, registrants)
    by_name: dict[str, list[str]] = {}
    for source, machine in names.items():
        by_name.setdefault(machine, []).append(source)

    search: list[str] = []
    bind: dict = {"@view": view}
    for i, seg in enumerate(query.path_segments):
        search.append(f"ANALYZER(d.{f['uri']} == @seg{i}, @analyzer)")
        bind[f"seg{i}"] = seg
    if query.path_segments:
        bind["analyzer"] = PATH_SEGMENTS_ANALYZER
    if query.name is not None:
        search.append(f"d.{f['label']} == @name")
        bind["name"] = query.name
    if query.name_contains is not None:
        search.append(f"LIKE(d.{f['label']}, @like)")
        bind["like"] = f"%{_like_literal(query.name_contains)}%"
    if query.modified_after is not None:
        search.append(f"d.{f['modified']} >= @after")
        bind["after"] = _iso(query.modified_after)
    if query.modified_before is not None:
        search.append(f"d.{f['modified']} < @before")
        bind["before"] = _iso(query.modified_before)
    if query.machines:
        unknown = [m for m in query.machines if m not in by_name]
        if unknown:
            raise ValueError(f"unknown machine(s) {unknown}; indexed machines are {sorted(by_name)}")
        search.append(f"d.{f['source']} IN @sources")
        bind["sources"] = [s for m in query.machines for s in by_name[m]]
    head = f"FOR d IN @@view SEARCH {' AND '.join(search)}"
    # The analyzer matches a segment anywhere in the URI, file name included;
    # path_segments are directory names, so the segment must precede the last "/".
    for i in range(len(query.path_segments)):
        head += (f" FILTER CONTAINS(CONCAT(REGEX_REPLACE(d.{f['uri']}, '/[^/]*$', ''), '/'),"
                 f" CONCAT('/', @seg{i}, '/'))")

    per_source = list(run_aql(
        db, f"{head} COLLECT s = d.{f['source']} WITH COUNT INTO n RETURN [s, n]", bind_vars=bind))
    by_machine: dict[str, int] = {}
    for source, n in per_source:
        machine = names.get(source, str(source)[:8])
        by_machine[machine] = by_machine.get(machine, 0) + n
    total = sum(by_machine.values())

    top_directories = [tuple(row) for row in run_aql(
        db,
        f"{head} COLLECT dir = REGEX_REPLACE(d.{f['uri']}, '/[^/]*$', '') WITH COUNT INTO n "
        f"SORT n DESC, dir LIMIT {_TOP_DIRECTORIES} RETURN [dir, n]",
        bind_vars=bind)] if total else []

    hits = []
    if query.limit and total:
        rows = run_aql(
            db,
            f"{head} SORT d.{f['modified']} DESC LIMIT @limit "
            f"RETURN {{uri: d.{f['uri']}, source: d.{f['source']}, "
            f"modified: d.{f['modified']}, size: d.{f['size']}}}",
            bind_vars={**bind, "limit": query.limit})
        hits = [{"uri": r["uri"], "machine": names.get(r["source"], str(r["source"])[:8]),
                 "modified": r["modified"], "size": r["size"]} for r in rows]

    # Every registered source, walked or not: "registered, never walked" is
    # exactly what someone deciding whether to believe "no matches" needs.
    coverage = []
    for source, machine in sorted(names.items(), key=lambda kv: kv[1]):
        if source == str(FIND_PROVIDER_ID):
            continue
        try:
            last = latest_walk_start(fact.data for fact in activity.query_range(UUID(source)))
        except ValueError:  # a registrant key that is not a provider UUID
            last = None
        coverage.append({"machine": machine, "last_walk": last})

    shape = query.shape()
    previous = [fact for fact in activity.query_range(FIND_PROVIDER_ID)
                if fact.data.get("query_shape") == shape]
    duplicate_of = max(previous, key=lambda fact: fact.timestamp).id if previous else None
    fact = FactRecord(
        provider_id=FIND_PROVIDER_ID,
        timestamp=datetime.now(timezone.utc),
        data={
            "query": query.model_dump(mode="json"),
            "query_shape": shape,
            "total_matched": total,
            "by_machine": by_machine,
            "returned": [h["uri"] for h in hits],
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "duplicate_of": str(duplicate_of) if duplicate_of else None,
        },
    )
    activity.store_fact(fact)
    return FindResult(total_matched=total, by_machine=by_machine, top_directories=top_directories,
                      coverage=coverage, hits=hits, fact_id=fact.id, duplicate_of=duplicate_of)
