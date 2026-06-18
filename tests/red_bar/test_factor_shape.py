"""Cross-consumer factor-shape guard: storage objects and LLM-memory objects
must normalize into ONE shared six-factor shape — or the convergence claim's
structural basis is unbuilt.

The convergence hypothesis (docs/superpowers/specs/
2026-06-13-find-shared-core-convergence-claim.md) rests on a claim that round-2
adversarial review correctly flagged as ASSERTED, not demonstrated:

  > Storage data and LLM-memory are differently-degenerate regions of ONE
  > six-factor coordinate space (who/what/when/where/why/how). Storage-find is
  > the low-dimensional projection of activity-find — a RESTRICTION of the same
  > mechanism, not a separate one.

If that is true, a filesystem object and an LLM-memory object must both be
expressible in the SAME factor shape, with:
  - the factors each one HAS populated,
  - the factors each one LACKS marked explicitly ABSENT (not silently omitted —
    silent omission is the lie-by-omission the whole project resists; a resolver
    must be able to tell "this object has no `why`" from "nobody computed `why`"),
  - the raw source retained beside the normalized factors — ALWAYS, for EVERY
    object, as an invariant of the shape, not a per-object option. (Indaleko
    precedent, Tony: you cannot extract what you did not save. Retained-raw is
    what lets a research prototype "fix" already-collected data by re-extracting
    factors it did not normalize initially, WITHOUT re-collecting — which for a
    cloud/glacial source is the expensive, sometimes-impossible step. Storage is
    cheap; re-collection is not. Normalize for queryability; never normalize
    lossily.) A factor shape constructed without its raw source must be ILLEGAL,
    not merely discouraged — the irreversible direction (discard raw) is closed
    by construction, the reversible one (derive more factors later) stays open.

There is no factor model in `src/` today (verified 2026-06-13: no `FactorValue`,
no coordinate-space type; `FactRecord.data` is an undifferentiated dict). So this
guard is HONESTLY RED. It goes green when a shared factor shape exists and both a
storage object and an LLM-memory object normalize into it.

This converts the load-bearing new vocabulary (six factors, "storage is a
degenerate region") from design prose into an executable gate — the round-2
review's central demand: the new terms need red bars quickly, or assertion feels
like architecture. Tracked: the convergence spec; gh #17 (uniform storage object
is the storage-shaped instance of this).

Do NOT satisfy this by making `absent` mean the same as `missing` — a guard
below asserts they are distinguishable, precisely so the degeneracy is HONEST
(a storage object's missing `why` is a known structural fact, not an un-run
transducer).
"""

from __future__ import annotations

import importlib

import pytest

# The six factors. A factor shape must address all six by stable identity, so a
# resolver can ask "what is this object's `when`" uniformly across silos.
SIX_FACTORS = ("who", "what", "when", "where", "why", "how")


def _load_factor_api():
    """Import the yanantin.factors MODULE, or None if it does not exist yet.

    The guards reference a small surface ON the module: a shape type
    (FactorVector / FactorShape / FactorMap), a FACTORS identity tuple, and
    normalizers (from_storage_object / from_llm_memory). These names are the
    guard's *property targets*, not a committed API — a real implementation may
    rename them, in which case update the guard deliberately (a stronger test is
    never an error) rather than silently.
    """
    try:
        return importlib.import_module("yanantin.factors")
    except ModuleNotFoundError:
        return None


def _require_factor_api():
    api = _load_factor_api()
    if api is None:
        pytest.fail(
            "No yanantin.factors module. The convergence claim's structural "
            "basis (one six-factor space for storage AND LLM-memory) is unbuilt. "
            "Honestly red until it exists."
        )
    return api


def _shape_type(api):
    for name in ("FactorVector", "FactorShape", "FactorMap", "Factors"):
        obj = getattr(api, name, None)
        if obj is not None:
            return obj
    return None


# ── Guard 1: a shared factor shape must EXIST and address all six factors ──

def test_factor_shape_exists_and_covers_six():
    """One shape, addressable by all six factor identities. Without it, storage
    and LLM-memory cannot be 'regions of the same space' — they're just two
    dicts. Honestly red until yanantin.factors exists."""
    api = _require_factor_api()
    declared = getattr(api, "FACTORS", None)
    assert declared is not None, (
        "factor shape does not declare its FACTORS. The six "
        f"({SIX_FACTORS}) must be addressable by stable identity."
    )
    assert tuple(declared) == SIX_FACTORS, (
        f"factor set diverges from the six-factor model; expected {SIX_FACTORS}, "
        f"got {tuple(declared)}."
    )


# ── Guard 2: a STORAGE object normalizes into the shape (degenerate region) ──
#
# Storage = dense what/when/where, thin who, ABSENT why, trivial how. The point
# is not that storage has all six; it is that storage's MISSING factors are
# represented honestly within the SAME shape an activity object uses.

