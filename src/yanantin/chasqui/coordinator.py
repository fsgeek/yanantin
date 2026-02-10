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
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yanantin.apacheta.clients.openrouter import OpenRouterClient
from yanantin.chasqui.model_selector import ModelInfo, ModelSelector
from yanantin.chasqui.scout import format_respond_prompt, format_scout_prompt, scout_metadata


# ── Configuration ────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src/yanantin/chasqui -> project root
CAIRN_DIR = PROJECT_ROOT / "docs" / "cairn"

# Models that can't follow complex instructions well enough for scouting
DEFAULT_EXCLUDE = [
    "openrouter/auto",  # Meta-router, not a real model
]

# ── Cairn writer ─────────────────────────────────────────────────────

def _claim_scout_number(cairn_dir: Path, model_short: str) -> tuple[int, Path]:
    """Claim a unique scout run number using filesystem atomicity.

    Lamport's bakery on POSIX: try to create a file with O_CREAT|O_EXCL.
    If it exists, take the next ticket. Safe across processes.

    Returns (run_number, claimed_path).
    """
    cairn_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

    # Find the high-water mark to start from
    existing = list(cairn_dir.glob("scout_*.md"))
    numbers = []
    for f in existing:
        match = re.search(r"scout_(\d+)", f.name)
        if match:
            numbers.append(int(match.group(1)))
    candidate = max(numbers, default=0) + 1

    # Bakery loop: try to claim this number atomically
    while True:
        filename = f"scout_{candidate:04d}_{date_str}_{model_short}.md"
        path = cairn_dir / filename
        try:
            # O_CREAT | O_EXCL: atomic create-if-not-exists
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(fd)
            return candidate, path
        except FileExistsError:
            candidate += 1


def write_to_cairn(
    content: str,
    model: ModelInfo,
    usage: dict[str, Any],
    cairn_dir: Path = CAIRN_DIR,
) -> tuple[int, Path]:
    """Claim a run number and write a scout's tensor to the cairn.

    Uses filesystem-atomic numbering (Lamport bakery on POSIX) to ensure
    unique run numbers even across concurrent processes.

    Returns (run_number, path).
    """
    model_short = model.id.split("/")[-1][:30].replace(" ", "_")
    run_number, path = _claim_scout_number(cairn_dir, model_short)

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
    return run_number, path


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
        loaded_count = selector.load_from_openrouter_response(models_data)

        if loaded_count == 0:
            return {"error": "No models available after filtering"}

        model = selector.select()

        # 3. Build prompt (run_number=0 placeholder — real number assigned at write)
        system_prompt, messages = format_scout_prompt(
            model=model,
            root=project_root,
            run_number=0,
        )

        # 4. Dispatch
        metadata = scout_metadata(model, 0)
        response = await client.complete(
            model=model.id,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata,
        )

        # 5. Write to cairn — number claimed atomically here
        run_number, path = write_to_cairn(
            content=response.content,
            model=model,
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
            "pool_size": loaded_count,
            "pool_stats": selector.stats(),
        }


async def dispatch_respond(
    tensor_path: str | Path,
    cairn_dir: Path = CAIRN_DIR,
    project_root: Path = PROJECT_ROOT,
    exclude_patterns: list[str] | None = None,
    seed: int | None = None,
    max_tokens: int = 4000,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Dispatch a messenger to respond to a previous scout's tensor.

    The cairn is the mailbox. The coordinator is the postal service.
    The tensors are the letters.

    Args:
        tensor_path: Path to the scout tensor to respond to.
    """
    tensor_path = Path(tensor_path)
    if not tensor_path.exists():
        return {"error": f"Tensor not found: {tensor_path}"}

    tensor_content = tensor_path.read_text(encoding="utf-8")

    # Extract the previous model from the provenance header
    model_match = re.search(r"Model:\s*(\S+)", tensor_content)
    previous_model = model_match.group(1) if model_match else "unknown"

    exclude = exclude_patterns or DEFAULT_EXCLUDE

    async with OpenRouterClient() as client:
        models_data = await client.list_models()

        selector = ModelSelector(
            min_context_length=8_000,
            exclude_patterns=exclude,
        )
        if seed is not None:
            selector.seed(seed)
        loaded_count = selector.load_from_openrouter_response(models_data)

        if loaded_count == 0:
            return {"error": "No models available after filtering"}

        model = selector.select()

        system_prompt, messages = format_respond_prompt(
            model=model,
            previous_tensor_content=tensor_content,
            previous_model_id=previous_model,
            root=project_root,
        )

        metadata = scout_metadata(model, 0, mode="respond")
        response = await client.complete(
            model=model.id,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata,
        )

        run_number, path = write_to_cairn(
            content=response.content,
            model=model,
            usage=response.usage,
            cairn_dir=cairn_dir,
        )

        return {
            "mode": "respond",
            "responding_to": str(tensor_path),
            "previous_model": previous_model,
            "model": model.id,
            "model_name": model.name,
            "cost_per_million": model.total_cost_per_million,
            "run_number": run_number,
            "cairn_path": str(path),
            "content_length": len(response.content),
            "usage": response.usage,
            "pool_size": loaded_count,
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
