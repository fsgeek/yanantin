#!/usr/bin/env python3
# scripts/measure_find_quality.py
"""Find quality: substring vs BM25 over the records lane (instrument runner).

    uv run python scripts/measure_find_quality.py retrieve --run-id 2026-09-29a
    uv run python scripts/measure_find_quality.py judge    --run-id 2026-09-29a --template PATH
    uv run python scripts/measure_find_quality.py score    --run-id 2026-09-29a

retrieve reads production ``apacheta`` READ-ONLY and runs BM25 in a temporary
collection in ``apacheta_test`` that is dropped before it returns. Output goes
to results/find-quality/<run_id>/. Nothing here appends to the ledger.
Definitions live in the docstring of yanantin.eval.find_quality.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import math
import random
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from yanantin.eval import find_quality as fq

REPO = Path(__file__).resolve().parent.parent
ARM_DEFINITIONS = {
    "A0": "find() rule: case-insensitive substring over top-level string field values; "
          "hits mapped to passages; recency order (cycle desc, pid asc)",
    "A1": "same substring rule over all passages (nested values); recency order",
    "A2": "ArangoSearch BM25, text_en, over humanized path + ': ' + value, "
          "underscores -> spaces in text and query",
    "A3": "A2 without the underscore rule: raw path + ': ' + raw value, raw query",
}


def _db(name: str):
    from arango import ArangoClient

    cfg = configparser.ConfigParser()
    cfg.read(Path.home() / ".yanantin" / "config" / "db.ini")
    db = cfg["database"]
    scheme = "https" if db.get("ssl", "false") == "true" else "http"
    client = ArangoClient(hosts=f"{scheme}://{db['host']}:{db.get('port', '8529')}")
    return client.db(name, username=db["admin_user"], password=db["admin_passwd"])


def _write_jsonl(path: Path, rows) -> None:
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l]


def retrieve(out: Path) -> dict:
    if (out / "manifest.json").exists():
        raise SystemExit(f"{out} already has a manifest; pick a new run_id")
    observed_at = datetime.now(UTC).isoformat()
    # Read-only: a single AQL read of the records lane, nothing written.
    records = list(_db("apacheta").aql.execute("FOR r IN records RETURN r"))
    queries = fq.extract_queries(records)
    passages = fq.build_passages(records)

    retrieval = []
    for q in queries:
        for arm, ranked in (("A0", fq.arm_a0(records, passages, q["query"])),
                            ("A1", fq.arm_a1(passages, q["query"]))):
            retrieval.append({"qid": q["qid"], "arm": arm, "total": len(ranked),
                              "top": ranked[: fq.K], "scores": None})
    bm25 = fq.run_bm25(_db("apacheta_test"), passages, queries)
    for arm in ("A2", "A3"):
        for q in queries:
            r = bm25[arm][q["qid"]]
            retrieval.append({"qid": q["qid"], "arm": arm, **r})

    out.mkdir(parents=True, exist_ok=True)
    _write_jsonl(out / "queries.jsonl", queries)
    _write_jsonl(out / "passages.jsonl", passages.values())
    _write_jsonl(out / "retrieval.jsonl", retrieval)
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    manifest = {
        "run_id": out.name,
        "observed_at": observed_at,
        "corpus": "apacheta.records",
        "corpus_sha256": fq.corpus_sha256(records),
        "git_head": head,
        "k": fq.K,
        "counts": {
            "records": len(records),
            "sessions": len({fq.session_of(r) for r in records}),
            "search_memory_calls": sum(q["occurrences"] for q in queries),
            "queries": len(queries),
            "queries_empty_reason": sum(1 for q in queries if not q["reason"]),
            "passages": len(passages),
            "zero_result": {
                arm: sum(1 for r in retrieval if r["arm"] == arm and r["total"] == 0)
                for arm in ARM_DEFINITIONS
            },
        },
        "arms": ARM_DEFINITIONS,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def judge(out: Path, template_path: Path, model: str, seed: str) -> dict:
    template = template_path.read_text()
    queries = {q["qid"]: q for q in _read_jsonl(out / "queries.jsonl")}
    passages = {p["pid"]: p for p in _read_jsonl(out / "passages.jsonl")}
    pooled = {q: p for q, p in fq.pool(_read_jsonl(out / "retrieval.jsonl")).items() if p}
    cache = out / "judge-cache"

    def run(qid: str, bypass: bool) -> list[dict]:
        q = queries[qid]
        items = [{"pid": p, "path": passages[p]["path"], "text": passages[p]["value"]}
                 for p in pooled[qid]]
        labels = fq.judge_query(q["query"], q["reason"], items, template, model,
                                cache_dir=cache, bypass_cache=bypass)
        return [{"qid": qid, "pid": p, "relevant": v} for p, v in sorted(labels.items())]

    qids = sorted(pooled)
    with ThreadPoolExecutor(max_workers=6) as ex:
        judgments = [r for rows in ex.map(lambda q: run(q, False), qids) for r in rows]
    _write_jsonl(out / "judgments.jsonl", judgments)

    sample = sorted(random.Random(seed).sample(qids, math.ceil(0.1 * len(qids))))
    with ThreadPoolExecutor(max_workers=6) as ex:
        rejudge = [r for rows in ex.map(lambda q: run(q, True), sample) for r in rows]
    _write_jsonl(out / "rejudge.jsonl", rejudge)
    info = {"model": model, "template": str(template_path),
            "template_sha256": hashlib.sha256(template.encode()).hexdigest(),
            "judged_queries": len(qids), "judged_labels": len(judgments),
            "rejudge_seed": seed, "rejudged_queries": sample}
    (out / "judge.json").write_text(json.dumps(info, indent=2) + "\n")
    return info


def score(out: Path) -> dict:
    rejudge_path = out / "rejudge.jsonl"
    result = fq.score(
        _read_jsonl(out / "queries.jsonl"),
        _read_jsonl(out / "retrieval.jsonl"),
        _read_jsonl(out / "judgments.jsonl"),
        _read_jsonl(rejudge_path) if rejudge_path.exists() else [],
    )
    (out / "scores.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=["retrieve", "judge", "score"])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--template", type=Path, help="judge prompt template (judge stage)")
    ap.add_argument("--model", default="gpt-6-astra")
    ap.add_argument("--seed", help="rejudge sample seed (default: run id)")
    a = ap.parse_args()
    out = REPO / "results" / "find-quality" / a.run_id
    if a.stage == "retrieve":
        res = retrieve(out)
    elif a.stage == "judge":
        if not a.template:
            ap.error("judge needs --template")
        res = judge(out, a.template, a.model, a.seed or a.run_id)
    else:
        res = score(out)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
