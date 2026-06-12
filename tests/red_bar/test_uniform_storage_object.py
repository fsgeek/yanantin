"""Cross-silo uniformity guard: a file is a file is a file, every silo.

Indaleko had a uniform storage object — `../indaleko/storage/i_object.py`,
`IndalekoObject` — whose entire job was *uniformity of information structure*
across silos. Its load-bearing features:

  - the four canonical timestamps as **named UUIDs** (CREATION / MODIFICATION /
    ACCESS / CHANGE), so a filesystem `st_mtime` and a Dropbox `modified_time`
    resolve to the **same join key** — the cross-silo temporal join that makes
    "files from the month I was in Lima" answerable across every store at once;
  - an **open** `SemanticAttributes` lane (UUID-keyed bag) so any collector can
    extend the object without editing a closed schema — late binding, the
    `extra=allow` posture the whole pipeline depends on;
  - the **raw blob retained beside** the normalized view — normalize for
    queryability, never discard the original.

That object did NOT port to yanantin. The pipeline grammar
(collector/wrangler/recorder) ported; the *object the pipeline moves* did not.
In its place each silo normalizes to its own closed model — `FileEntryData`
(`extra="forbid"`, `uri must start with file://`) and `DropboxEntryData`
(flat `modified_time`) — two incompatible shapes stuffed into opaque tensor
JSON. There is no shared shape for the query layer to grip, so cross-silo find
is structurally impossible: the join key ("when") has two different names and a
recorder must know which silo it is reading to extract it.

This is the closed-schema reflex (yanantin's recurring erosion: careful, closed,
single-silo objects get built; the messy, open, cross-silo object does not).
These guards convert that prohibition from prose into a running red bar. They
are HONESTLY RED today — the uniform object does not exist yet. They go green
when a `yanantin.collector.storage_object.StorageObject` (or equivalent) is
ported from `i_object.py` carrying the three contract features above, and both
real collectors normalize to it.

Tracked: the i_object.py port. Related: yanantin#3 (window axis — the temporal
join these named-UUID timestamps make cross-silo), the save-it-all law
(raw-retained-beside-normalized), closed_schema_is_the_llm_default.

A correctly-red result here is the honest signal until the uniform object lands.
Do NOT satisfy these by closing the open lane (extra="forbid") — that is the
exact erosion the open `SemanticAttributes` bag was designed to resist; a guard
below asserts the lane is open precisely so it cannot be "fixed" by closing it.
"""

from __future__ import annotations

import importlib

import pytest

# The four canonical timestamp roles every storage object must expose under a
# stable, silo-independent identity. Values are the UUIDs Indaleko assigned in
# storage/i_object.py — reused so the two systems' timestamps are joinable and
# a future bridge does not have to invent a fresh, divergent set.
CANONICAL_TIMESTAMP_UUIDS = {
    "created": "6b3f16ec-52d2-4e9b-afd0-e02a875ec6e6",
    "modified": "434f7ac1-f71a-4cea-a830-e2ea9a47db5a",
    "accessed": "581b5332-4d37-49c7-892a-854824f5d66f",
    "changed": "3bdc4130-774f-4e99-914e-0bec9ee47aab",
}


def _load_storage_object():
    """Import the uniform storage object, or None if it does not exist yet.

    The contract is named structurally, not by a single hard-coded path: the
    port may land as StorageObject / UniformObject / IObject. Any of those in
    yanantin.collector.storage_object satisfies the import.
    """
    try:
        module = importlib.import_module("yanantin.collector.storage_object")
    except ModuleNotFoundError:
        return None
    for name in ("StorageObject", "UniformObject", "IObject", "FileObject"):
        obj = getattr(module, name, None)
        if obj is not None:
            return obj
    return None


# ── Guard 1: the uniform storage object must EXIST ────────────────────
#
# Honestly red today. The pipeline that moves storage objects ported; the
# object did not. Cross-silo find cannot work without one shared shape.

