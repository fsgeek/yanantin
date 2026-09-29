"""Find quality: substring vs BM25 over the apacheta ``records`` lane.

Implements the pre-registered intent (predictions/, not read by the builder).
Every arm returns *passages*; every judgment is about a passage.

Unit
----
A passage is one unique ``(session, field path, string value)`` leaf.
``session`` = ``provenance.author_instance_id``. The path is dotted, list
indices included (``what_i_carry.0.claim``). Excluded: any key starting with
``_`` (at any depth), top-level ``provenance`` and ``lineage_tags``, and every
non-string leaf. ``pid`` = first 16 hex of
``sha256(session + '\\x00' + path + '\\x00' + value)``.

A passage belongs to the first record in its session that introduced it.
Records in a session are ordered by (cycle ascending, provenance.timestamp,
_key); a record's cycle is its ``cycle-N`` lineage tag. Records with no such
tag (two in the corpus at build time, each alone in its session) sort after
the cycled ones and are ordered by ``provenance.timestamp``.

Queries
-------
Every ``_activity_log`` entry with ``tool == "search_memory"`` and a string
``parameters.query``. De-duplicated by (session, query), keeping the earliest
by the entry's own timestamp; its ``reason`` is kept (``None`` becomes ``""``)
together with the original scope/limit/narrow_by. The search then runs over
the whole corpus regardless of the original scope. ``qid`` = first 16 hex of
``sha256(session + '\\x00' + query)``.

Arms (all return the full ranked pid list; retrieval keeps total + top 10)
----
* A0 -- today's ``ApachetaArango.find()`` rule: case-insensitive substring of
  the query in the *value* of a top-level, non-``_``, string field of a
  record. Each matching (record, field) maps to its passage pid; pids are
  de-duplicated (``find()`` counts records, A0 counts passages).
* A1 -- the same substring rule over every passage (nested included). This is
  hamutay's ``search_memory`` reach: ``_value_contains`` recurses into dict
  VALUES and list items, never keys. It also str()-matches non-string leaves;
  A1 does not, because non-strings are not passages under the unit.
* Recency order for A0/A1: the passage's (introducing record's) cycle
  descending, tie-break pid ascending. Passages from cycle-less records sort
  after all cycled ones, by provenance.timestamp descending, then pid.
* A2 -- ArangoSearch BM25, analyzer ``text_en``, over
  ``humanize(path) + ': ' + value.replace('_', ' ')`` where ``humanize``
  turns ``_`` and ``.`` into spaces; the query has ``_`` -> space.
* A3 -- the same over ``path + ': ' + value`` with the raw query.
* BM25 ties are broken by pid ascending. A query whose tokens are empty
  matches nothing (zero-result).

Judge
-----
``judge_query`` renders the template by literal replacement of ``{query}``,
``{reason}`` and ``{passages}`` (not ``str.format``, so braces elsewhere in the
template are safe). An empty reason renders as the empty string. Passage
``text`` is the raw value, capped at 2000 chars plus a truncation marker.
Order is deterministic: sort by ``sha256(query + pid)``. Results are cached
at ``<cache_dir>/<sha256(prompt)>.json``; ``bypass_cache=True`` re-runs the
byte-identical prompt without reading or writing the cache.

Metrics (k = 10), see ``score``
-------
* zero_result_rate: queries with total == 0 / all queries.
* success_at_10: queries with >= 1 relevant in the top 10 / all queries.
* precision_at_10: mean over queries with total > 0 of
  relevant_in_top10 / min(10, total).
* pooled_recall: macro mean over queries with >= 1 relevant pooled passage of
  (relevant in this arm's top 10) / (relevant in the pool).
* mrr (A2, A3 only): mean over all queries of 1/rank of the first relevant
  passage in the top 10, 0 if none.
* judge flip rate: rejudged (qid, pid) labels that differ from the first
  judgment / rejudged labels.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

K = 10
EXCLUDED_TOP = ("provenance", "lineage_tags")
TEXT_CAP = 2000
_CYCLE_TAG = re.compile(r"^cycle-(\d+)$")

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "judgments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pid": {"type": "string"},
                    "relevant": {"type": "integer", "enum": [0, 1]},
                },
                "required": ["pid", "relevant"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["judgments"],
    "additionalProperties": False,
}


def _h16(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:16]


def passage_id(session: str, path: str, value: str) -> str:
    return _h16(session, path, value)


def query_id(session: str, query: str) -> str:
    return _h16(session, query)


def session_of(record: dict) -> str:
    return record["provenance"]["author_instance_id"]


def cycle_of(record: dict) -> int | None:
    for tag in record.get("lineage_tags") or ():
        m = _CYCLE_TAG.match(str(tag))
        if m:
            return int(m.group(1))
    return None


def _record_order(record: dict):
    c = cycle_of(record)
    return (c is None, c or 0, record["provenance"]["timestamp"], record["_key"])


def corpus_sha256(records: list[dict]) -> str:
    clean = [
        {k: v for k, v in r.items() if k not in ("_rev", "_id")}
        for r in sorted(records, key=lambda r: r["_key"])
    ]
    return hashlib.sha256(json.dumps(clean, sort_keys=True).encode()).hexdigest()


# ── Queries ──────────────────────────────────────────────────────────────


def extract_queries(records: list[dict]) -> list[dict]:
    """De-duplicated search_memory calls, earliest first."""
    calls = []
    for r in sorted(records, key=_record_order):
        for i, e in enumerate(r.get("_activity_log") or ()):
            if not isinstance(e, dict) or e.get("tool") != "search_memory":
                continue
            params = e.get("parameters") or {}
            q = params.get("query")
            if not isinstance(q, str) or not q:
                continue
            ts = datetime.fromisoformat(e["timestamp"]) if e.get("timestamp") else None
            calls.append((ts, r, i, e, params, q))
    # Earliest by the call's own timestamp; untimestamped calls keep record order.
    calls.sort(key=lambda c: (c[0] is None, c[0].timestamp() if c[0] else 0))
    out: dict[tuple[str, str], dict] = {}
    for ts, r, _, e, params, q in calls:
        key = (session_of(r), q)
        if key in out:
            out[key]["occurrences"] += 1
            continue
        out[key] = {
            "qid": query_id(*key),
            "session": key[0],
            "query": q,
            "reason": e.get("reason") or "",
            "first_seen_at": e.get("timestamp"),
            "record_key": r["_key"],
            "cycle": e.get("cycle"),
            "scope": params.get("scope"),
            "limit": params.get("limit"),
            "narrow_by": params.get("narrow_by"),
            "occurrences": 1,
        }
    return list(out.values())


# ── Passages ─────────────────────────────────────────────────────────────


def _leaves(value, path: tuple):
    if isinstance(value, dict):
        for k, v in value.items():
            if str(k).startswith("_"):
                continue
            yield from _leaves(v, path + (str(k),))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _leaves(v, path + (str(i),))
    elif isinstance(value, str):
        yield ".".join(path), value


def record_leaves(record: dict):
    """(path, value) for every passage-eligible string leaf of a record."""
    for k, v in record.items():
        if k.startswith("_") or k in EXCLUDED_TOP:
            continue
        yield from _leaves(v, (k,))


def build_passages(records: list[dict]) -> dict[str, dict]:
    """pid -> passage, each owned by the first record in its session to carry it."""
    passages: dict[str, dict] = {}
    for r in sorted(records, key=_record_order):
        s = session_of(r)
        for path, value in record_leaves(r):
            pid = passage_id(s, path, value)
            if pid in passages:
                continue
            passages[pid] = {
                "pid": pid,
                "session": s,
                "path": path,
                "value": value,
                "record_key": r["_key"],
                "cycle": cycle_of(r),
                "timestamp": r["provenance"]["timestamp"],
            }
    return passages


# ── Substring arms ───────────────────────────────────────────────────────


def recency_sort(pids, passages: dict[str, dict]) -> list[str]:
    ranked = sorted(set(pids))  # pid ascending: the final tie-break
    ranked.sort(
        key=lambda p: (
            passages[p]["cycle"] is not None,
            passages[p]["cycle"] or 0,
            passages[p]["timestamp"] if passages[p]["cycle"] is None else "",
        ),
        reverse=True,  # stable: equal keys keep pid ascending
    )
    return ranked


def arm_a0(records: list[dict], passages: dict[str, dict], query: str) -> list[str]:
    needle = query.lower()
    hits = []
    for r in records:
        s = session_of(r)
        for key, value in r.items():
            if key.startswith("_") or not isinstance(value, str):
                continue
            if needle in value.lower():
                hits.append(passage_id(s, key, value))
    return recency_sort(hits, passages)


def arm_a1(passages: dict[str, dict], query: str) -> list[str]:
    needle = query.lower()
    return recency_sort(
        (p for p, x in passages.items() if needle in x["value"].lower()), passages
    )


# ── BM25 arms ────────────────────────────────────────────────────────────


def humanize_path(path: str) -> str:
    return path.replace("_", " ").replace(".", " ")


def text_a2(path: str, value: str) -> str:
    return humanize_path(path) + ": " + value.replace("_", " ")


def text_a3(path: str, value: str) -> str:
    return path + ": " + value


def query_a2(q: str) -> str:
    return q.replace("_", " ")


def query_a3(q: str) -> str:
    return q


_BM25_AQL = """
FOR doc IN @@view
  SEARCH ANALYZER(doc.@field IN TOKENS(@q, 'text_en'), 'text_en')
  OPTIONS {waitForSync: true}
  LET score = BM25(doc)
  SORT score DESC, doc._key ASC
  LIMIT @k
  RETURN {pid: doc._key, score: score}
