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
from datetime import datetime, timezone
from uuid import uuid4

import pytest

# Pour B (spec §2): the canonical timestamp UUIDs are DELETED. Indaleko assigned
# stable UUIDs to timestamp roles so silos could join on "when" — a silo-
# independent naming layer built INSIDE the object because Indaleko had no Pukara.
# Yanantin's Pukara (SchemaMap/obfuscator) IS that layer, lifted out and made
# systematic. Cross-silo joining is the boundary's job; the object's timestamps
# are the four plain, flat, nullable names. Guard 2 below asserts the UUID-keyed
# shape did NOT survive (positive proof cross-silo naming did not creep back).


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


# ── Guard 2: timestamps are FLAT, NULLABLE, and NOT UUID-named (spec §2) ──
#
# Pour B reversed this guard's original requirement. Indaleko UUID-keyed the
# timestamps to join silos on "when"; yanantin's Pukara does that systematically
# at the boundary, so the object carries the four PLAIN names — flat, top-level
# (the hottest query axis must not be taxed with an unwind), nullable (absence is
# legible). The cross-silo join is tested at the Pukara boundary, NOT here.

def test_canonical_timestamps_are_flat_and_nullable():
    """The four file timestamps are flat top-level, nullable, plain-named
    (created/modified/accessed/changed) — NOT UUID-keyed. Cross-silo joining is
    Pukara's job (spec §2 deletes the canonical UUIDs); a guard enforcing the
    superseded UUID-keying would lock in the mistake. Positive proof the
    cross-silo naming layer did NOT creep back into the object."""
    obj = _load_storage_object()
    assert obj is not None, "uniform storage object absent; build it (spec §1)."

    fields = obj.model_fields
    for ts in ("created", "modified", "accessed", "changed"):
        assert ts in fields, (
            f"timestamp {ts!r} must be a flat top-level field on the object, "
            "not nested and not UUID-keyed (spec §2)."
        )
        # Nullable + defaulted None: absence is legible, not faked.
        instance = obj(
            object_identifier=uuid4(),
            uri="file:///probe",
            source=uuid4(),
            observed_at=datetime.now(timezone.utc),
        )
        assert getattr(instance, ts) is None, (
            f"timestamp {ts!r} must default to None (absence is information)."
        )

    assert getattr(obj, "CANONICAL_TIMESTAMP_UUIDS", None) is None, (
        "the object declares CANONICAL_TIMESTAMP_UUIDS — the cross-silo naming "
        "layer crept back INTO the object. Pukara owns cross-silo joining "
        "(spec §2); the object's timestamps are the four plain flat names."
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
        instance = obj(
            object_identifier=uuid4(),
            uri="file:///probe",
            source=uuid4(),
            observed_at=datetime.now(timezone.utc),
            semantic_attributes={probe_uuid: 2756347094955649599},
        )
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
