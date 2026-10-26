"""M3: label abandoned search chains as snippet-found, existed-not-found, absent or unclear.

Pre-registered in predictions/2026-10-26-finding-metrics-claude.md (97cbe9f7). The
judge is Codex (a different model family), run read-only in an empty directory
(so it cannot read the predictions), with khipumaq's MCP search and recall. It may
search only episodes before the chain's first search (`until`); its JSON event
stream is kept, and the audit below checks that bound and the cited episode's time.

Usage:
    uv run --with-editable ../khipumaq python scripts/adjudicate_finding_chains.py [--limit N] [--no-ledger]
"""

from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from khipumaq.db import get_database

from yanantin.eval.finding_chains import span_context
from yanantin.eval.ledger import append

VERSION = "2026-10-26a"
DIR = Path("results/finding-metrics") / VERSION
CACHE = DIR / "judge-cache"
MODEL = "gpt-6-astra"
SEED, SAMPLE, MAX_SEARCHES = 20261026, 60, 10
LABELS = ("snippet-found", "existed-not-found", "absent", "unclear")
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["label", "evidence_key", "reason"],
    "properties": {
        "label": {"type": "string", "enum": list(LABELS)},
        "evidence_key": {"type": ["string", "null"]},
        "reason": {"type": "string"},
    },
}
LINES = """FOR r IN raw FILTER r.source_file == @s COLLECT host = r.host INTO g
  LIMIT 1 RETURN (FOR x IN g[*].r SORT x.line RETURN x.text)"""
EPISODE_TS = "FOR e IN episodes FILTER e._key == @k RETURN e.ts"

PROMPT = """You are judging one search an AI assistant made in its own conversation history.
The history store is reachable through your MCP tools `search` and `recall` (server
khipumaq). The assistant searched, then did not open any result. Decide why.

Rules:
- Call `search` with until="{until}" on EVERY call (only what existed before the
  assistant searched counts), and scope="all". At most {max_searches} searches.
- You may `recall` any key a search returned.
- Do not read files or run commands.

Labels:
- snippet-found: a snippet the assistant already got answered what it needed.
- existed-not-found: an episode before {until} answers the need; give its key.
- absent: after your searches, nothing before {until} answers the need.
- unclear: you cannot tell what was needed, or cannot decide.

What the person said before the search:
<<<
{request}
>>>

The assistant's searches: {queries}

What its searches returned:
<<<
{results}
>>>

How the assistant ended that turn:
<<<
{response}
>>>
"""


def clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + f"\n[... {len(s) - n} characters cut]"


def iso_z(ts: str) -> str:
    dt = datetime.fromisoformat(ts)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def judge(prompt: str) -> dict:
    key = hashlib.sha256(f"{MODEL}\x00{prompt}".encode()).hexdigest()
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{key}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    with tempfile.TemporaryDirectory() as tmp:
        out, schema = Path(tmp) / "out.json", Path(tmp) / "schema.json"
        schema.write_text(json.dumps(SCHEMA))
        proc = subprocess.run(
            ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", "--json",
             "-C", tmp, "-m", MODEL, "--output-schema", str(schema), "-o", str(out), prompt],
            stdin=subprocess.DEVNULL, cwd=tmp, capture_output=True, text=True, timeout=900)
        answer = out.read_text() if out.exists() else ""
    record = {"prompt_sha256": key, "model": MODEL, "answer": answer,
              "events": proc.stdout, "returncode": proc.returncode}
    cached.write_text(json.dumps(record))
    return record


def mcp_calls(events: str) -> list[dict]:
    calls = []
    for line in events.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        item = e.get("item") if isinstance(e, dict) else None
        if isinstance(item, dict) and item.get("type") == "mcp_tool_call" and e.get("type") == "item.completed":
            calls.append({"tool": item.get("tool"), "arguments": item.get("arguments") or {}})
    return calls


