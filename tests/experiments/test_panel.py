from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import json

import yaml

from yanantin.experiments.catalog import catalog_snapshot_sha
from yanantin.experiments.panel import (
    DEFAULT_NATIVE_MAX_TOKENS,
    CandidateModel,
    PanelCriteria,
    dump_resolved,
    load_criteria,
    resolve_panel,
)


def _sample_catalog() -> list[dict]:
    fixture_path = Path(__file__).parent / "fixtures" / "openrouter_models_sample.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return payload["data"]


def test_load_criteria_reads_real_panel_file() -> None:
    criteria = load_criteria("experiments/memory_tools/panels/iteration_v1.criteria.yaml")

    assert criteria.panel_id == "iteration_v1"
    assert criteria.context_length_min == 8000
    assert criteria.exclude_patterns == ["*-audio-*", "*:online"]
    assert len(criteria.candidates) > 0
    assert isinstance(criteria.candidates[0], CandidateModel)


def test_resolve_panel_resolves_manifest_fields_from_catalog() -> None:
    catalog = _sample_catalog()
    criteria = PanelCriteria(
        panel_id="panel_under_test",
        rationale="test rationale",
        context_length_min=8000,
        exclude_patterns=[],
        candidates=[
            CandidateModel(
                id="meta-llama/llama-4-scout",
                family="llama",
                size_tier="large-open",
                cost_tier="cheap",
            ),
            CandidateModel(
                id="google/gemma-4-31b-it",
                family="gemma",
                size_tier="mid",
                cost_tier="cheap",
            ),
        ],
    )
    resolved_at = datetime(2026, 5, 12, 15, 0, tzinfo=UTC)

    panel = resolve_panel(criteria, catalog, resolved_at=resolved_at)

    assert panel.panel_id == criteria.panel_id
    assert panel.rationale == criteria.rationale
    assert panel.resolved_at == resolved_at
    assert panel.catalog_snapshot_sha == catalog_snapshot_sha(catalog)

    models_by_id = {m.id: m for m in panel.models}
    assert set(models_by_id) == {
        "meta-llama/llama-4-scout",
        "google/gemma-4-31b-it",
    }

    llama = models_by_id["meta-llama/llama-4-scout"]
    assert llama.family == "llama"
    assert llama.size_tier == "large-open"
    assert llama.cost_tier == "cheap"
    assert llama.prompt_cost == 0.00000008
    assert llama.completion_cost == 0.0000003
    assert llama.context_length == 131072
    assert llama.native_max_tokens == 16384


def test_resolve_panel_applies_context_min_and_exclude_patterns() -> None:
    catalog = _sample_catalog()
    criteria = PanelCriteria(
        panel_id="filtered",
        rationale="filters should be honored",
        context_length_min=8000,
        exclude_patterns=["*-audio-*"],
        candidates=[
            CandidateModel(
                id="meta-llama/llama-4-scout",
                family="llama",
                size_tier="large-open",
                cost_tier="cheap",
            ),
            CandidateModel(
                id="openai/gpt-4o-audio-preview",
                family="openai",
                size_tier="small",
                cost_tier="frontier-cheap",
            ),
            CandidateModel(
                id="tiny/no-context-model",
                family="tiny",
                size_tier="tiny",
                cost_tier="cheap",
            ),
        ],
    )

    panel = resolve_panel(criteria, catalog)

    assert {m.id for m in panel.models} == {"meta-llama/llama-4-scout"}


def test_resolve_panel_uses_default_native_max_tokens_fallback() -> None:
    catalog = _sample_catalog()
    criteria = PanelCriteria(
        panel_id="native_max_fallback",
        rationale="missing top_provider.max_completion_tokens should fallback",
        context_length_min=0,
        exclude_patterns=[],
        candidates=[
            CandidateModel(
                id="tiny/no-context-model",
                family="tiny",
                size_tier="tiny",
                cost_tier="cheap",
            )
        ],
    )

    panel = resolve_panel(criteria, catalog)

    assert len(panel.models) == 1
    assert panel.models[0].native_max_tokens == DEFAULT_NATIVE_MAX_TOKENS


def test_dump_resolved_writes_yaml_and_creates_parent_dirs(tmp_path: Path) -> None:
    catalog = _sample_catalog()
    criteria = PanelCriteria(
        panel_id="for_dump",
        rationale="dump test",
        context_length_min=8000,
        exclude_patterns=[],
        candidates=[
            CandidateModel(
                id="anthropic/claude-haiku-4-5",
                family="anthropic-haiku",
                size_tier="small",
                cost_tier="frontier-cheap",
            )
        ],
    )
    panel = resolve_panel(criteria, catalog, resolved_at=datetime(2026, 5, 12, 15, 0, tzinfo=UTC))

    out_path = tmp_path / "nested" / "dir" / "panel.resolved.yaml"
    dump_resolved(panel, out_path)

    assert out_path.exists()
    doc = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert doc["panel_id"] == "for_dump"
    assert doc["catalog_snapshot_sha"] == panel.catalog_snapshot_sha
    assert doc["resolved_at"].startswith("2026-05-12T15:00:00")
    assert [m["id"] for m in doc["models"]] == ["anthropic/claude-haiku-4-5"]