"""


def run_bm25(db, passages: dict[str, dict], queries: list[dict], k: int = K) -> dict:
    """A2 and A3 over a temporary collection + two views in ``db``.

    ``db`` must be a scratch database (apacheta_test); everything created here
    is dropped in ``finally``. Returns {arm: {qid: {total, top, scores}}}.
    """
    if db.name == "apacheta":
        raise ValueError("run_bm25 creates collections; never point it at apacheta")
    suffix = uuid.uuid4().hex[:12]
    coll = f"fq_passages_{suffix}"
    views = {"A2": (f"fq_a2_{suffix}", "t2", query_a2), "A3": (f"fq_a3_{suffix}", "t3", query_a3)}
    try:
        c = db.create_collection(coll)
        docs = [
            {"_key": p, "t2": text_a2(x["path"], x["value"]), "t3": text_a3(x["path"], x["value"])}
            for p, x in passages.items()
        ]
        for i in range(0, len(docs), 1000):
            c.import_bulk(docs[i : i + 1000], on_duplicate="error", halt_on_error=True)
        for view, field, _ in views.values():
            db.create_arangosearch_view(
                view,
                properties={
                    "links": {coll: {"fields": {field: {"analyzers": ["text_en"]}}}}
                },
            )
        out: dict[str, dict] = {}
        for arm, (view, field, norm) in views.items():
            out[arm] = {}
            for q in queries:
                cur = db.aql.execute(
                    _BM25_AQL,
                    bind_vars={"@view": view, "field": field, "q": norm(q["query"]), "k": k},
                    full_count=True,
                )
                rows = list(cur)
                out[arm][q["qid"]] = {
                    "total": cur.statistics()["fullCount"],
                    "top": [r["pid"] for r in rows],
                    "scores": [r["score"] for r in rows],
                }
        return out
    finally:
        for view, _, _ in views.values():
            db.delete_view(view, ignore_missing=True)
        db.delete_collection(coll, ignore_missing=True)


# ── Judge ────────────────────────────────────────────────────────────────


def _cap(text: str) -> str:
    if len(text) <= TEXT_CAP:
        return text
    return text[:TEXT_CAP] + f" [...truncated {len(text) - TEXT_CAP} chars]"


def render_prompt(template: str, query: str, reason: str, passages: list[dict]) -> str:
    """passages: [{pid, path, text}], in any order; shuffled deterministically."""
    ordered = sorted(
        passages, key=lambda p: hashlib.sha256((query + p["pid"]).encode()).hexdigest()
    )
    block = json.dumps(
        [{"pid": p["pid"], "path": p["path"], "text": _cap(p["text"])} for p in ordered],
        ensure_ascii=False,
        indent=1,
    )
    return (
        template.replace("{query}", query)
        .replace("{reason}", reason or "")
        .replace("{passages}", block)
    )


def parse_judgments(raw: str, pids: set[str]) -> dict[str, int]:
    """Exactly one {pid, relevant in {0,1}} per expected pid, else ValueError."""
    data = json.loads(raw)
    items = data["judgments"] if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ValueError("no judgments array")
    out: dict[str, int] = {}
    for j in items:
        pid, rel = j.get("pid"), j.get("relevant")
        if pid not in pids:
            raise ValueError(f"unexpected pid {pid!r}")
        if pid in out:
            raise ValueError(f"duplicate pid {pid!r}")
        if type(rel) is not int or rel not in (0, 1):
            raise ValueError(f"bad relevant {rel!r} for {pid}")
        out[pid] = rel
    missing = pids - out.keys()
    if missing:
        raise ValueError(f"missing pids {sorted(missing)}")
    return out


def judge_query(
    query: str,
    reason: str,
    passages: list[dict],
    template: str,
    model: str = "gpt-6-astra",
    *,
    cache_dir: Path,
    bypass_cache: bool = False,
) -> dict[str, int]:
    """Label each passage 1/0 via ``codex exec`` (read-only). pid -> label."""
    if not passages:
        return {}
    prompt = render_prompt(template, query, reason, passages)
    # The model is part of the key: the same prompt judged by another model is
    # a different judgment, never a cache hit.
    key = hashlib.sha256(f"{model}\x00{prompt}".encode()).hexdigest()
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{key}.json"
    pids = {p["pid"] for p in passages}
    if not bypass_cache and cache_file.exists():
        return parse_judgments(json.loads(cache_file.read_text())["raw"], pids)

    errors = []
    for _ in range(2):
        # Blinding: codex runs in an EMPTY directory. Its read-only sandbox
        # blocks writes, not reads; from the repo root an agentic judge could
        # open retrieval.jsonl (arm per passage) or predictions/. The schema
        # lives in the per-call tmp dir too (no shared file, no write race).
        # --json keeps the event stream so tool use can be audited.
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "out.json"
            schema_path = Path(tmp) / "judge_schema.json"
            schema_path.write_text(json.dumps(JUDGE_SCHEMA, indent=1))
            try:
                proc = subprocess.run(
                    ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check",
                     "--json", "-C", tmp,
                     "-m", model, "--output-schema", str(schema_path),
                     "-o", str(out_path), prompt],
                    stdin=subprocess.DEVNULL,  # codex hangs waiting on stdin otherwise
                    cwd=tmp,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    check=True,
                )
                raw = out_path.read_text()
                labels = parse_judgments(raw, pids)
            except (subprocess.SubprocessError, OSError, ValueError, KeyError,
                    AttributeError, TypeError) as exc:
                errors.append(repr(exc))
                continue
        if not bypass_cache:
            cache_file.write_text(json.dumps({
                "prompt_sha256": key, "model": model, "raw": raw,
                "events": proc.stdout,
            }))
        return labels
    raise RuntimeError(f"judge failed twice for {query!r}: {errors}")


# ── Scoring ──────────────────────────────────────────────────────────────


def pool(retrieval: list[dict]) -> dict[str, list[str]]:
    """qid -> sorted union of every arm's top 10."""
    out: dict[str, set] = {}
    for row in retrieval:
        out.setdefault(row["qid"], set()).update(row["top"][:K])
    return {q: sorted(p) for q, p in out.items()}


