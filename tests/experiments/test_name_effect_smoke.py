from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from pydantic import ConfigDict

import yanantin.apacheta
from yanantin.apacheta.clients.openrouter import OpenRouterClient
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.experiments.capture import load_run
from yanantin.experiments.panel import ResolvedModel
from yanantin.experiments.prompts import load_template
from yanantin.experiments.runner import RunnerConfig, run_experiment
from yanantin.experiments.tools.registry import build_name_effect_variants


class SmokeRecord(ApachetaBaseModel):
    model_config = ConfigDict(extra="allow")


@pytest.mark.integration
def test_name_effect_smoke(tmp_path: Path) -> None:
    if "OPENROUTER_API_KEY" not in os.environ:
        pytest.skip("no OPENROUTER_API_KEY")

    db_ini = Path("~/.yanantin/config/db.ini").expanduser()
    if not db_ini.exists():
        pytest.skip(f"missing Apacheta config: {db_ini}")

    try:
        apacheta = yanantin.apacheta.connect(tier="test")
    except (FileNotFoundError, ConnectionError) as exc:
        pytest.skip(f"apacheta test backend unavailable: {exc}")

    scout7_existing = apacheta.query_open_by_author_instance("scout-7", limit=10)
    scout9_existing = apacheta.query_open_by_author_instance("scout-9", limit=10)

    to_seed = [
        SmokeRecord(
            provenance={"author_instance_id": "scout-7"},
            lineage_tags=["iteration_v1", "smoke"],
            content="scout-7 smoke record",
        ),
        SmokeRecord(
            provenance={"author_instance_id": "scout-7"},
            lineage_tags=["iteration_v1"],
            content="scout-7 baseline record",
        ),
        SmokeRecord(
            provenance={"author_instance_id": "scout-9"},
            lineage_tags=["iteration_v1"],
            content="scout-9 baseline record",
        ),
    ]

    have_scout7 = len(scout7_existing)
    have_scout9 = len(scout9_existing)

    if have_scout7 == 0:
        apacheta.store_record(uuid4(), to_seed[0])
        have_scout7 += 1
    if have_scout7 <= 1:
        apacheta.store_record(uuid4(), to_seed[1])
        have_scout7 += 1
    if have_scout9 == 0:
        apacheta.store_record(uuid4(), to_seed[2])
        have_scout9 += 1

    scout7_after = apacheta.query_open_by_author_instance("scout-7", limit=10)
    scout9_after = apacheta.query_open_by_author_instance("scout-9", limit=10)
    assert len(scout7_after) >= 1
    assert len(scout9_after) >= 1

    panel_path = Path("experiments/memory_tools/panels/iteration_v1.resolved.yaml")
    panel_data = yaml.safe_load(panel_path.read_text(encoding="utf-8"))
    all_models = [ResolvedModel.model_validate(m) for m in panel_data["models"]]

    preferred_ids = [
        "google/gemini-2.5-flash-lite",
        "mistralai/mistral-small-3.2-24b-instruct",
        "openai/gpt-oss-20b",
    ]
    by_id = {m.id: m for m in all_models}

    selected: list[ResolvedModel] = []
    seen_tiers: set[str] = set()
    for model_id in preferred_ids:
        model = by_id.get(model_id)
        if model is not None and model.size_tier not in seen_tiers:
            selected.append(model)
            seen_tiers.add(model.size_tier)

    if not selected:
        for model in all_models:
            if model.size_tier in seen_tiers:
                continue
            selected.append(model)
            seen_tiers.add(model.size_tier)
            if len(selected) >= 4:
                break

    selected = selected[:4]
    if len(selected) < 2:
        pytest.skip("resolved panel did not provide enough models for smoke test")

    variants = build_name_effect_variants()
    prompts = [
        load_template("experiments/memory_tools/prompts/find_a_record.yaml"),
        load_template("experiments/memory_tools/prompts/find_by_lineage.yaml"),
        load_template("experiments/memory_tools/prompts/find_by_author.yaml"),
    ]

    cfg = RunnerConfig(
        experiment_id="name_effect_v1_smoke",
        panel_id="iteration_v1",
        capture_dir=tmp_path,
        run_id="smoke",
        cost_ceiling_usd=0.10,
        max_turns=3,
        query_budget_per_task=4,
        max_tokens=4096,
        x_title="yanantin:memtool:smoke",
    )

    async def _run() -> Path:
        async with OpenRouterClient() as client:
            return await run_experiment(
                cfg,
                apacheta,
                client,
                selected,
                variants,
                prompts,
            )

    out_path = asyncio.run(_run())
    records = load_run(out_path)

    assert len(records) >= 1

    variant_ids = {v.variant_id for v in variants}
    prompt_ids = {p.content_hash for p in prompts}
    task_counts: dict[str, int] = {}

    for rec in records:
        assert rec.experiment_id == "name_effect_v1_smoke"
        assert rec.panel_id == "iteration_v1"
        assert rec.tool_variant_id in variant_ids
        assert rec.status in {"ok", "error"}
        assert rec.prompt_template_id in prompt_ids

        task_id = rec.task_id
        task_counts[task_id] = task_counts.get(task_id, 0) + 1

    assert task_counts
    for task_id, count in task_counts.items():
        assert count >= 1, f"task {task_id} had no records"

    terminal_kinds = ["final_content", "http_error", "tool_error", "max_turns"]
    for variant_id in ["find_objects_v1", "search_v1", "query_v1"]:
        rows = [r for r in records if r.tool_variant_id == variant_id]
        counts = {
            k: sum(1 for r in rows if getattr(r, "terminated_by", None) == k)
            for k in terminal_kinds
        }
        print(
            f"variant={variant_id} final_content={counts['final_content']} "
            f"http_error={counts['http_error']} tool_error={counts['tool_error']} "
            f"max_turns={counts['max_turns']}"
        )
