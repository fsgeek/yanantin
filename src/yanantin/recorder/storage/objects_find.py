"""Find objects by path segment, name and time: one SEARCH over the objects_find view.

Tony's target (2026-10-16): ".ssh" in the directory part of the URI and "config"
as the name, across machines, within 50 ms. Segments are exact (".ssh" is not
"ssh"); every given segment must appear somewhere in the URI.
"""

from __future__ import annotations

from yanantin.core.aql import run as run_aql
from yanantin.core.storage_obfuscator import StorageObfuscator
from yanantin.recorder.storage.objects_definition import OBJECTS_FIND_VIEW, PATH_SEGMENTS_ANALYZER


def find_objects(
    db,
    obfuscator: StorageObfuscator,
    *,
    segments: tuple[str, ...] = (),
    label: str | None = None,
    modified_from: str | None = None,
    modified_to: str | None = None,
    view: str = OBJECTS_FIND_VIEW,
    limit: int = 1000,
    wait_for_sync: bool = False,
) -> list[str]:
    """URIs of objects matching every condition given. At least one is required.

    modified_from/to are ISO strings, inclusive/exclusive. wait_for_sync makes the
    view include writes not yet indexed (read-your-writes; slower).
    """
    uri = obfuscator.field_path(("uri",))
    lab = obfuscator.field_path(("label",))
    mod = obfuscator.field_path(("modified",))
    conditions, bind = [], {"@view": view, "limit": limit}
    for i, seg in enumerate(segments):
        conditions.append(f"ANALYZER(d.{uri} == @seg{i}, @analyzer)")
        bind[f"seg{i}"] = seg
    if segments:
        bind["analyzer"] = PATH_SEGMENTS_ANALYZER
    if label is not None:
        conditions.append(f"d.{lab} == @label")
        bind["label"] = label
    if modified_from is not None:
        conditions.append(f"d.{mod} >= @from")
        bind["from"] = modified_from
    if modified_to is not None:
        conditions.append(f"d.{mod} < @to")
        bind["to"] = modified_to
    if not conditions:
        raise ValueError("find_objects needs a segment, a label or a time bound")
    options = " OPTIONS {waitForSync: true}" if wait_for_sync else ""
    query = (
        f"FOR d IN @@view SEARCH {' AND '.join(conditions)}{options} "
        f"LIMIT @limit RETURN d.{uri}"
    )
    return list(run_aql(db, query, bind_vars=bind))
