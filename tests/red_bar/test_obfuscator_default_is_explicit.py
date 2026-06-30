"""Red bar: the storage boundary must never be turned off *silently*.

`TransparentObfuscator` is legitimate — devices run transparent (no fortress in
the path). The bypass is not transparency itself; it is transparency arriving
INVISIBLY through a bare `obfuscator or TransparentObfuscator()` default. A
silent default never shows in a diff, so a coder builds and "verifies" against a
boundary-absent system and goes green — the environment teaches the bypass.

The fix makes every transparent path EXPLICIT and greppable: `git grep
TransparentObfuscator` over src/ is then a complete, honest census of every
boundary-off site, each one a reviewed argument rather than a hidden default.

This test scans source — no DB — so it is authoritative regardless of which
obfuscator the live suite happens to wire.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"

# `obfuscator or TransparentObfuscator()` and spelling variants: the silent
# default that substitutes a boundary-absent obfuscator without a reviewer
# seeing it at the call site.
SILENT_DEFAULT = re.compile(r"\bor\s+TransparentObfuscator\s*\(")


def test_no_silent_transparent_default_in_src() -> None:
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if SILENT_DEFAULT.search(line):
                rel = path.relative_to(SRC.parent.parent)
                offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "The storage boundary is turned off by a SILENT default. Make each "
        "transparent path an explicit `TransparentObfuscator()` argument so it "
        "shows in the diff and `git grep` finds it:\n  " + "\n  ".join(offenders)
    )
