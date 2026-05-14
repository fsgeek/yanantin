"""Parameter-name probe — 2026-05-14

Exploratory probe (NOT pre-registered). Tests whether Finding 5's
substring-extraction mechanism operates on parameter identifiers, not
just function-name identifiers.

Held constant:
  - function name: `find_objects`             (aligned English)
  - description:    rich/aligned              (the production description,
                                              auto-rendered with the
                                              parameter name in place)
  - prompts:        the three name-effect prompts (find_a_record,
                                              find_by_lineage,
                                              find_by_author)
  - panel:          strong-five subset of iteration_v1

Varied:
  - top-level filter-container parameter name:
      * matching           (neutral baseline)
      * criteria_to_delete (destructive substring `delete`)
      * records_to_purge   (destructive substring `purge`)
      * query_spec         (clean alternative)

Cells: 5 models × 4 variants × 3 prompts = 60 turn-0 calls.
Budget cap: $0.20 (~3× the cost of run_007 at $0.057).

Reads OPENROUTER_API_KEY from env. Expects apacheta_test to already be
seeded with scout-7 and scout-9 records (the name-effect smoke test
seeds idempotently; re-run it once if the store is empty).
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

import yanantin.apacheta
from yanantin.apacheta.clients.openrouter import OpenRouterClient
from yanantin.experiments.panel import ResolvedModel
from yanantin.experiments.prompts import load_template
from yanantin.experiments.runner import RunnerConfig, run_experiment
from yanantin.experiments.tools.registry import build_param_name_probe_variants


STRONG_FIVE_IDS = [
    "anthropic/claude-haiku-4.5",
    "google/gemini-2.5-flash-lite",
    "mistralai/mistral-small-3.2-24b-instruct",
    "qwen/qwen3-32b",
    "openai/gpt-oss-20b",
]

OUT_PATH = ROOT / "experiments/memory_tools/name_effect_v1/run_008_param_name.jsonl"
PANEL_PATH = ROOT / "experiments/memory_tools/panels/iteration_v1.resolved.yaml"
PROMPT_DIR = ROOT / "experiments/memory_tools/prompts"


def load_strong_five() -> list[ResolvedModel]:
    panel_data = yaml.safe_load(PANEL_PATH.read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in panel_data["models"]}
    out: list[ResolvedModel] = []
    missing: list[str] = []
    for mid in STRONG_FIVE_IDS:
        if mid in by_id:
            out.append(ResolvedModel.model_validate(by_id[mid]))
        else:
            missing.append(mid)
    if missing:
        raise RuntimeError(f"missing from resolved panel: {missing}")
    return out


async def main() -> Path:
    if "OPENROUTER_API_KEY" not in os.environ:
        raise SystemExit("OPENROUTER_API_KEY not set")

    apacheta = yanantin.apacheta.connect(tier="test")

    # Sanity-check seeding (don't reseed — assume the smoke test or a
    # prior run has populated apacheta_test).
    s7 = apacheta.query_open_by_author_instance("scout-7", limit=5)
    s9 = apacheta.query_open_by_author_instance("scout-9", limit=5)
    if not s7 or not s9:
        raise SystemExit(
            "apacheta_test missing scout-7 / scout-9 seed records. "
            "Run: uv run pytest tests/experiments/test_name_effect_smoke.py "
            "to seed."
        )

    models = load_strong_five()
    variants = build_param_name_probe_variants()
    prompts = [
        load_template(PROMPT_DIR / "find_a_record.yaml"),
        load_template(PROMPT_DIR / "find_by_lineage.yaml"),
        load_template(PROMPT_DIR / "find_by_author.yaml"),
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg = RunnerConfig(
        experiment_id="param_name_probe",
        panel_id="iteration_v1_strong_subset",
        capture_dir=OUT_PATH.parent,
        run_id=OUT_PATH.stem,
        cost_ceiling_usd=0.20,
        max_turns=4,
        query_budget_per_task=6,
        max_tokens=4096,
        x_title="yanantin:memtool:param-name",
    )

    print(f"models={len(models)} variants={len(variants)} prompts={len(prompts)}")
    print(f"expected cells: {len(models) * len(variants) * len(prompts)}")
    print(f"writing to: {OUT_PATH}")

    async with OpenRouterClient() as client:
        out_path = await run_experiment(
            cfg,
            apacheta,
            client,
            models,
            variants,
            prompts,
        )

    print(f"done: {out_path}")
    return out_path


if __name__ == "__main__":
    asyncio.run(main())
