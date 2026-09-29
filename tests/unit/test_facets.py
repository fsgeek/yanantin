"""Facet discrimination — the Archivist navigator (gh #34).

Synthetic ground truth (known entropy by construction) for the mechanism, plus a
live-corpus reproduction of the issue's worked example (query `ghola` over the
episodes silo: session 0.89, day 0.90, model 0.12) so the unit is anchored to the
real numbers it was designed from, not just to hand-built fixtures.
"""

from __future__ import annotations

import configparser
from pathlib import Path

import pytest

from yanantin.llika.facets import discriminate


# ── Synthetic ground truth: entropy is known by construction ──────────────

def test_even_two_way_split_is_max_discrimination():
    """A facet split evenly across 2 values scores 1.0 — the perfect question."""
    records = [{"side": "a"}, {"side": "b"}, {"side": "a"}, {"side": "b"}]
    fd = discriminate(records, facet_fields=["side"])
    (facet,) = fd.facets
    assert facet.distinct == 2
    assert facet.entropy == pytest.approx(1.0)
    assert facet.discriminating is True


def test_single_value_facet_cannot_ask_anything():
    """One dominant value = 0 entropy = useless cut, even with many records."""
    records = [{"model": "opus"} for _ in range(50)]
    fd = discriminate(records, facet_fields=["model"])
    (facet,) = fd.facets
    assert facet.entropy == 0.0
    assert facet.discriminating is False
    assert fd.best is None


def test_ranks_by_discrimination_and_picks_best():
    """The high-entropy facet ranks first and is surfaced as `best`."""
    # session: 4 distinct even -> 1.0; model: 7/1 skewed -> low
    records = [
        {"session": s, "model": "opus" if i < 7 else "haiku"}
        for i, s in enumerate(["a", "b", "c", "d"] * 2)
    ]
    fd = discriminate(records)
    assert fd.facets[0].name == "session"
    assert fd.facets[0].entropy > fd.facets[-1].entropy
    assert fd.best is not None and fd.best.name == "session"


def test_facets_discovered_open_schema_not_enumerated():
    """With no facet_fields given, facets come from the records' own keys —
    a new key in the data becomes a candidate axis with no code change."""
    records = [{"a": 1, "b": 2}, {"a": 1, "c": 3}]
    fd = discriminate(records)
    assert {f.name for f in fd.facets} == {"a", "b", "c"}


def test_private_keys_excluded():
    """ArangoDB _id/_rev are storage plumbing, never navigation axes."""
    records = [{"_id": "x/1", "_rev": "r1", "k": "v"}, {"_id": "x/2", "k": "w"}]
    fd = discriminate(records)
    assert {f.name for f in fd.facets} == {"k"}


def test_none_is_not_a_bucket():
    """An absent field value is excluded, not counted as its own answer."""
    records = [{"x": "a"}, {"x": None}, {"x": "a"}, {"x": "b"}]
    fd = discriminate(records, facet_fields=["x"])
    (facet,) = fd.facets
    assert facet.distinct == 2                       # a, b — not None
    assert sum(c for _, c in facet.top) == 3         # three non-null values


def test_empty_result_set():
    fd = discriminate([])
    assert fd.result_size == 0
    assert fd.best is None


# ── Live-corpus reproduction of the issue's worked example ────────────────

def _live_episodes_rows_for(term: str):
    ini = Path.home() / ".yanantin" / "config" / "db.ini"
    if not ini.exists():
        pytest.skip("no ~/.yanantin/config/db.ini — live store unavailable")
    ArangoClient = pytest.importorskip("arango").ArangoClient
    cfg = configparser.ConfigParser()
    cfg.read(ini)
    db = cfg["database"]
    scheme = "https" if db.get("ssl", "false") == "true" else "http"
    client = ArangoClient(hosts=f"{scheme}://{db['host']}:{db['port']}")
    h = client.db("llm_memory", username=db["admin_user"], password=db["admin_passwd"])
    aql = """
    FOR e IN episodes
      FILTER CONTAINS(LOWER(e.user_message), @t) OR CONTAINS(LOWER(e.response), @t)
      RETURN { session: e.session_id, model: e.model,
               day: SUBSTRING(e.ts, 0, 10) }
    """
    # This is a LOCAL-CORPUS reproduction: the `llm_memory` silo (the `ghola`
    # data) lives on the dev box, not in CI (which only provisions apacheta_test).
    # Skip cleanly when that corpus is absent — never hard-fail on a missing DB.
    # The skip is narrow: it catches "this environment lacks llm_memory/episodes",
    # NOT a broken query or wrong result (those still fail loudly). The synthetic
    # ground-truth tests above carry the portable verification; this one anchors
    # the mechanism to real numbers where the real data exists.
    from arango.exceptions import AQLQueryExecuteError, ArangoServerError

    try:
        return list(h.aql.execute(aql, bind_vars={"t": term}))
    except (AQLQueryExecuteError, ArangoServerError) as exc:
        if "not found" in str(exc).lower() or getattr(exc, "error_code", None) in (1203, 1228):
            pytest.skip(f"llm_memory/episodes corpus not in this environment: {exc}")
        raise


def test_ghola_query_session_and_day_lead_on_live_silo():
    """gh #34's worked example, against the live episodes silo: session and day
    discriminate and lead the ranking.

    The issue's exact numbers (121 rows; model entropy ~0.12, ~all opus) were a
    snapshot and cannot be reproduced: the silo grows in BOTH directions —
    backfill from other machines adds old-dated episodes (196 rows dated before
    the issue by 2026-09-29), so even a time window does not pin it. And model
    now legitimately discriminates (0.55) because more model families were used
    since. Assert only what is a property of the mechanism, not of the corpus."""
    rows = _live_episodes_rows_for("ghola")
    fd = discriminate(rows, facet_fields=["session", "day", "model"])
    by = {f.name: f for f in fd.facets}

    assert fd.result_size == len(rows)
    assert by["session"].discriminating and by["day"].discriminating
    assert fd.best.name in {"session", "day"}