def audit(record: dict, until: str, db) -> dict:
    """The label stands only if the judge kept to the rules we can check."""
    try:
        answer = json.loads(record["answer"])
    except (ValueError, TypeError):
        return {"label": "unclear", "audit": "no parseable answer"}
    calls = mcp_calls(record["events"])
    searches = [c for c in calls if c["tool"] == "search"]
    problems = []
    if len(searches) > MAX_SEARCHES:
        problems.append(f"{len(searches)} searches")
    if any(str(c["arguments"].get("until", "")) > until or not c["arguments"].get("until") for c in searches):
        problems.append("a search without the until bound")
    label = answer["label"]
    if label == "existed-not-found":
        ts = next(iter(db.aql.execute(EPISODE_TS, bind_vars={"k": answer.get("evidence_key") or ""})), None)
        if ts is None or ts >= until:
            problems.append(f"evidence {answer.get('evidence_key')!r} not an episode before the chain")
    if label in ("existed-not-found", "absent") and not searches:
        problems.append("labelled without searching")
    return {"label": "unclear" if problems else label, "judge_label": label,
            "evidence_key": answer.get("evidence_key"), "reason": answer.get("reason"),
            "searches": len(searches), "audit": "; ".join(problems) or "ok"}


def main() -> None:
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    rows = [json.loads(line) for line in (DIR / "chains.jsonl").read_text().splitlines()]
    abandoned = [r for r in rows if r["arm"] == "tool" and not r["found"]]
    chosen = abandoned if len(abandoned) <= SAMPLE else random.Random(SEED).sample(abandoned, SAMPLE)
    chosen = chosen[:limit] if limit else chosen
    db = get_database()
    out = []
    for i, r in enumerate(chosen):
        lines = next(iter(db.aql.execute(LINES, bind_vars={"s": r["source"]})), [])
        ctx = span_context([t for t in lines if t], r["first_call_id"])
        if ctx is None or not r["first_ts"]:
            out.append({**r, "label": "unclear", "audit": "context not recovered"})
            continue
        until = iso_z(r["first_ts"])
        prompt = PROMPT.format(
            until=until, max_searches=MAX_SEARCHES, request=clip(ctx["request"], 4000),
            queries=json.dumps(r["queries"]), results=clip("\n---\n".join(ctx["results"]), 6000),
            response=clip(ctx["response"], 2500))
        verdict = audit(judge(prompt), until, db)
        out.append({"first_call_id": r["first_call_id"], "window": r["window"], "session": r["session"],
                    "first_ts": r["first_ts"], **verdict})
        print(f"{i + 1}/{len(chosen)} {r['window']} {verdict['label']} ({verdict['audit']})", flush=True)

    (DIR / "adjudication.jsonl").write_text("".join(json.dumps(o, sort_keys=True) + "\n" for o in out))
    counts = {"abandoned_tool_chains": len(abandoned), "judged": len(out),
              "labels": dict(Counter(o["label"] for o in out)),
              "judge_labels_before_audit": dict(Counter(o.get("judge_label", o["label"]) for o in out)),
              "by_window": {w: dict(Counter(o["label"] for o in out if o["window"] == w))
                            for w in sorted({o["window"] for o in out})}}
    (DIR / "adjudication-summary.json").write_text(json.dumps(counts, indent=2, sort_keys=True))
    print(json.dumps(counts, indent=1))
    if "--no-ledger" not in sys.argv and not limit:
        append({"observed_at": datetime.now(UTC).isoformat(),
                "instrument": {"name": "finding-chains-m3", "version": VERSION, "model": MODEL,
                               "predictions": "predictions/2026-10-26-finding-metrics-claude.md",
                               "scripts": ["scripts/adjudicate_finding_chains.py"],
                               "known_limits": "LLM judge, no human audit; absent bounded by 10 searches; "
                                               "tool arm only (grep chains have no snippets to judge)"},
                "population": {"abandoned_tool_chains": len(abandoned), "seed": SEED, "sample": len(out)},
                "quantity": "m3_abandoned_chain_labels", "value": counts})


if __name__ == "__main__":
    main()
