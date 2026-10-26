"""M1 (abandonment) and M2 (cost to find) over khipumaq's raw history.

Pre-registered in predictions/2026-10-26-finding-metrics-claude.md (97cbe9f7),
before this script existed. M3 (adjudicating abandoned chains) is a separate step.

Usage (reads khipumaq's store through its own config):
    uv run --with-editable ../khipumaq python scripts/measure_finding_chains.py [--no-ledger]
Writes results/finding-metrics/<VERSION>/{chains.jsonl,summary.json}; appends the
summary quantities to ledger/observations.jsonl unless --no-ledger.
"""

from __future__ import annotations

import hashlib
import json
import random
import statistics
import sys
from collections import defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from khipumaq.db import get_database

from yanantin.eval.finding_chains import chains_from_claude, chains_from_codex, dedupe
from yanantin.eval.ledger import append

VERSION = "2026-10-26a"
PREDICTIONS = "predictions/2026-10-26-finding-metrics-claude.md"
SEED, RESAMPLES = 20261026, 10_000
WINDOWS = (("V1", "2026-06-19", "2026-09-03"), ("V2", "2026-09-03", "2026-09-29"), ("V3", "2026-09-29", "9999"))
DEV_LABELS = {"khipumaq", "llm-memory", "llm_memory"}
OUT = Path("results/finding-metrics") / VERSION

CANDIDATES = """
FOR r IN raw
  FILTER r.kind IN ['claude', 'codex'] AND HAS(r, 'text')
  FILTER CONTAINS(r.text, '__search"') OR CONTAINS(r.text, '"tool":"search') OR
         (CONTAINS(r.text, '.jsonl') AND (CONTAINS(r.text, 'grep') OR CONTAINS(r.text, 'rg ') OR CONTAINS(r.text, '"Grep"'))) OR
         (CONTAINS(r.text, '.claude/projects') AND (CONTAINS(r.text, 'grep') OR CONTAINS(r.text, 'rg ') OR CONTAINS(r.text, '"Grep"')))
  COLLECT host = r.host, source = r.source_file, kind = r.kind
  RETURN {host, source, kind}
"""
# One scan for every candidate file's lines (raw has no source_file index; a query
# per file would scan it once per file).
LINES = """FOR r IN raw FILTER CONCAT(r.host, '|', r.source_file) IN @files
  RETURN [r.host, r.source_file, r.line, r.text]"""
LABELS = """FOR e IN episodes FILTER e.source_file IN @sources
  COLLECT source = e.source_file AGGREGATE label = MAX(e.experiment_label) RETURN [source, label]"""


def session_of(source: str) -> str:
    """Subagent files belong to their parent session: resample sessions, not files."""
    p = Path(source)
    return p.parent.parent.name if p.parent.name == "subagents" else p.stem


def window(c) -> str:
    if c.arm == "grep":
        return "grep"
    day = c.first_ts.date().isoformat() if c.first_ts else ""
    return next((w for w, lo, hi in WINDOWS if lo <= day < hi), "pre-V1")


def boot(rows: list[dict], stat, rng: random.Random) -> tuple[float | None, float | None, float | None]:
    """stat over rows, with a 95% interval from resampling sessions."""
    by_session: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_session[r["session"]].append(r)
    groups = list(by_session.values())
    point = stat(rows)
    if point is None or len(groups) < 2:
        return point, None, None
    draws = []
    for _ in range(RESAMPLES):
        sample = [r for g in rng.choices(groups, k=len(groups)) for r in g]
        v = stat(sample)
        if v is not None:
            draws.append(v)
    draws.sort()
    return point, draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1]


def abandonment(rows):
    return sum(not r["found"] for r in rows) / len(rows) if rows else None


def median_of(field):
    def stat(rows):
        vals = [r[field] for r in rows if r["found"] and r[field] is not None]
        return statistics.median(vals) if vals else None
    return stat


