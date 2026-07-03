"""The six-factor shape — one coordinate space for storage AND LLM-memory.

The convergence claim: storage data and LLM-memory are differently-degenerate
regions of ONE six-factor space (who/what/when/where/why/how). This module is
that shape. Storage-find is a projection of activity-find because both normalize
HERE. Spec: docs/superpowers/specs/2026-07-02-factor-shape.md.

The honesty hinge is the three states a factor can be in:
  - present  — a value was computed          (get() returns it)
  - absent   — known to have no value         (is_absent() True; get() None)
  - unknown  — nobody computed it yet         (is_absent() False; get() None)
Collapsing absent into unknown is the lie-by-omission the project resists — a
resolver reasoning about coverage must tell "this object structurally has no
`why`" from "the `why` transducer has not run."

Raw retention is an invariant of the shape, not an option: constructing a
Factors without a raw source raises. You cannot extract what you did not save
(Indaleko) — retained raw keeps the reversible direction (derive more factors
later) open and closes the irreversible one (lossy normalization) by
construction.
"""

from __future__ import annotations

from typing import Any

# The six factors, addressable by stable identity so a resolver can ask "what is
# this object's `when`" uniformly across silos.
FACTORS: tuple[str, ...] = ("who", "what", "when", "where", "why", "how")

# The sentinel a normalizer uses to mark a factor as a KNOWN structural absence,
# distinct from simply not passing it (which reads as unknown/not-yet-computed).
ABSENT = "__absent__"


class Factors:
    """One object's position in the six-factor space, plus its retained raw source.

    Construct with the raw source and any known factor values:
        Factors(raw={...}, what="design.md", when=..., why=ABSENT)
    A factor passed as ABSENT reads as a known absence; a factor not passed at
    all reads as unknown. Constructing without `raw` is illegal.
    """

    def __init__(self, raw: Any = None, **factors: Any) -> None:
        if raw is None:
            raise ValueError(
                "a Factors shape must retain its raw source (raw=...); a shape "
                "constructed without raw makes lossy normalization representable, "
                "which is the irreversible direction this shape closes by "
                "construction."
            )
        unknown = set(factors) - set(FACTORS)
        if unknown:
            raise ValueError(
                f"unknown factor(s) {sorted(unknown)}; the six are {FACTORS}."
            )
        self._raw = raw
        # Store only factors that were spoken about. A factor absent from this
        # dict is UNKNOWN; a factor mapped to ABSENT is a known structural absence.
        self._factors: dict[str, Any] = dict(factors)

    @property
    def raw(self) -> Any:
        """The retained original source, beside the normalized factors."""
        return self._raw

    def get(self, factor: str) -> Any:
        """The factor's value, or None for both absent and unknown.

        None is deliberately ambiguous between absent and unknown here — use
        is_absent() to separate them. `get` answers "is there a value to use",
        which is None in both non-present states.
        """
        value = self._factors.get(factor)
        return None if value == ABSENT else value

    def is_absent(self, factor: str) -> bool:
        """True only when the factor is marked as a KNOWN structural absence.

        Distinguishes "this object has no `why`" (absent) from "nobody computed
        `why`" (unknown) — the honesty the degeneracy claim rests on.
        """
        return self._factors.get(factor) == ABSENT

    def is_unknown(self, factor: str) -> bool:
        """True when nobody has said anything about the factor (not yet computed)."""
        return factor not in self._factors

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        parts = []
        for f in FACTORS:
            if self.is_absent(f):
                parts.append(f"{f}=ABSENT")
            elif self.is_unknown(f):
                parts.append(f"{f}=?")
            else:
                parts.append(f"{f}={self.get(f)!r}")
        return f"Factors({', '.join(parts)})"


def from_storage_object(obj: dict) -> Factors:
    """Normalize a filesystem-shaped object into the shared factor shape.

    Storage is dense on what/when/where, thin on who, structurally ABSENT on why
    (a file has no intent) and how (no action is captured at rest — the
    execution-history provider fills `how` later, the action-edge gap). The
    point is not that storage has all six; it is that storage's MISSING factors
    are represented honestly within the SAME shape an activity object uses.
    """
    raw = obj.get("_raw", obj)
    values: dict[str, Any] = {
        # what it is
        "what": obj.get("name") or obj.get("label"),
        # when it last changed (fall back through the timestamp spine)
        "when": obj.get("modified") or obj.get("created") or obj.get("observed_at"),
        # where it lives — the uniform locator, else the path
        "where": obj.get("uri") or obj.get("path"),
        # who observed/owns it, if the source recorded one; else unknown
        "who": obj.get("source") or obj.get("owner"),
        # a file has no intent — a KNOWN structural absence, not an un-run transducer
        "why": ABSENT,
        # no action captured at rest — structurally absent until execution history
        "how": ABSENT,
    }
    # Drop keys that came back None so they read as UNKNOWN, not present-None.
    # (who with no source is unknown; what/when/where None would also be unknown,
    # but a real storage object populates them — the tests assert that.)
    present = {k: v for k, v in values.items() if v is not None}
    return Factors(raw=raw, **present)


def from_llm_memory(obj: dict) -> Factors:
    """Normalize an LLM-memory object (a turn/conclusion) into the SAME shape.

    LLM-memory is degenerate on DIFFERENT axes than storage: rich what
    (language), real when/who (timestamp + model id), thin where (a turn has no
    strong locus), why expensive/absent. Same shape, different dense region —
    which is exactly the convergence claim.
    """
    raw = obj.get("_raw", obj)
    values: dict[str, Any] = {
        "what": obj.get("text") or obj.get("content"),
        "when": obj.get("timestamp") or obj.get("created"),
        "who": obj.get("model_family") or obj.get("model"),
        # a turn's locus is thin; only populate where if the source gave one
        "where": obj.get("where") or obj.get("session"),
    }
    present = {k: v for k, v in values.items() if v is not None}
    return Factors(raw=raw, **present)
