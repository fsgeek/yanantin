"""BM25 arms (A2/A3) against live ArangoSearch in apacheta_test.

Skips cleanly when the DB is unreachable; the temporary collection and views
are dropped by run_bm25's finally, and this test checks nothing is left.
"""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest

from yanantin.eval import find_quality as fq


@pytest.fixture
def test_db():
    ini = Path.home() / ".yanantin" / "config" / "db.ini"
    if not ini.exists():
        pytest.skip("no ~/.yanantin/config/db.ini — live store unavailable")
    ArangoClient = pytest.importorskip("arango").ArangoClient
    cfg = configparser.ConfigParser()
    cfg.read(ini)
    db = cfg["database"]
    scheme = "https" if db.get("ssl", "false") == "true" else "http"
    client = ArangoClient(hosts=f"{scheme}://{db['host']}:{db.get('port', '8529')}")
    h = client.db("apacheta_test", username=db["admin_user"], password=db["admin_passwd"])
    try:
        h.version()
    except Exception as exc:  # connection refused, auth, missing db
        pytest.skip(f"apacheta_test unreachable: {exc}")
    return h


def _fq_objects(db):
    return ({c["name"] for c in db.collections() if c["name"].startswith("fq_")}
            | {v["name"] for v in db.views() if v["name"].startswith("fq_")})


def test_bm25_underscore_rule_separates_a2_from_a3(test_db):
    before = _fq_objects(test_db)
    records = [
        {"_key": "r1", "provenance": {"author_instance_id": "s", "timestamp": "t1"},
         "lineage_tags": ["cycle-1"],
         "reward_function": "shaped by relational feedback",
         "notes": ["the reward_function was discussed", "nothing relevant"]},
        {"_key": "r2", "provenance": {"author_instance_id": "s", "timestamp": "t2"},
         "lineage_tags": ["cycle-2"], "other": "a reward and a function, apart"},
    ]
    passages = fq.build_passages(records)
    queries = [{"qid": "q1", "query": "reward_function"}, {"qid": "q2", "query": "zzqqxx"}]
    out = fq.run_bm25(test_db, passages, queries)

    a2, a3 = out["A2"]["q1"], out["A3"]["q1"]
    field = fq.passage_id("s", "reward_function", "shaped by relational feedback")
    inline = fq.passage_id("s", "notes.0", "the reward_function was discussed")
    apart = fq.passage_id("s", "other", "a reward and a function, apart")
    # A2 splits the underscore: the humanized path, the inline token and the
    # "reward ... function" passage all match.
    assert {field, inline, apart} <= set(a2["top"])
    assert a2["total"] == len(a2["top"]) == 3
    assert a2["scores"] == sorted(a2["scores"], reverse=True)
    # A3 keeps reward_function as one token: the free-text passage is out.
    assert apart not in a3["top"]
    assert inline in a3["top"]
    assert out["A2"]["q2"] == {"total": 0, "top": [], "scores": []}
    assert _fq_objects(test_db) == before


def test_bm25_refuses_production(test_db):
    class Prod:
        name = "apacheta"

    with pytest.raises(ValueError):
        fq.run_bm25(Prod(), {}, [])
