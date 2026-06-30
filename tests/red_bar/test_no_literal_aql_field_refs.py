"""Red bar (Phase 1 of the AQL field-mapping guardrail; see
docs/design-aql-field-mapping-guardrail.md): no AQL query may interpolate a
field name that was mapped with `field_name(...)` directly into a `doc.<field>`
text position.

WHY this exact shape, and not "no `doc.{...}` interpolation at all":
The disciplined sites (Regime 1) ALSO interpolate a variable into `doc.{...}` —
but that variable comes from `field_path((...))`, which is the sanctioned
primitive. Flagging all interpolation would indict the very pattern we want
callers to converge on. And `field_name` has a LEGITIMATE non-query use:
obfuscating a document's keys on the write path (`mapped_doc[field_name(k)] = v`),
which is never interpolated into query text and must NOT be flagged (design §3.2).

So the forbidden signature is provenance-based and separable without an AST
parser: a local variable assigned from `.field_name(` that is then interpolated
into a `(doc|d|e|v).{var}` field position inside a string. That is exactly
Regime 2 (the leaky f-string sites) and nothing else.

BORN RED on purpose: the Regime-2 sites in activity/backends/arango.py violate
this today. It runs in the informational (non-blocking) red_bar lane until
Phase 2 migrates those sites; then it goes green and moves to the blocking gate.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
OBFUSCATOR_MODULE = "storage_obfuscator.py"  # the primitive's own home — exempt

# A local var assigned from `<something>.field_name(` — the unsanctioned mapping.
_ASSIGNED_FROM_FIELD_NAME = re.compile(r"\b([A-Za-z_]\w*)\s*=\s*[^=\n]*\.field_name\(")
# A `(doc|d|e|v).{var}` interpolation into an f-string field position.
_FIELD_INTERP = re.compile(r"\b(?:doc|d|e|v)\.\{([A-Za-z_]\w*)\}")


def _violations_in(path: Path) -> list[str]:
    text = path.read_text()
    lines = text.splitlines()

    # vars in this file assigned from field_name(...)
    field_name_vars = set(_ASSIGNED_FROM_FIELD_NAME.findall(text))
    if not field_name_vars:
        return []

    out: list[str] = []
    for lineno, line in enumerate(lines, start=1):
        for var in _FIELD_INTERP.findall(line):
            if var in field_name_vars:
                rel = path.relative_to(SRC.parent.parent)
                out.append(f"{rel}:{lineno}: {line.strip()}")
    return out


def test_no_field_name_var_interpolated_into_aql() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        if path.name == OBFUSCATOR_MODULE:
            continue
        offenders.extend(_violations_in(path))

    assert not offenders, (
        "A field mapped with field_name(...) is interpolated directly into an "
        "AQL `doc.<field>` position. Use field_path((...)) — the sanctioned "
        "primitive — and bind it, so the mapping is structural and greppable "
        "(design §3, §5). Offending sites:\n  " + "\n  ".join(offenders)
    )
