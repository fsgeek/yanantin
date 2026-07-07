"""Falsification: the recall-vs-index fold on the REAL Claude Code archive.

Spec 2026-07-06 §1 ("Episodic recall, not an index") and §5.5 (faceted
episodic recall). The integration thesis: content-find PROPOSES a result set
(llm-memory's role — high recall), facet discrimination DISPOSES it
(qhaway-done-right's role — the scarce precision). yanantin.llika.discriminate
is the already-built precision half; this test proves the two halves meet on
real ground truth before any collector/recorder tree is built.

Ground truth: ~/.yanantin/archive/claude-projects/ (778 real transcript
files, snapshotted 2026-07-06). Guarded on corpus existence and skip-narrow
when absent (the non-portable-live-test lesson) — but the synthetic path is
NOT the one skipped; there is no synthetic here, the real corpus is the point.

The two halves are asserted SEPARATELY: a red test names whether RETRIEVAL
found nothing (recall half broke) or DISCRIMINATION found no cut (precision
half broke / thesis falsified). Compound failure is disqualified by
construction, per the bound goal.

AYLLU axes: the facet fields projected are the ones a sibling (Hamut'ay)
recall would also need — project, model, git_branch, is_sidechain, session —
coarse navigation axes, NOT per-line-unique fields (uuid/timestamp) which
would score max entropy while being useless as a recall question.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yanantin.llika import discriminate

ARCHIVE = Path.home() / ".yanantin" / "archive" / "claude-projects"

# The content term to match. A word that recurs across many sessions/projects
# so the result set is genuinely too big and spans several facet values.
MATCH_TERM = "test"

# "Too big" floor: below this the precision problem is unreal for this term.
TOO_BIG = 50

# Facet axes a sibling recall would share. Coarse, askable, NOT per-line-unique.
AYLLU_FACET_FIELDS = ("project", "model", "git_branch", "is_sidechain", "session")

pytestmark = pytest.mark.skipif(
    not ARCHIVE.is_dir() or not any(ARCHIVE.rglob("*.jsonl")),
    reason=f"real archive corpus absent at {ARCHIVE}; live-only fold test",
)


def _text_of(event: dict) -> str:
    """Flatten an event's message content to searchable text. tool_use/result
    blocks and plain strings alike; observation is total — unknown shapes
    contribute their json so nothing silently drops out of the match."""
    msg = event.get("message")
    if not isinstance(msg, dict):
        return json.dumps(event.get("attachment", "")) if "attachment" in event else ""
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text") or json.dumps(block))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return ""


def _project_record(event: dict) -> dict:
    """Project a raw transcript event to a facet record carrying ONLY the
    ayllu axes. Per-line-unique fields (uuid, timestamp) are deliberately
    excluded — they trivially max entropy and are useless as recall questions."""
    msg = event.get("message")
    model = msg.get("model") if isinstance(msg, dict) else None
    cwd = event.get("cwd") or ""
    project = cwd.rsplit("/", 1)[-1] if cwd else None
    return {
        "project": project,
        "model": model,
        "git_branch": event.get("gitBranch"),
        "is_sidechain": event.get("isSidechain"),
        "session": event.get("sessionId"),
    }


def _load_matching_events() -> list[dict]:
    """The RETRIEVAL half: content-find over the real archive. Every event
    whose flattened text contains MATCH_TERM. This is llm-memory's role at
    its simplest honest form — a content match over real text, no index yet."""
    matched = []
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
                continue  # observed-but-unparseable; not a content match
            if MATCH_TERM.lower() in _text_of(event).lower():
                matched.append(event)
    return matched


def test_recall_vs_index_fold(capsys):
    # --- Receipt 1: RETRIEVAL half — content-find produces a too-big set ---
    events = _load_matching_events()
    n_matched = len(events)
    assert n_matched >= TOO_BIG, (
        f"RETRIEVAL half: content match on '{MATCH_TERM}' returned "
        f"{n_matched} events (< {TOO_BIG}); precision problem is unreal for "
        f"this term — the thesis is uninteresting, not falsified. Pick a "
        f"more common term."
    )

    records = [_project_record(e) for e in events]

    # --- Receipt 2: DISCRIMINATION half — discriminate() disposes it ---
    disc = discriminate(records, facet_fields=AYLLU_FACET_FIELDS)
    best = disc.best
    assert best is not None, (
        "DISCRIMINATION half FALSIFIED on real data: no ayllu facet splits "
        f"the {n_matched}-event recall (every facet dominated by one value). "
        "The recall-vs-index thesis fails on real transcripts."
    )
    assert best.entropy >= 0.5 and best.distinct > 1

    # --- Receipt 3: the cut is REAL, not decorative ---
    lead_value = best.top[0][0]
    narrowed = [r for r in records if str(r.get(best.name)) == lead_value]
    n_narrowed = len(narrowed)
    assert 0 < n_narrowed < n_matched, (
        f"cut not real: narrowing on {best.name}={lead_value} left "
        f"{n_narrowed} of {n_matched} (must be strictly smaller and non-empty)"
    )

    # --- Finding: normalized entropy alone ranks a BOOLEAN first. ---
    # A 2-value even split scores as high as a 20-value even split (the score
    # is normalized by log2(distinct)). is_sidechain evenly splits 17k into
    # 11k/6.6k — a "perfect" discriminator that barely narrows. The
    # recall-USEFUL cut is the high-cardinality one (session). Surface the
    # best HIGH-CARDINALITY discriminator too, and show it cuts far harder.
    high_card = next(
        (f for f in disc.facets if f.discriminating and f.distinct > 2), None
    )
    assert high_card is not None, (
        "no high-cardinality discriminator — only boolean splits available"
    )
    hc_value = high_card.top[0][0]
    hc_narrowed = sum(1 for r in records if str(r.get(high_card.name)) == hc_value)
    # The scarce-precision claim: the high-cardinality cut narrows HARDER than
    # the boolean the score ranked first. This is the finding, asserted.
    assert hc_narrowed < n_narrowed, (
        f"high-cardinality facet {high_card.name} did not out-narrow the "
        f"boolean {best.name} ({hc_narrowed} vs {n_narrowed})"
    )

    with capsys.disabled():
        print(
            f"\n[FOLD — recall vs index, real archive]\n"
            f"  RETRIEVAL: '{MATCH_TERM}' matched {n_matched} events "
            f"(too-big floor {TOO_BIG}) — narrowing needed.\n"
            f"  DISPOSE:   best facet = '{best.name}'  "
            f"entropy={best.entropy:.3f}  distinct={best.distinct}\n"
            f"             top: {best.top}\n"
            f"  CUT:       narrow on {best.name}='{lead_value}' → "
            f"{n_narrowed} of {n_matched} "
            f"({n_narrowed / n_matched:.1%} of the set)\n"
            f"  FINDING:   entropy ranks a BOOLEAN first; the recall-useful cut\n"
            f"             is high-cardinality '{high_card.name}' "
            f"(entropy={high_card.entropy:.3f}, distinct={high_card.distinct}):\n"
            f"             narrow on {high_card.name}='{hc_value[:16]}…' → "
            f"{hc_narrowed} of {n_matched} "
            f"({hc_narrowed / n_matched:.2%} — cuts {n_narrowed // hc_narrowed}× harder)\n"
            f"  AYLLU axes available to discriminate(): {AYLLU_FACET_FIELDS}\n"
            f"  ranked: "
            + ", ".join(f"{f.name}={f.entropy:.2f}" for f in disc.facets)
        )