def test_uniform_storage_object_exists():
    """A silo-independent storage object must exist for cross-silo find.
    Without it, filesystem and Dropbox files are incomparable JSON blobs and
    the query layer has no shared shape to grip. Port from i_object.py."""
    obj = _load_storage_object()
    assert obj is not None, (
        "No uniform storage object found in "
        "yanantin.collector.storage_object. The pipeline grammar ported but "
        "the object it moves (Indaleko's IndalekoObject, i_object.py) did not. "
        "Cross-silo find is structurally impossible until a shared file shape "
        "exists. This guard is honestly red until the port lands."
    )


# ── Guard 2: timestamps must be UUID-named so silos JOIN ──────────────
#
# The whole value of the temporal axis is as a cross-silo join key. A timestamp
# named `modified` on FileEntryData and `modified_time` on DropboxEntryData
# cannot be joined without per-silo knowledge. Named-UUID timestamps fix this.

def test_canonical_timestamps_are_uuid_named():
    """The four timestamps must be addressable by a stable, silo-independent
    UUID identity (created/modified/accessed/changed), not by a per-silo Python
    attribute name. This is what lets a filesystem mtime and a Dropbox
    modified_time be the SAME join key — the cross-silo temporal axis
    (yanantin#3). Honestly red until the uniform object carries them."""
    obj = _load_storage_object()
    if obj is None:
        pytest.fail(
            "uniform storage object absent; cannot carry canonical "
            "UUID-named timestamps. Port i_object.py."
        )
    declared = getattr(obj, "CANONICAL_TIMESTAMP_UUIDS", None)
    assert declared is not None, (
        "uniform storage object does not declare CANONICAL_TIMESTAMP_UUIDS. "
        "The four timestamps must carry stable cross-silo UUID identity so "
        "silos join on 'when'. See i_object.py lines 58-61."
    )
    assert dict(declared) == CANONICAL_TIMESTAMP_UUIDS, (
        "canonical timestamp UUIDs diverge from Indaleko's. Reuse the "
        "i_object.py UUIDs so the two systems' temporal data is joinable; "
        f"expected {CANONICAL_TIMESTAMP_UUIDS}, got {dict(declared)}."
    )


# ── Guard 3: the semantic-attribute lane must be OPEN ─────────────────
#
# i_object.py's genius is a fixed spine PLUS an open UUID-keyed bag. The
# erosion that lost the object also wrote its replacements extra="forbid".
# This guard asserts the open lane exists AND accepts an undeclared
# UUID-keyed attribute — so the contract cannot be satisfied by closing it.

def test_semantic_attribute_lane_is_open():
    """The uniform object must carry an OPEN semantic-attribute lane: a
    collector can attach a UUID-keyed attribute the base schema never declared,
    and it round-trips. Closing this lane (extra="forbid") is the precise
    erosion the bag resists — so 'fixing' the guard by closing it must itself
    fail. Honestly red until the open lane exists."""
    obj = _load_storage_object()
    if obj is None:
        pytest.fail(
            "uniform storage object absent; cannot host an open "
            "semantic-attribute lane. Port i_object.py."
        )
    # An arbitrary UUID-keyed attribute no base schema declares.
    probe_uuid = "3fa47f24-b198-434d-b440-119ec5af4f7d"  # i_object's st_dev
    try:
        instance = obj(semantic_attributes={probe_uuid: 2756347094955649599})
    except Exception as exc:  # noqa: BLE001 — any rejection is a closed lane
        pytest.fail(
            "uniform storage object rejected an undeclared UUID-keyed "
            f"semantic attribute ({type(exc).__name__}: {exc}). The lane is "
            "closed. The open bag (i_object.py SemanticAttributes) must accept "
            "collector-defined attributes without a schema edit — that is the "
            "late-binding the pipeline depends on. Do not close it."
        )
    stored = getattr(instance, "semantic_attributes", {})
    assert stored.get(probe_uuid) == 2756347094955649599, (
        "undeclared semantic attribute did not round-trip through the open "
        "lane. The bag must retain what a collector attaches."
    )
