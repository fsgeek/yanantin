#!/usr/bin/env python3
"""Substrate progress dashboard: two grounded metrics, read live.

Tracks the two numbers that matter for the storage-spine build (the
2026-06-20 forward plan) without depending on any not-yet-built module:

1. RED-BAR PROGRESS — how many of the architectural-gap tests in
   tests/red_bar/ are still red. This is BUILD progress toward the spine
   (factors / resolver / StorageObject / Llika wall). Source: pytest.

2. THE MIRROR TEST — the substrate's blindness-to-its-own-construction.
   Searches the live llm_memory BM25 view for the vocabulary of the
   substrate-building work itself. A program building a memory substrate
   that cannot find its own construction history is store-without-find
   looking in the mirror (project_federation_runs_today_and_i_was_the_
   uningested_episode). This is RESEARCH progress: the 0 -> N proof.
   Source: live ArangoDB (llm_memory.episodes_search).

Both metrics are read-only. Nothing here writes to the store or touches
src/. Re-run any time to watch the numbers move as providers land.

Usage:
    uv run python tools/dashboard.py            # both metrics
    uv run python tools/dashboard.py --json      # machine-readable
    uv run python tools/dashboard.py --no-db     # skip the live mirror test
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Vocabulary of the substrate-BUILDING work. These terms describe the
# construction history (gholas designing the spine), NOT the taste
# experiment that currently populates llm_memory. A hit means a session
# about building the substrate has been ingested INTO the substrate.
#
# DIAGNOSTIC terms are near-unambiguous: a hit really is our construction
# history. AMBIGUOUS terms (resolver, factor shape) collide with generic
# usage in the existing corpus, so they're shown but EXCLUDED from the
# verdict — a hit on them is not proof. CONTROL terms are known-present in
# the taste corpus and prove only that the view works.
DIAGNOSTIC_TERMS = ["ghola", "Pour A", "storage object", "federation", "dogfood", "curiosity"]
AMBIGUOUS_TERMS = ["resolver", "factor shape"]
CONTROL_TERMS = ["memory", "find", "yanantin"]
MIRROR_TERMS = DIAGNOSTIC_TERMS + AMBIGUOUS_TERMS + CONTROL_TERMS


@dataclass
class RedBarStatus:
    total: int
    red: int
    green: int
    failures: list[str] = field(default_factory=list)

    @property
    def pct_green(self) -> float:
        return 100.0 * self.green / self.total if self.total else 0.0


@dataclass
class MirrorHit:
    term: str
    count: int


@dataclass
class MirrorStatus:
    episodes: int
    hits: list[MirrorHit] = field(default_factory=list)
    error: str | None = None

    @property
    def construction_terms_found(self) -> int:
        """Distinct DIAGNOSTIC terms with at least one hit.

        Only the near-unambiguous terms count toward the verdict. Ambiguous
        and control terms are reported but excluded — a hit on them is not
        proof the substrate's own construction history was ingested.
        """
        diag = set(DIAGNOSTIC_TERMS)
        return sum(1 for h in self.hits if h.term in diag and h.count > 0)


def measure_red_bars() -> RedBarStatus:
    """Run tests/red_bar/ and count red vs green. Source of build truth."""
    proc = subprocess.run(
        ["uv", "run", "pytest", "tests/red_bar/", "-q", "--no-header"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout
    failures = [
        line.split(" ")[1]
        for line in out.splitlines()
        if line.startswith("FAILED ")
    ]
    # Last summary line, e.g. "13 failed, 120 passed, 1 warning in 1.28s"
    import re

    red = green = 0
    for line in reversed(out.splitlines()):
        if " passed" in line or " failed" in line:
            m_red = re.search(r"(\d+) failed", line)
            m_green = re.search(r"(\d+) (passed|xpassed)", line)
            red = int(m_red.group(1)) if m_red else 0
            green = int(m_green.group(1)) if m_green else 0
            break
    return RedBarStatus(total=red + green, red=red, green=green, failures=failures)


def measure_mirror() -> MirrorStatus:
    """Search the live llm_memory BM25 view for construction vocabulary.

    Read-only, admin-tier (llm_memory is a different DB than the app default).
    """
    try:
        from yanantin.infra.config import ApachetaDBConfig, get_database
    except Exception as exc:  # import guarded: dashboard must run without full env
        return MirrorStatus(episodes=0, error=f"import: {exc}")

    try:
        cfg = ApachetaDBConfig()
        admin = cfg.get_admin_credentials()
        db = get_database(
            db_name="llm_memory",
            username=admin["username"],
            password=admin["password"],
        )
        episodes = db.collection("episodes").count()
        hits: list[MirrorHit] = []
        query = """
            FOR e IN episodes_search
              SEARCH ANALYZER(
                PHRASE(e.response, @t) OR
                PHRASE(e.state_text, @t) OR
                PHRASE(e.user_message, @t), 'text_en')
              COLLECT WITH COUNT INTO n RETURN n
        """
        for term in MIRROR_TERMS:
            cur = db.aql.execute(query, bind_vars={"t": term})
            hits.append(MirrorHit(term=term, count=list(cur)[0]))
        return MirrorStatus(episodes=episodes, hits=hits)
    except Exception as exc:
        return MirrorStatus(episodes=0, error=f"db: {exc}")


def render(red: RedBarStatus, mirror: MirrorStatus | None) -> str:
    lines: list[str] = []
    lines.append("=" * 56)
    lines.append("  YANANTIN SUBSTRATE PROGRESS")
    lines.append("=" * 56)
    lines.append("")
    lines.append("BUILD  — red-bar progress (the spine)")
    bar_w = 40
    filled = round(bar_w * red.green / red.total) if red.total else 0
    lines.append(f"  [{'#' * filled}{'.' * (bar_w - filled)}]  {red.pct_green:.0f}%")
    lines.append(f"  {red.green}/{red.total} green, {red.red} architectural gaps remain")
    if red.failures:
        lines.append("  still red:")
        for f in red.failures:
            short = f.split("::")[-1]
            lines.append(f"    - {short}")
    lines.append("")

    if mirror is not None:
        lines.append("RESEARCH — the mirror test (blindness to self)")
        if mirror.error:
            lines.append(f"  (db unavailable: {mirror.error})")
        else:
            lines.append(f"  llm_memory: {mirror.episodes} episodes, BM25 view live")
            by_term = {h.term: h.count for h in mirror.hits}
            lines.append("  diagnostic vocabulary (the 0->N proof):")
            for term in DIAGNOSTIC_TERMS:
                count = by_term.get(term, 0)
                mark = "found " if count else "BLIND "
                lines.append(f"    [{mark}] {term:18} {count}")
            found = mirror.construction_terms_found
            lines.append(
                f"  -> {found}/{len(DIAGNOSTIC_TERMS)} diagnostic terms findable"
                + ("  (substrate sees its own build)" if found else "  (substrate is blind to its own build)")
            )
            lines.append("  ambiguous (shown, not counted — collide with generic usage):")
            for term in AMBIGUOUS_TERMS:
                lines.append(f"    {term:18} {by_term.get(term, 0)}")
            lines.append("  control (corpus already present — proves the view works):")
            for term in CONTROL_TERMS:
                lines.append(f"    {term:18} {by_term.get(term, 0)}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--no-db", action="store_true", help="skip the live mirror test")
    args = ap.parse_args()

    red = measure_red_bars()
    mirror = None if args.no_db else measure_mirror()

    if args.json:
        payload = {"red_bars": asdict(red)}
        if mirror is not None:
            payload["mirror"] = asdict(mirror)
            payload["mirror"]["construction_terms_found"] = mirror.construction_terms_found
        print(json.dumps(payload, indent=2))
    else:
        print(render(red, mirror))
    return 0


if __name__ == "__main__":
    sys.exit(main())
