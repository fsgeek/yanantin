"""Find objects by path segment, name and time.

Tony's target (2026-10-16): ".ssh" in the directory part of the URI and "config"
as the name, across machines, within 50 ms. Segments are exact (".ssh" is not
"ssh"); every given segment must appear somewhere in the URI.

Each structure does what it is fast at (measured 2026-10-26 on 4.4M objects):
segments and name go to the objects_find view (3 ms; a scan took 2,973 ms); a
time window filters that small candidate set, or, with no segment or name, goes
to the persistent modified index (12 ms, against 77 ms as a view string range).
"""

from __future__ import annotations

from yanantin.core.aql import run as run_aql
from yanantin.core.storage_obfuscator import StorageObfuscator
from yanantin.recorder.storage.objects_definition import (
    OBJECTS_FIND_VIEW,
    PATH_SEGMENTS_ANALYZER,
    STORAGE_OBJECTS,
)


def find_objects(
    db,
    obfuscator: StorageObfuscator,
    *,
    segments: tuple[str, ...] = (),
    label: str | None = None,
    modified_from: str | None = None,
    modified_to: str | None = None,
    view: str = OBJECTS_FIND_VIEW,
    collection: str = STORAGE_OBJECTS,
    limit: int = 1000,
    wait_for_sync: bool = False,
) -> list[dict]:
    """Objects matching every condition given, as {uri, source}. At least one
    condition is required. source is the collector that saw the object, so the
    same path on two machines comes back as two hits.

    modified_from/to are ISO strings, inclusive/exclusive. wait_for_sync makes the
    view include writes not yet indexed (read-your-writes; slower).
    """
    uri = obfuscator.field_path(("uri",))
    lab = obfuscator.field_path(("label",))
    mod = obfuscator.field_path(("modified",))
    src = obfuscator.field_path(("source",))
    bind: dict = {"limit": limit}

    search = []
    for i, seg in enumerate(segments):
        search.append(f"ANALYZER(d.{uri} == @seg{i}, @analyzer)")
        bind[f"seg{i}"] = seg
    if segments:
        bind["analyzer"] = PATH_SEGMENTS_ANALYZER
    if label is not None:
        search.append(f"d.{lab} == @label")
        bind["label"] = label

    time = []
    if modified_from is not None:
        time.append(f"d.{mod} >= @from")
        bind["from"] = modified_from
    if modified_to is not None:
        time.append(f"d.{mod} < @to")
        bind["to"] = modified_to

    if search:
        bind["@source"] = view
        options = " OPTIONS {waitForSync: true}" if wait_for_sync else ""
        head = f"FOR d IN @@source SEARCH {' AND '.join(search)}{options}"
    elif time:
        bind["@source"] = obfuscator.collection_name(collection)
        head = "FOR d IN @@source"
    else:
        raise ValueError("find_objects needs a segment, a label or a time bound")
    filters = f" FILTER {' AND '.join(time)}" if time else ""
    query = f"{head}{filters} LIMIT @limit RETURN {{uri: d.{uri}, source: d.{src}}}"
    return list(run_aql(db, query, bind_vars=bind))
