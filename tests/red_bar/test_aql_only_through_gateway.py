"""RED BAR: AQL runs only through yanantin.core.aql.run().

The gateway records what every query cost (rows returned, documents scanned
whole or by index, server time). That record is the input an indexing policy
needs; a query that goes around the gateway is a query nobody sees. Calling
`db.aql.execute(...)` directly is the obvious completion, so the next session
will write it unless the build goes red.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "yanantin"

ALLOWLIST = {"core/aql.py"}

DIRECT = re.compile(r"\.aql\s*\.\s*execute\s*\(")


def test_no_module_outside_the_gateway_executes_aql():
    offenders = sorted(
        p.relative_to(SRC).as_posix()
        for p in SRC.rglob("*.py")
        if p.relative_to(SRC).as_posix() not in ALLOWLIST
        and DIRECT.search(p.read_text(encoding="utf-8"))
    )
    assert not offenders, (
        "AQL executed outside yanantin.core.aql.run(); route it through the "
        f"gateway so its cost is observed: {offenders}"
    )


def test_the_gateway_exists_and_executes():
    gateway = SRC / "core" / "aql.py"
    assert gateway.exists() and DIRECT.search(gateway.read_text(encoding="utf-8"))
