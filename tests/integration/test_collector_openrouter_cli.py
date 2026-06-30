"""Wiring test for the `openrouter` collector verb (gh #29).

OpenRouterFactRecorder is built but, until now, was never reachable from the
collector entrypoint. These tests drive the `openrouter` verb the same way the
other domains are exercised and prove the recorder actually writes facts into
the activity-stream store.

No live DB: `--store memory` keeps this in-process (the entrypoint's own store
backend), matching the existing CLI smoke test.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.collector import __main__ as collector_main
from yanantin.collector import pipeline as collector_pipeline


CSV_TWO_ROWS = (
    "generation_id,created_at,cost_total,tokens_prompt,tokens_completion,model_permaslug\n"
    "gen-abc-1,2026-06-01T12:00:00Z,0.0021,100,50,anthropic/claude-opus\n"
    "gen-abc-2,2026-06-01T12:05:00Z,0.0007,40,20,openai/gpt-4o\n"
)


def _write_csv(tmp_path: Path) -> Path:
    csv_path = tmp_path / "openrouter_export.csv"
    csv_path.write_text(CSV_TWO_ROWS, encoding="utf-8")
    return csv_path


def test_openrouter_verb_lands_facts_in_store(tmp_path, monkeypatch, capsys) -> None:
    """Drive the openrouter entrypoint handler and assert the facts land.

    The handler calls `_store_facts`, which opens a store via
    `pipeline.open_store`. We pin that to a store WE own so the recorder's
    output is inspectable after the entrypoint runs — proving the fact
    reached the store, not just that stdout said "Stored".
    """
    csv_path = _write_csv(tmp_path)
    store = InMemoryActivityStreamStore()
    monkeypatch.setattr(collector_pipeline, "open_store", lambda _name: store)

    args = collector_main.argparse.Namespace(
        path=str(csv_path), since=None, store="memory", json=False,
    )
    collector_main._cmd_openrouter(args)

    providers = store.list_providers()
    assert len(providers) == 1
    assert store.count_facts() == 2

    fact = store.query_latest(providers[0])
    assert fact is not None
    assert fact.data["generation_id"] == "gen-abc-2"
    assert fact.data["model_permaslug"] == "openai/gpt-4o"


def test_openrouter_verb_runs_through_module_entrypoint(tmp_path) -> None:
    """End-to-end smoke through `python -m yanantin.collector openrouter`."""
    csv_path = _write_csv(tmp_path)
    r = subprocess.run(
        [sys.executable, "-m", "yanantin.collector", "openrouter",
         str(csv_path), "--store", "memory"],
        capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stderr
    assert "Stored 2 facts" in r.stdout, r.stdout
