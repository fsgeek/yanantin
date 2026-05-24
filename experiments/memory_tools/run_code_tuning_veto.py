"""code_tuning_veto_v1 — does code-tuning suppress the destructive-substring veto?

Pre-registered confirmatory probe (see
experiments/memory_tools/code_tuning_veto_v1/preregistration.yaml,
OTS-stamped before this data was collected).

Reuses build_separator_probe_variants() verbatim (5 destructive-`delete`
shapes x rich/contradicting). Runs the matched code/chat panel
(code_chat_v1.resolved.yaml). Protocol: run twice, pool to n=6/cell.

  python run_code_tuning_veto.py                 # -> run_a (3 prompts)
  python run_code_tuning_veto.py code_tuning_veto_v1_run_b  # -> run_b

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
from yanantin.experiments.runner import RunnerConfig, run_experiment
from yanantin.experiments.tools.registry import build_separator_probe_variants

PANEL_PATH = ROOT / "experiments/memory_tools/panels/code_chat_v1.resolved.yaml"
PROMPT_DIR = ROOT / "experiments/memory_tools/prompts"
OUT_DIR = ROOT / "experiments/memory_tools/code_tuning_veto_v1"


def load_panel() -> list[ResolvedModel]:
    data = yaml.safe_load(PANEL_PATH.read_text(encoding="utf-8"))
    return [ResolvedModel.model_validate(m) for m in data["models"]]


async def main() -> Path:
    if "OPENROUTER_API_KEY" not in os.environ:
        raise SystemExit("OPENROUTER_API_KEY not set")

    run_id = sys.argv[1] if len(sys.argv) > 1 else "code_tuning_veto_v1_run_a"
    out_path = OUT_DIR / f"{run_id}.jsonl"

    apacheta = yanantin.apacheta.connect(tier="test")
    s7 = apacheta.query_open_by_author_instance("scout-7", limit=5)
    s9 = apacheta.query_open_by_author_instance("scout-9", limit=5)
    if not s7 or not s9:
        raise SystemExit(
            "apacheta_test missing scout-7 / scout-9 seed records. "
            "Run: uv run pytest tests/experiments/test_name_effect_smoke.py to seed."
        )

    models = load_panel()
    variants = build_separator_probe_variants()
    prompts = [
        load_template(PROMPT_DIR / "find_a_record.yaml"),
        load_template(PROMPT_DIR / "find_by_lineage.yaml"),
        load_template(PROMPT_DIR / "find_by_author.yaml"),
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = RunnerConfig(
        experiment_id="code_tuning_veto_v1",
        panel_id="code_chat_v1",
        capture_dir=out_path.parent,
        run_id=out_path.stem,
        cost_ceiling_usd=0.80,
        max_turns=4,
        query_budget_per_task=6,
        max_tokens=4096,
        x_title="yanantin:memtool:codeveto",
    )

    print(f"models={len(models)} variants={len(variants)} prompts={len(prompts)}")
    print(f"expected cells: {len(models) * len(variants) * len(prompts)}")
    print(f"writing to: {out_path}")

    async with OpenRouterClient() as client:
        result = await run_experiment(cfg, apacheta, client, models, variants, prompts)

    print(f"done: {result}")
    return result


if __name__ == "__main__":
    asyncio.run(main())
