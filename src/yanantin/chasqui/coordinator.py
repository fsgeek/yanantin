"""Chasqui Coordinator — the heartbeat of Yanantin.

Wake up the coordinator, and it dispatches messengers. Scouts wander
the codebase with randomly selected models, weighted inversely by cost.
Each scout produces a tensor that goes in the cairn.

Over time, the cairn accumulates data: which models notice what, at what
cost, and whether noticing more is worth paying more.

Usage::

    # From the command line
    uv run python -m yanantin.chasqui

    # Or from code
    import asyncio
    from yanantin.chasqui.coordinator import dispatch_scout
    result = asyncio.run(dispatch_scout())
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from itertools import count
from pathlib import Path
from typing import Any

from yanantin.apacheta.clients.openrouter import OpenRouterClient
from yanantin.chasqui.model_selector import ModelInfo, ModelSelector
from yanantin.chasqui.scout import format_scout_prompt, scout_metadata


# ── Configuration ────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src/yanantin/chasqui -> project root
CAIRN_DIR = PROJECT_ROOT / "docs" / "cairn"

# Models that can't follow complex instructions well enough for scouting
DEFAULT_EXCLUDE = [
    "openrouter/auto",  # Meta-router, not a real model
]

# Atomic counter for parallel dispatches — survives across calls within a process.
_run_counter: count | None = None


# ── Cairn writer ─────────────────────────────────────────────────────

def _next_scout_number(cairn_dir: Path) -> int:
    """Get the next scout run number, safe for parallel dispatches.

    On first call, scans the cairn directory to find the high-water mark.
    Subsequent calls increment atomically within the process.
    """
    global _run_counter
    if _run_counter is None:
        existing = list(cairn_dir.glob("scout_*.md"))
        numbers = []
        for f in existing:
            match = re.search(r"scout_(\d+)", f.name)
            if match:
                numbers.append(int(match.group(1)))
        start = max(numbers, default=0) + 1
        _run_counter = count(start)
    return next(_run_counter)


def write_to_cairn(
    content: str,
    model: ModelInfo,
    run_number: int,
    usage: dict[str, Any],
    cairn_dir: Path = CAIRN_DIR,
) -> Path:
    """Write a scout's tensor to the cairn.

    The filename encodes the run number, date, and model family.
    The content is the raw response — log before you parse.
    """
    cairn_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

    # Sanitize model name for filename
    model_short = model.id.split("/")[-1][:30].replace(" ", "_")
    filename = f"scout_{run_number:04d}_{date_str}_{model_short}.md"
    path = cairn_dir / filename

    # Wrap with provenance header
    header = f"""\
<!-- Chasqui Scout Tensor
     Run: {run_number}
     Model: {model.id} ({model.name})
     Cost: prompt=${model.prompt_cost}/M, completion=${model.completion_cost}/M
     Usage: {usage}
     Timestamp: {datetime.now(timezone.utc).isoformat()}
-->

"""
    path.write_text(header + content, encoding="utf-8")
    return path


# ── Dispatch ─────────────────────────────────────────────────────────

async def dispatch_scout(
    cairn_dir: Path = CAIRN_DIR,
    project_root: Path = PROJECT_ROOT,
    exclude_patterns: list[str] | None = None,
    seed: int | None = None,
    max_tokens: int = 4000,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Dispatch a single scout messenger.

    1. Pull available models from OpenRouter
    2. Select one by inverse-cost weighting
    3. Build a scout prompt with random file selection
    4. Send the messenger
    5. Write the tensor to the cairn

    Returns a summary dict with model info, cost, path, and content length.
    """
    exclude = exclude_patterns or DEFAULT_EXCLUDE

    async with OpenRouterClient() as client:
        # 1. Get available models
        models_data = await client.list_models()

        # 2. Build selector and pick
        selector = ModelSelector(
            min_context_length=8_000,
            exclude_patterns=exclude,
        )
        if seed is not None:
            selector.seed(seed)
        count = selector.load_from_openrouter_response(models_data)

        if count == 0:
            return {"error": "No models available after filtering"}

        model = selector.select()
        run_number = _next_scout_number(cairn_dir)

        # 3. Build prompt
        system_prompt, messages = format_scout_prompt(
            model=model,
            root=project_root,
            run_number=run_number,
        )

        # 4. Dispatch
        metadata = scout_metadata(model, run_number)
        response = await client.complete(
            model=model.id,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata,
        )

        # 5. Write to cairn
        path = write_to_cairn(
            content=response.content,
            model=model,
            run_number=run_number,
            usage=response.usage,
            cairn_dir=cairn_dir,
        )

        return {
            "model": model.id,
            "model_name": model.name,
            "cost_per_million": model.total_cost_per_million,
            "run_number": run_number,
            "cairn_path": str(path),
            "content_length": len(response.content),
            "usage": response.usage,
            "pool_size": count,
            "pool_stats": selector.stats(),
        }


async def dispatch_many(
    n: int = 3,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Dispatch multiple scouts in parallel.

    Each gets an independently selected model — you might get the same
    model twice, or three completely different ones. That's the point.
    """
    tasks = [dispatch_scout(**kwargs) for _ in range(n)]
    return await asyncio.gather(*tasks)
