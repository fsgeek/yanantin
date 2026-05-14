"""Separator / shape conditionality probe — 2026-05-14

Exploratory probe (NOT pre-registered). Addresses Kimi's open item:
is the substring-extraction mechanism BPE-driven (any occurrence of
`delete` triggers the veto, regardless of separator/position) or
convention-driven (only snake_case verb_noun specifically)?

Five function-name shapes, all carrying the destructive `delete`
morpheme:
  - snake_case        delete_objects     (baseline; matches run_010's strongest veto cell)
  - camelCase         deleteObjects      (no separator; case boundary)
  - kebab-case        delete-objects     (different separator character)
  - verb_last         objects_delete     (positional reversal)
  - substring_buried  predelete_objects  (morpheme inside a longer compound)

× 2 description states (rich control, contradicting where run_010
showed the strongest function-name veto). Strong-five panel × 3
prompts = 150 turn-0 cells. Budget cap $0.15.

Function-name slot only. Parameter held at `matching`.

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


STRONG_FIVE_IDS = [
    "anthropic/claude-haiku-4.5",
    "google/gemini-2.5-flash-lite",
    "mistralai/mistral-small-3.2-24b-instruct",
    "qwen/qwen3-32b",
    "openai/gpt-oss-20b",
]

OUT_PATH = ROOT / "experiments/memory_tools/name_effect_v1/run_011_separator_probe.jsonl"
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

    s7 = apacheta.query_open_by_author_instance("scout-7", limit=5)
    s9 = apacheta.query_open_by_author_instance("scout-9", limit=5)
    if not s7 or not s9:
        raise SystemExit(
            "apacheta_test missing scout-7 / scout-9 seed records. "
            "Run: uv run pytest tests/experiments/test_name_effect_smoke.py to seed."
        )

    models = load_strong_five()
    variants = build_separator_probe_variants()
    prompts = [
        load_template(PROMPT_DIR / "find_a_record.yaml"),
        load_template(PROMPT_DIR / "find_by_lineage.yaml"),
        load_template(PROMPT_DIR / "find_by_author.yaml"),
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg = RunnerConfig(
        experiment_id="separator_conditionality",
        panel_id="iteration_v1_strong_subset",
        capture_dir=OUT_PATH.parent,
        run_id=OUT_PATH.stem,
        cost_ceiling_usd=0.15,
        max_turns=4,
        query_budget_per_task=6,
        max_tokens=4096,
        x_title="yanantin:memtool:separator",
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
