"""affordance_absence_v1 — does cultivating request_capability convert
capability-fabrication into an honest gap declaration?

Pre-registered (see experiments/memory_tools/affordance_absence_v1/
preregistration.yaml, OTS-stamped before data). 2x2: tool surface
{control, with_request_capability} x system prompt {thin, cultivation}.
The runner fixes one system prompt per run, so cultivation is selected
on the CLI; the two surfaces are both swept within a run via the two
ToolVariants.

  python run_affordance_absence.py <run_id> <thin|cultivation>

e.g.
  python run_affordance_absence.py affordance_absence_v1_thin_a       thin
  python run_affordance_absence.py affordance_absence_v1_cult_a       cultivation

Reads OPENROUTER_API_KEY from env. Expects apacheta_test seeded.
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
from yanantin.experiments.runner import DEFAULT_SYSTEM_PROMPT, RunnerConfig, run_experiment
from yanantin.experiments.tools.affordance import CULTIVATION_SYSTEM_PROMPT
from yanantin.experiments.tools.registry import build_affordance_absence_variants

PANEL_PATH = ROOT / "experiments/memory_tools/panels/affordance_v1.resolved.yaml"
PROMPT_DIR = ROOT / "experiments/memory_tools/prompts"
OUT_DIR = ROOT / "experiments/memory_tools/affordance_absence_v1"

SYSTEM_PROMPTS = {"thin": DEFAULT_SYSTEM_PROMPT, "cultivation": CULTIVATION_SYSTEM_PROMPT}


def load_panel() -> list[ResolvedModel]:
    data = yaml.safe_load(PANEL_PATH.read_text(encoding="utf-8"))
    return [ResolvedModel.model_validate(m) for m in data["models"]]


async def main() -> Path:
    if "OPENROUTER_API_KEY" not in os.environ:
        raise SystemExit("OPENROUTER_API_KEY not set")
    if len(sys.argv) < 3 or sys.argv[2] not in SYSTEM_PROMPTS:
        raise SystemExit("usage: run_affordance_absence.py <run_id> <thin|cultivation>")

    run_id, sp_choice = sys.argv[1], sys.argv[2]
    out_path = OUT_DIR / f"{run_id}.jsonl"

    apacheta = yanantin.apacheta.connect(tier="test")
    if not apacheta.query_open_by_author_instance("scout-7", limit=1):
        raise SystemExit(
            "apacheta_test missing scout-7 seed. Run: "
            "uv run pytest tests/experiments/test_name_effect_smoke.py to seed."
        )

    models = load_panel()
    variants = build_affordance_absence_variants()
    prompts = [
        load_template(PROMPT_DIR / "forget_a_record.yaml"),
        load_template(PROMPT_DIR / "update_a_record.yaml"),
        load_template(PROMPT_DIR / "store_a_record.yaml"),
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = RunnerConfig(
        experiment_id="affordance_absence_v1",
        panel_id="affordance_v1",
        capture_dir=out_path.parent,
        run_id=out_path.stem,
        cost_ceiling_usd=0.50,
        max_turns=4,
        query_budget_per_task=6,
        max_tokens=4096,
        x_title=f"yanantin:memtool:afford:{sp_choice}",
        system_prompt=SYSTEM_PROMPTS[sp_choice],
    )

    print(f"system_prompt={sp_choice} models={len(models)} variants={len(variants)} prompts={len(prompts)}")
    print(f"expected tasks: {len(models) * len(variants) * len(prompts)}")
    print(f"writing to: {out_path}")

    async with OpenRouterClient() as client:
        result = await run_experiment(cfg, apacheta, client, models, variants, prompts)

    print(f"done: {result}")
    return result


if __name__ == "__main__":
    asyncio.run(main())