def test_storage_object_normalizes_into_factor_shape():
    """A filesystem-shaped object emits factor values into the shared shape:
    what/when/where present, why explicitly ABSENT (not omitted), raw retained.
    Honestly red until a storage->factor normalizer exists."""
    api = _require_factor_api()
    normalize = getattr(api, "from_storage_object", None)
    if normalize is None:
        pytest.fail(
            "no from_storage_object normalizer on the factor API; cannot show "
            "storage is a region of the factor space."
        )
    fs_like = {
        "name": "design.md",
        "uri": "file:///data/u/design.md",
        "modified": "2026-05-01T12:00:00+00:00",
        "path": "/data/u",
        "size": 1024,
        "_raw": {"st_mode": 33188},
    }
    fv = normalize(fs_like)
    assert fv.get("what") is not None, "storage object must populate `what`"
    assert fv.get("when") is not None, "storage object must populate `when`"
    assert fv.get("where") is not None, "storage object must populate `where`"
    # why must be present-as-ABSENT, distinguishable from never-computed:
    assert fv.is_absent("why"), (
        "a storage object's `why` must be marked explicitly ABSENT (a known "
        "structural fact), not silently omitted."
    )
    assert fv.raw is not None, "raw source must be retained beside the factors"


# ── Guard 3: an LLM-MEMORY object normalizes into the SAME shape ────────────
#
# LLM-memory is degenerate on DIFFERENT axes: rich what (language), real
# when/who (model id, timestamp), thin where, expensive/absent why. The
# convergence claim requires this lands in the SAME shape as storage.

def test_llm_memory_normalizes_into_same_factor_shape():
    """An LLM-memory object (a turn/conclusion) emits into the SAME factor shape
    as the storage object — differently degenerate, same shape. Honestly red
    until an llm-memory->factor normalizer exists."""
    api = _require_factor_api()
    normalize = getattr(api, "from_llm_memory", None)
    if normalize is None:
        pytest.fail(
            "no from_llm_memory normalizer on the factor API; cannot show "
            "LLM-memory is a region of the SAME factor space as storage."
        )
    mem_like = {
        "text": "concluded the silo is a structural-similarity class",
        "model_family": "claude-opus",
        "timestamp": "2026-06-13T20:00:00+00:00",
        "_raw": {"turn_id": "abc"},
    }
    fv = normalize(mem_like)
    assert fv.get("what") is not None, "LLM-memory must populate `what`"
    assert fv.get("when") is not None, "LLM-memory must populate `when`"
    assert fv.get("who") is not None, "LLM-memory must populate `who` (model)"
    assert fv.raw is not None, "raw source must be retained"


# ── Guard 4: ABSENT must be distinguishable from MISSING ───────────────────
#
# The honesty hinge. A storage object's missing `why` is a known structural
# absence; an un-run `why` transducer is unknown. If the shape collapses them,
# the degeneracy is a lie and a resolver cannot reason about coverage.

def test_raw_retention_is_an_invariant_not_an_option():
    """Raw source retention is a property of the SHAPE, for every object,
    unconditionally — you cannot extract what you did not save (Indaleko). A
    factor shape that can be constructed WITHOUT a retained raw source makes the
    irreversible direction (lossy normalization) representable, which is the law
    this guards. Constructing a factor shape with no raw source must FAIL.
    Honestly red until the shape enforces it."""
    api = _require_factor_api()
    shape = _shape_type(api)
    if shape is None:
        pytest.fail("no constructible factor shape to probe raw-retention.")
    # A shape with raw is fine.
    ok = shape(raw={"src": "x"}, what="thing")
    assert ok.raw is not None, "a shape given raw must retain it"
    # A shape with NO raw source must be illegal — discarding the source is the
    # irreversible direction and must not be constructible.
    with pytest.raises((ValueError, TypeError)):
        shape(what="thing")  # no raw → must reject


def test_absent_is_distinguishable_from_unknown():
    """`absent` (known to have no value) must differ from `unknown` (not yet
    computed). Collapsing them makes the degeneracy dishonest. Honestly red
    until the shape encodes the distinction."""
    api = _require_factor_api()
    shape = _shape_type(api)
    if shape is None:
        pytest.fail("no constructible factor shape to probe absent-vs-unknown.")
    absent = shape(raw={"src": "x"}, why="__absent__")
    unknown = shape(raw={"src": "x"})  # nothing said about why
    assert absent.is_absent("why"), "explicit absence must read as absent"
    assert not unknown.is_absent("why"), (
        "an unspecified factor must NOT read as absent — absent (known-empty) and "
        "unknown (not-computed) are different facts a resolver depends on."
    )
