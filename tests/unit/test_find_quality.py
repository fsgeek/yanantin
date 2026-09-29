"""Find-quality instrument (yanantin.eval.find_quality) on synthetic records."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from yanantin.eval import find_quality as fq


def rec(key, session, cycle, body, log=(), ts=None, extra_tags=()):
    tags = ["hamutay", *extra_tags] + ([f"cycle-{cycle}"] if cycle is not None else [])
    return {
        "_key": key, "_id": f"records/{key}", "_rev": "x",
        "provenance": {"author_instance_id": session,
                       "timestamp": ts or f"2026-01-01T00:00:{(cycle or 0):02d}Z"},
        "lineage_tags": tags,
        "_activity_log": list(log),
        **body,
    }


def call(query, reason, ts, **params):
    return {"tool": "search_memory", "cycle": 1, "timestamp": ts,
            "parameters": {"query": query, **params}, "reason": reason}


# ── queries ────────────────────────────────────────────────────────────────

def test_cumulative_log_dedupes_by_session_and_query_keeping_first():
    c1 = call("clock", "why 1", "2026-01-01T00:00:01+00:00", scope="session", limit=5)
    c2 = call("clock", "why 2", "2026-01-01T00:00:05+00:00", scope="all")
    other = {"tool": "bash", "parameters": {"command": "ls"}, "reason": "x",
             "timestamp": "2026-01-01T00:00:02+00:00"}
    records = [
        rec("b", "s1", 2, {}, log=[c1, other, c2]),     # cumulative: repeats c1
        rec("a", "s1", 1, {}, log=[c1]),
        rec("c", "s2", 1, {}, log=[call("clock", None, "2026-01-01T00:00:09Z")]),
    ]
    qs = fq.extract_queries(records)
    assert [(q["session"], q["query"]) for q in qs] == [("s1", "clock"), ("s2", "clock")]
    s1 = qs[0]
    assert s1["reason"] == "why 1" and s1["scope"] == "session" and s1["limit"] == 5
    assert s1["occurrences"] == 3 and s1["record_key"] == "a"
    assert qs[1]["reason"] == ""  # empty reason kept
    assert s1["qid"] == fq.query_id("s1", "clock")


# ── passages ───────────────────────────────────────────────────────────────

def test_passage_belongs_to_first_introducing_record_in_session():
    records = [
        rec("late", "s", 5, {"note": "same"}),
        rec("early", "s", 2, {"note": "same"}),
        rec("other", "t", 9, {"note": "same"}),
    ]
    ps = fq.build_passages(records)
    assert len(ps) == 2  # one per session
    s = ps[fq.passage_id("s", "note", "same")]
    assert s["record_key"] == "early" and s["cycle"] == 2


def test_nested_extraction_and_exclusions():
    body = {
        "what_i_carry": [{"claim": "c0", "n": 3}, {"claim": "c1", "_hidden": "no"}],
        "deep": {"a": {"b": ["x", None, True]}},
        "_private": "no",
        "count": 7,
        "flag": False,
    }
    ps = fq.build_passages([rec("r", "s", 1, body)])
    assert sorted(p["path"] for p in ps.values()) == [
        "deep.a.b.0", "what_i_carry.0.claim", "what_i_carry.1.claim"]
    assert all(not p["path"].startswith(("provenance", "lineage_tags")) for p in ps.values())


def test_pid_is_sha256_prefix():
    import hashlib
    expect = hashlib.sha256("s\x00p.q\x00v".encode()).hexdigest()[:16]
    assert fq.passage_id("s", "p.q", "v") == expect


# ── substring arms ─────────────────────────────────────────────────────────

def test_a0_top_level_only_a1_reaches_nested():
    records = [rec("r", "s", 1, {"top": "Needle here", "nest": {"x": "needle deep"}})]
    ps = fq.build_passages(records)
    top = fq.passage_id("s", "top", "Needle here")
    deep = fq.passage_id("s", "nest.x", "needle deep")
    assert fq.arm_a0(records, ps, "NEEDLE") == [top]
    assert set(fq.arm_a1(ps, "needle")) == {top, deep}


def test_substring_matches_values_not_keys():
    records = [rec("r", "s", 1, {"needle_key": "hay"})]
    ps = fq.build_passages(records)
    assert fq.arm_a0(records, ps, "needle") == []
    assert fq.arm_a1(ps, "needle") == []


def test_recency_order_cycle_desc_pid_tiebreak_cycleless_last():
    records = [
        rec("r1", "s", 1, {"a": "k one", "b": "k two"}),
        rec("r3", "s", 3, {"a": "k three"}),
        rec("nc", "u", None, {"a": "k none"}, ts="2030-01-01T00:00:00Z"),
    ]
    ps = fq.build_passages(records)
    ranked = fq.arm_a1(ps, "k")
    assert [ps[p]["cycle"] for p in ranked] == [3, 1, 1, None]
    assert ranked[1] < ranked[2]


# ── BM25 text normalisation ────────────────────────────────────────────────

def test_a2_vs_a3_text_and_query():
    assert fq.text_a2("what_i_carry.0.claim", "reward_function x") == \
        "what i carry 0 claim: reward function x"
    assert fq.text_a3("what_i_carry.0.claim", "reward_function x") == \
        "what_i_carry.0.claim: reward_function x"
    assert fq.query_a2("reward_function") == "reward function"
    assert fq.query_a3("reward_function") == "reward_function"


# ── corpus hash ────────────────────────────────────────────────────────────

def test_corpus_sha_ignores_rev_id_and_order():
    a, b = rec("a", "s", 1, {"x": "1"}), rec("b", "s", 2, {"x": "2"})
    b2 = dict(b, _rev="other", _id="elsewhere")
    assert fq.corpus_sha256([a, b]) == fq.corpus_sha256([b2, a])
    assert fq.corpus_sha256([a]) != fq.corpus_sha256([a, b])


# ── judge ──────────────────────────────────────────────────────────────────

PASSAGES = [{"pid": "p1", "path": "a", "text": "one"},
            {"pid": "p2", "path": "b", "text": "x" * 3000}]
TEMPLATE = "Q={query}\nR={reason}\nP={passages}\n{not a slot}"


class FakeCodex:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, argv, **kw):
        self.calls.append((argv, kw))
        out = self.outputs.pop(0)
        path = argv[argv.index("-o") + 1]
        if out is not None:
            with open(path, "w") as f:
                f.write(out if isinstance(out, str) else json.dumps(out))
        return subprocess.CompletedProcess(argv, 0, "", "")


def good(**labels):
    return {"judgments": [{"pid": p, "relevant": v} for p, v in labels.items()]}


def test_render_prompt_shuffles_deterministically_and_caps():
    p = fq.render_prompt(TEMPLATE, "q", "", PASSAGES)
    assert p == fq.render_prompt(TEMPLATE, "q", "", list(reversed(PASSAGES)))
    assert "R=\n" in p and "{not a slot}" in p
    block = json.loads(p.split("P=", 1)[1].rsplit("\n{not", 1)[0])
    long = next(x for x in block if x["pid"] == "p2")["text"]
    assert long.startswith("x" * 2000) and long.endswith("[...truncated 1000 chars]")


def test_judge_invokes_codex_readonly_with_devnull_and_caches(tmp_path, monkeypatch):
    fake = FakeCodex([good(p1=1, p2=0), good(p1=1, p2=0)])
    monkeypatch.setattr(fq.subprocess, "run", fake)
    labels = fq.judge_query("q", "r", PASSAGES, TEMPLATE, cache_dir=tmp_path)
    assert labels == {"p1": 1, "p2": 0}
    argv, kw = fake.calls[0]
    assert argv[:5] == ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check"]
    assert argv[argv.index("-m") + 1] == "gpt-6-astra"
    assert "--json" in argv and "--output-schema" in argv
    assert kw["stdin"] is subprocess.DEVNULL and kw["timeout"] == 600
    # blinding: the judge runs in its own empty tmp dir, not the repo
    workdir = argv[argv.index("-C") + 1]
    assert kw["cwd"] == workdir and not workdir.startswith(str(Path.cwd()))
    assert Path(argv[argv.index("--output-schema") + 1]).parent == Path(workdir)
    assert argv[-1] == fq.render_prompt(TEMPLATE, "q", "r", PASSAGES)
    # cached: no second call
    assert fq.judge_query("q", "r", PASSAGES, TEMPLATE, cache_dir=tmp_path) == labels
    assert len(fake.calls) == 1
    # a different model is a different judgment, never a cache hit
    fq.judge_query("q", "r", PASSAGES, TEMPLATE, model="other", cache_dir=tmp_path)
    assert len(fake.calls) == 2


def test_judge_bypass_reruns_identical_prompt(tmp_path, monkeypatch):
    fake = FakeCodex([good(p1=1, p2=0), good(p1=0, p2=0)])
    monkeypatch.setattr(fq.subprocess, "run", fake)
    fq.judge_query("q", "r", PASSAGES, TEMPLATE, cache_dir=tmp_path)
    again = fq.judge_query("q", "r", PASSAGES, TEMPLATE, cache_dir=tmp_path, bypass_cache=True)
    assert again == {"p1": 0, "p2": 0}
    assert fake.calls[0][0][-1] == fake.calls[1][0][-1]
    # bypass does not overwrite the first judgment's cache
    assert fq.judge_query("q", "r", PASSAGES, TEMPLATE, cache_dir=tmp_path) == {"p1": 1, "p2": 0}


@pytest.mark.parametrize("bad", [
    good(p1=1),                                   # missing pid
    good(p1=1, p2=0, p3=1),                       # extra pid
    {"judgments": [{"pid": "p1", "relevant": 1}, {"pid": "p1", "relevant": 0},
                   {"pid": "p2", "relevant": 0}]},  # duplicate
    good(p1=2, p2=0),                             # out of range
    good(p1=True, p2=0),                          # bool, not int
    "not json",
    None,                                         # no output file
])
def test_judge_rejects_bad_output_then_retries_once(tmp_path, monkeypatch, bad):
    fake = FakeCodex([bad, good(p1=0, p2=1)])
    monkeypatch.setattr(fq.subprocess, "run", fake)
    assert fq.judge_query("q", "r", PASSAGES, TEMPLATE, cache_dir=tmp_path) == {"p1": 0, "p2": 1}
    assert len(fake.calls) == 2


def test_judge_fails_after_two_bad_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(fq.subprocess, "run", FakeCodex([good(p1=1), "junk"]))
    with pytest.raises(RuntimeError):
        fq.judge_query("q", "r", PASSAGES, TEMPLATE, cache_dir=tmp_path)
    assert not list(tmp_path.glob("[0-9a-f]*.json"))


def test_judge_timeout_is_retried(tmp_path, monkeypatch):
    outs = iter([subprocess.TimeoutExpired("codex", 600), None])

    def run(argv, **kw):
        exc = next(outs)
        if exc:
            raise exc
        return FakeCodex([good(p1=1, p2=1)])(argv, **kw)

    monkeypatch.setattr(fq.subprocess, "run", run)
    assert fq.judge_query("q", "", PASSAGES, TEMPLATE, cache_dir=tmp_path) == {"p1": 1, "p2": 1}


# ── scoring ────────────────────────────────────────────────────────────────

def test_score_metrics():
    queries = [{"qid": "q1"}, {"qid": "q2"}]
    retrieval = [
        {"qid": "q1", "arm": "A1", "total": 3, "top": ["a", "b", "c"]},
        {"qid": "q2", "arm": "A1", "total": 0, "top": []},
        {"qid": "q1", "arm": "A2", "total": 50, "top": ["x", "b"]},
        {"qid": "q2", "arm": "A2", "total": 1, "top": ["y"]},
    ]
    pooled = fq.pool(retrieval)
    assert pooled == {"q1": ["a", "b", "c", "x"], "q2": ["y"]}
    rel = {"a": 0, "b": 1, "c": 1, "x": 0, "y": 0}
    judgments = [{"qid": q, "pid": p, "relevant": rel[p]} for q, ps in pooled.items() for p in ps]
    rejudge = [{"qid": "q1", "pid": "a", "relevant": 1}, {"qid": "q1", "pid": "b", "relevant": 1}]
    s = fq.score(queries, retrieval, judgments, rejudge)
    a1, a2 = s["arms"]["A1"], s["arms"]["A2"]
    assert a1["zero_result_rate"] == 0.5 and a2["zero_result_rate"] == 0
    assert a1["success_at_10"] == 0.5 and a2["success_at_10"] == 0.5
    assert a1["precision_at_10"] == pytest.approx(2 / 3)
    assert a2["precision_at_10"] == pytest.approx((1 / 10 + 0 / 1) / 2)
    assert a1["pooled_recall"] == 1.0 and a2["pooled_recall"] == 0.5
    assert a2["mrr"] == pytest.approx((1 / 2 + 0) / 2) and "mrr" not in a1
    assert s["judge_noise"]["flip_rate"] == 0.5
