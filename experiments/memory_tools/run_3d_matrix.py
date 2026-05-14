"""Verb × description × slot 3D matrix — 2026-05-14

Exploratory probe (NOT pre-registered). Crosses the verb-severity
gradient (run_009) with the description-degradation axis (run_004),
at both identifier slots (Finding 7 / run_008).

Axes:
  - Verb (8 levels):
      find, retrieve, fetch, extract, remove, delete, purge, destroy
  - Description (3 states):
      rich          (the production find-flavored description)
      empty         (single period — semantically empty)
      contradicting (write-flavored description; cue conflict)
  - Slot (2):
      fn    — function name varies, parameter held at `matching`
      param — function held at `find_objects`, parameter varies as `{verb}_criteria`

Total: 8 × 3 × 2 = 48 variants. On strong-five panel × 3 prompts =
720 turn-0 cells. Budget cap: $0.60. ~$0.45 expected based on
run_009's per-cell rate.

Hypothesis: under *degraded* descriptions, the verb-severity gradient
should surface a Gemini veto threshold somewhere on the function-name
slot — since description no longer dominates and substring-extraction
becomes the operative signal. Whether the parameter-name slot also
shows a threshold under degradation distinguishes interpretation (a)
("function-name slot is structurally privileged") from (b) ("rich
descriptions just dominated; param-slot vetoes hide until descriptions
degrade") in Finding 7.

Reads OPENROUTER_API_KEY from env. Expects apacheta_test seeded with
scout-7 and scout-9 records.
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
from yanantin.experiments.tools.registry import build_verb_x_description_x_slot_variants


STRONG_FIVE_IDS = [
    "anthropic/claude-haiku-4.5",
    "google/gemini-2.5-flash-lite",
    "mistralai/mistral-small-3.2-24b-instruct",
    "qwen/qwen3-32b",
    "openai/gpt-oss-20b",
]

OUT_PATH = ROOT / "experiments/memory_tools/name_effect_v1/run_010_3d_matrix.jsonl"
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
    variants = build_verb_x_description_x_slot_variants()
    prompts = [
        load_template(PROMPT_DIR / "find_a_record.yaml"),
        load_template(PROMPT_DIR / "find_by_lineage.yaml"),
        load_template(PROMPT_DIR / "find_by_author.yaml"),
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg = RunnerConfig(
        experiment_id="verb_x_description_x_slot",
        panel_id="iteration_v1_strong_subset",
        capture_dir=OUT_PATH.parent,
        run_id=OUT_PATH.stem,
        cost_ceiling_usd=0.60,
        max_turns=4,
        query_budget_per_task=6,
        max_tokens=4096,
        x_title="yanantin:memtool:3d",
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
