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
    return list(h.aql.execute(aql, bind_vars={"t": term}))


def test_ghola_query_reproduces_issue_numbers():
    """gh #34's worked example, against the live episodes silo: session and day
    discriminate (~0.9), model does not (~0.12, ~all opus). The numbers are the
    issue's; reproducing them proves the mechanism on real data, not a fixture."""
    rows = _live_episodes_rows_for("ghola")
    fd = discriminate(rows, facet_fields=["session", "day", "model"])
    by = {f.name: f for f in fd.facets}

    # the result set the issue measured
    assert fd.result_size == 121

    # session and day shatter the set; model does not
    assert by["session"].entropy == pytest.approx(0.89, abs=0.03)
    assert by["day"].entropy == pytest.approx(0.90, abs=0.03)
    assert by["model"].entropy == pytest.approx(0.12, abs=0.05)

    # the Archivist asks about session-or-day, never model
    assert by["session"].discriminating and by["day"].discriminating
    assert not by["model"].discriminating
    assert fd.best.name in {"session", "day"}
