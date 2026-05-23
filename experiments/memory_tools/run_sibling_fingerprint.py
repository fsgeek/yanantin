"""Sibling-fingerprint probe (run_012) — 2026-05-23

Exploratory probe (NOT pre-registered). Extends run_011 / Finding 10.

Finding 10 established that the function-name identifier-shape parser is
model-specific: Mistral scans every shape, Gemini only snake_case,
GPT-OSS-20B snake+camel-but-not-hyphen-or-buried, Claude doesn't apply
the parser at all. That characterization rests on *one model per lab*.

Question this probe asks: is the shape-parser a **lab signature** or a
**per-model quirk**? If same-lab siblings share a parser fingerprint,
the parser de-anonymizes a model behind a router. If siblings diverge,
the "fingerprint-level / lab signature" framing in the run_011 abstract
is undercut by data from the same harness.

Reuses `build_separator_probe_variants()` verbatim (10 variants:
5 function-name shapes carrying the `delete` morpheme x rich/contradicting
descriptions). The only change from run_011 is the model list.

Panel = anchors (one characterized model per lab, to re-confirm the
fingerprint in-run) + siblings (same lab, different size/product line)
+ deepseek-v4-flash (a lab never characterized on this axis):

  OpenAI    gpt-oss-20b   (anchor: snake+camel)  | gpt-oss-120b (sibling, 6x size)
  Qwen      qwen3-32b     (anchor: terse-skip)   | qwen3.5-9b, qwen3-coder-30b
  Google    gemini-2.5-flash-lite (anchor: snake-only) | gemma-4-31b (same org, open-weights line)
  Mistral   mistral-small-3.2 (anchor: uniform scan)
  Anthropic claude-haiku-4.5 (anchor: no parser)
  DeepSeek  deepseek-v4-flash (uncharacterized)

10 models x 10 variants x 3 prompts = 300 turn-0 cells. Budget cap $0.40
(run_011 was $0.100 / 150 cells; the two larger models push this up but
nowhere near the cap).

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


# Anchors (characterized in run_011) interleaved with same-lab siblings.
SIBLING_PANEL_IDS = [
    # OpenAI gpt-oss: the key pair. 20b = snake+camel-not-hyphen-not-buried.
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    # Qwen: anchor terse-skip + two siblings (one code-trained).
    "qwen/qwen3-32b",
    "qwen/qwen3.5-9b",
    "qwen/qwen3-coder-30b-a3b-instruct",
    # Google: Gemini anchor (snake-only) vs Gemma open-weights line.
    "google/gemini-2.5-flash-lite",
    "google/gemma-4-31b-it",
    # Single-model anchors.
    "mistralai/mistral-small-3.2-24b-instruct",  # uniform scan
    "anthropic/claude-haiku-4.5",                # no parser
    # New lab, never characterized on the shape axis.
    "deepseek/deepseek-v4-flash",
]

PANEL_PATH = ROOT / "experiments/memory_tools/panels/iteration_v1.resolved.yaml"
PROMPT_DIR = ROOT / "experiments/memory_tools/prompts"
OUT_DIR = ROOT / "experiments/memory_tools/name_effect_v1"


def out_path(run_id: str) -> Path:
    # Pass a run_id on the CLI to write a replication file, e.g.
    #   python run_sibling_fingerprint.py run_012b_sibling_fingerprint_rep
    # Default is the original run_012. Temperature is 0.7, so a second
    # run gives an independent sample; pool both to lift n=3 -> n=6.
    return OUT_DIR / f"{run_id}.jsonl"


def load_sibling_panel() -> list[ResolvedModel]:
    panel_data = yaml.safe_load(PANEL_PATH.read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in panel_data["models"]}
    out: list[ResolvedModel] = []
    missing: list[str] = []
    for mid in SIBLING_PANEL_IDS:
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

    run_id = sys.argv[1] if len(sys.argv) > 1 else "run_012_sibling_fingerprint"
    OUT_PATH = out_path(run_id)

    apacheta = yanantin.apacheta.connect(tier="test")

    s7 = apacheta.query_open_by_author_instance("scout-7", limit=5)
    s9 = apacheta.query_open_by_author_instance("scout-9", limit=5)
    if not s7 or not s9:
        raise SystemExit(
            "apacheta_test missing scout-7 / scout-9 seed records. "
            "Run: uv run pytest tests/experiments/test_name_effect_smoke.py to seed."
        )

    models = load_sibling_panel()
    variants = build_separator_probe_variants()
    prompts = [
        load_template(PROMPT_DIR / "find_a_record.yaml"),
        load_template(PROMPT_DIR / "find_by_lineage.yaml"),
        load_template(PROMPT_DIR / "find_by_author.yaml"),
    ]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg = RunnerConfig(
        experiment_id="sibling_fingerprint",
        panel_id="iteration_v1_sibling_subset",
        capture_dir=OUT_PATH.parent,
        run_id=OUT_PATH.stem,
        cost_ceiling_usd=0.40,
        max_turns=4,
        query_budget_per_task=6,
        max_tokens=4096,
        x_title="yanantin:memtool:sibling",
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
