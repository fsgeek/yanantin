"""Falsification: best_for_recall() picks the hard-narrowing facet on the
REAL Claude Code archive — the recall-oriented selector the entropy-only
ranking under-serves. Spec 2026-07-06 §5.5; bound goal 2026-07-07 #3.

Finding that motivates this (test_recall_vs_index_fold.py): normalized entropy
ranks a BOOLEAN (is_sidechain, distinct=2) above the high-cardinality axis
(session, distinct=101) that actually narrows a 17,768-event recall 7x harder.
best_for_recall() is the thin, GENERIC selector that fixes the ranking for
recall WITHOUT touching the cardinality-neutral primitive discriminate().

Ground truth: the real 778-file archive. Guarded, skip-narrow when absent
(non-portable-live-test lesson); the real corpus IS the point here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yanantin.llika import best_for_recall, discriminate

ARCHIVE = Path.home() / ".yanantin" / "archive" / "claude-projects"
MATCH_TERM = "test"
AYLLU_FACET_FIELDS = ("project", "model", "git_branch", "is_sidechain", "session")

pytestmark = pytest.mark.skipif(
    not ARCHIVE.is_dir() or not any(ARCHIVE.rglob("*.jsonl")),
    reason=f"real archive corpus absent at {ARCHIVE}; live-only selector test",
)


def _text_of(event: dict) -> str:
    msg = event.get("message")
    if not isinstance(msg, dict):
        return json.dumps(event.get("attachment", "")) if "attachment" in event else ""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            parts.append(block.get("text") or json.dumps(block) if isinstance(block, dict) else str(block))
        return "\n".join(parts)
    return ""


def _project_record(event: dict) -> dict:
    msg = event.get("message")
    model = msg.get("model") if isinstance(msg, dict) else None
    cwd = event.get("cwd") or ""
    return {
        "project": cwd.rsplit("/", 1)[-1] if cwd else None,
        "model": model,
        "git_branch": event.get("gitBranch"),
        "is_sidechain": event.get("isSidechain"),
        "session": event.get("sessionId"),
    }


def _archive_records() -> list[dict]:
    records = []
    for fp in ARCHIVE.rglob("*.jsonl"):
        try:
            lines = fp.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if MATCH_TERM.lower() in _text_of(event).lower():
                records.append(_project_record(event))
    return records


def _cut_fraction(records, facet) -> float:
    lead = facet.top[0][0]
    n = sum(1 for r in records if str(r.get(facet.name)) == lead)
    return n / len(records)


def test_best_for_recall_picks_hard_narrowing_facet(capsys):
    records = _archive_records()
    assert len(records) >= 50, "recall set too small — pick a more common term"

    disc = discriminate(records, facet_fields=AYLLU_FACET_FIELDS)

    entropy_best = disc.best                 # what plain entropy picks
    recall_best = best_for_recall(disc)      # what recall SHOULD pick

    assert recall_best is not None, "no discriminating facet for recall"

    # The claim: recall's pick narrows STRICTLY harder than entropy's pick.
    entropy_cut = _cut_fraction(records, entropy_best)
    recall_cut = _cut_fraction(records, recall_best)
    assert recall_cut < entropy_cut, (
        f"recall selector did not out-narrow entropy: "
        f"{recall_best.name} cut {recall_cut:.2%} vs "
        f"{entropy_best.name} cut {entropy_cut:.2%}"
    )
    # And specifically: it prefers higher cardinality when both discriminate.
    assert recall_best.distinct > entropy_best.distinct

    with capsys.disabled():
        print(
            f"\n[best_for_recall — real archive, {len(records)} events]\n"
            f"  entropy .best : {entropy_best.name} "
            f"(distinct={entropy_best.distinct}) cuts to {entropy_cut:.2%}\n"
            f"  best_for_recall: {recall_best.name} "
            f"(distinct={recall_best.distinct}) cuts to {recall_cut:.2%}\n"
            f"  recall narrows {entropy_cut / recall_cut:.1f}x harder"
        )