def score(queries: list[dict], retrieval: list[dict], judgments: list[dict],
          rejudge: list[dict] = ()) -> dict:
    rel = {(j["qid"], j["pid"]): j["relevant"] for j in judgments}
    pooled_rel: dict[str, set] = {}
    for (q, p), v in rel.items():
        if v:
            pooled_rel.setdefault(q, set()).add(p)
    by_arm: dict[str, dict] = {}
    for row in retrieval:
        by_arm.setdefault(row["arm"], {})[row["qid"]] = row
    qids = [q["qid"] for q in queries]
    arms = {}
    for arm, rows in sorted(by_arm.items()):
        zero = succ = 0
        precs, recalls, rrs = [], [], []
        for q in qids:
            row = rows[q]
            top = row["top"][:K]
            hits = [rel[(q, p)] for p in top]  # KeyError = unjudged pooled passage
            n_rel = sum(hits)
            if row["total"] == 0:
                zero += 1
            else:
                precs.append(n_rel / min(K, row["total"]))
            succ += n_rel > 0
            if pooled_rel.get(q):
                recalls.append(n_rel / len(pooled_rel[q]))
            rrs.append(next((1 / (i + 1) for i, h in enumerate(hits) if h), 0.0))
        n = len(qids)
        arms[arm] = {
            "queries": n,
            "zero_result": zero,
            "zero_result_rate": zero / n,
            "success_at_10": succ / n,
            "precision_at_10": sum(precs) / len(precs) if precs else None,
            "precision_denominator_queries": len(precs),
            "pooled_recall": sum(recalls) / len(recalls) if recalls else None,
            "recall_denominator_queries": len(recalls),
        }
        if arm in ("A2", "A3"):
            arms[arm]["mrr"] = sum(rrs) / n
    flips = sum(rel[(r["qid"], r["pid"])] != r["relevant"] for r in rejudge)
    return {
        "k": K,
        "arms": arms,
        "judged_labels": len(rel),
        "relevant_labels": sum(rel.values()),
        "judge_noise": {
            "rejudged_labels": len(rejudge),
            "rejudged_queries": len({r["qid"] for r in rejudge}),
            "flips": flips,
            "flip_rate": flips / len(rejudge) if rejudge else None,
        },
    }
