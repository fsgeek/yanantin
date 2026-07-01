"""RED BAR: only the connection factory may import python-arango directly.

The façade roadmap's load-bearing invariant (2026-06-30): every Arango call goes
through the obfuscating façade, which is built on the ONE allowlisted raw-arango
home — infra/config.py's connection factory. Any other module reaching for
`from arango import ...` or `ArangoClient(` bypasses the obfuscation boundary,
and an LLM WILL write that bypass next session (`from arango import ArangoClient`
is the high-probability completion). Prose cannot stop it; this test can.

unimplemented-is-absent: a raw import outside the allowlist is not a style nit —
it is a hole in the boundary, and the build goes red.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "yanantin"

# The ONLY module permitted to construct a raw Arango client: the connection
# factory the façade is built on. Everything else routes through the façade,
# receiving its handle from get_database().
ALLOWLIST = {"infra/config.py"}

# The bypass is CONSTRUCTING or IMPORTING a raw client — reaching around the
# factory to open your own connection. That is the hole an LLM writes next
# session. Forbid:
#   - `import arango` / `from arango import ...`  (top-level package: pulls the client)
#   - `ArangoClient(...)`                          (constructing a client directly)
# ALLOW `from arango.database import StandardDatabase` and similar submodule TYPE
# imports: a type annotation on a handle you were HANDED cannot bypass the
# boundary — it is inert, and it is exactly the return type of the allowlisted
# factory. Forbidding it would punish correct code for naming its own handle.
RAW_ARANGO = re.compile(
    r"^\s*(?:from\s+arango\s+import\b|import\s+arango\b)|ArangoClient\s*\(",
    re.MULTILINE,
)


def _relpath(p: Path) -> str:
    return p.relative_to(SRC).as_posix()


def test_no_module_outside_the_factory_imports_raw_arango():
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        rel = _relpath(path)
        if rel in ALLOWLIST:
            continue
        if RAW_ARANGO.search(path.read_text(encoding="utf-8")):
            offenders.append(rel)

    assert not offenders, (
        "raw python-arango used outside the allowlisted connection factory "
        f"({sorted(ALLOWLIST)}); route these through the façade instead: "
        f"{sorted(offenders)}"
    )