def summarize(rows: list[dict], rng: random.Random) -> dict:
    out = {}
    for name in sorted({r["window"] for r in rows}):
        sub = [r for r in rows if r["window"] == name]
        out[name] = {
            "chains": len(sub),
            "sessions": len({r["session"] for r in sub}),
            "found": sum(r["found"] for r in sub),
            "unlinked_recalls": sum(r["unlinked_recalls"] for r in sub),
            "M1_abandonment": boot(sub, abandonment, rng),
            "M2a_median_seconds": boot(sub, median_of("seconds_to_found"), rng),
            "M2b_median_searches": boot(sub, median_of("searches_before_found"), rng),
            "M2c_median_result_chars": boot(sub, median_of("result_chars_to_found"), rng),
        }
    tool = [r for r in rows if r["window"] in ("V1", "V2", "V3")]
    if tool:
        out["tool_all"] = {"chains": len(tool), "M1_abandonment": boot(tool, abandonment, rng)}
    v1 = [r for r in rows if r["window"] == "V1"]
    v3 = [r for r in rows if r["window"] == "V3"]
    if v1 and v3:
        both = v1 + v3

        def diff(rs):
            a = [r for r in rs if r["window"] == "V1"]
            b = [r for r in rs if r["window"] == "V3"]
            return abandonment(a) - abandonment(b) if a and b else None
        out["V1_minus_V3_M1"] = boot(both, diff, rng)
    return out


def main() -> None:
    ledger = "--no-ledger" not in sys.argv
    db = get_database()
    raw_lines = db.collection("raw").count()
    files = {(f["host"], f["source"]): f["kind"] for f in db.aql.execute(CANDIDATES, stream=True)}
    texts: dict[tuple, list[tuple[int, str]]] = {}
    for host, source, n, text in db.aql.execute(
            LINES, bind_vars={"files": [f"{h}|{s}" for h, s in files]}, stream=True, batch_size=5000):
        if text:
            texts.setdefault((host, source), []).append((n, text))
    chains = []
    for (host, source), numbered in texts.items():
        build = chains_from_claude if files[(host, source)] == "claude" else chains_from_codex
        chains.extend((c, source) for c in build(t for _, t in sorted(numbered)))
    labels = dict(db.aql.execute(LABELS, bind_vars={"sources": sorted({s for _, s in files})}))

    source_of = {(c.arm, c.first_call_id): s for c, s in chains}
    rows = []
    for c in dedupe(c for c, _ in chains):
        src = source_of[(c.arm, c.first_call_id)]
        d = {k: v for k, v in asdict(c).items() if not k.startswith("_")}
        d.update(first_ts=c.first_ts.isoformat() if c.first_ts else None, source=src,
                 session=session_of(src), label=labels.get(src), window=window(c))
        rows.append(d)
    rows.sort(key=lambda r: (r["first_ts"] or "", r["first_call_id"]))

    OUT.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
    (OUT / "chains.jsonl").write_text(body)
    rng = random.Random(SEED)
    summary = {
        "primary": summarize(rows, rng),
        "sensitivity_no_dev_sessions": summarize([r for r in rows if r["label"] not in DEV_LABELS], rng),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps(summary, indent=1))

    if ledger:
        instrument = {
            "name": "finding-chains", "version": VERSION, "predictions": PREDICTIONS,
            "scripts": ["scripts/measure_finding_chains.py", "src/yanantin/eval/finding_chains.py"],
            "method": "search chains between human turns in khipumaq raw; found = recall of a returned key "
                      "(tool) or read of a grep-matched session file (grep); session bootstrap",
            "known_limits": "snippet-answered searches count as abandoned until M3; raw covers files on disk "
                            "at sweeps since 2026-09-30; grep arm's found signal is weaker; chars proxy tokens",
        }
        population = {"raw_lines": raw_lines, "chains": len(rows),
                      "chains_sha256": hashlib.sha256(body.encode()).hexdigest()}
        now = datetime.now(UTC).isoformat()
        for quantity, value in summary.items():
            append({"observed_at": now, "instrument": instrument, "population": population,
                    "quantity": f"m1_m2_by_window_{quantity}", "value": value})


if __name__ == "__main__":
    main()
