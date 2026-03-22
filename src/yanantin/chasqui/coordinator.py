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
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
import logging

from yanantin.apacheta.clients.openrouter import OpenRouterClient, OpenRouterResponse
from yanantin.chasqui.model_selector import ModelInfo, ModelSelector
from yanantin.chasqui.scout import (
    format_respond_prompt,
    format_scout_prompt,
    format_verify_prompt,
    scout_metadata,
)
from yanantin.chasqui.scourer import VALID_SCOPES, format_scour_prompt

logger = logging.getLogger(__name__)


# ── Activity map ─────────────────────────────────────────────────────

def _build_activity_map(project_root: Path) -> dict[str, datetime] | None:
    """Query the activity stream for recently-observed file state.

    Returns {relative_path: last_modified_datetime} from the DuckDB
    activity store, or None if the store doesn't exist or imports fail.
    Graceful degradation: this is additive signal, not required.
    """
    try:
        from yanantin.collector.pipeline import open_store
        from yanantin.query.engine import QueryEngine
        from yanantin.query.models import QuerySpec
    except ImportError:
        return None

    db_path = Path.home() / ".local" / "share" / "yanantin" / "activity.duckdb"
    if not db_path.exists():
        return None

    try:
        store = open_store("duckdb")
        engine = QueryEngine(store)

        # Query all facts — we want the full file inventory with timestamps.
        spec = QuerySpec(limit=10000)
        result = engine.execute(spec)
    except Exception:
        logger.debug("Activity map: failed to query DuckDB store", exc_info=True)
        return None

    activity_map: dict[str, datetime] = {}
    for fact in result.facts:
        data = fact.get("data", {})
        path = data.get("path", "")
        if not path:
            continue

        # Extract mtime from fact data timestamps
        timestamps = data.get("timestamps", {})
        mtime_str = timestamps.get("modified") or timestamps.get("mtime")
        if mtime_str:
            try:
                mtime = datetime.fromisoformat(mtime_str)
            except (ValueError, TypeError):
                continue
        else:
            # Fall back to fact timestamp (collection time)
            try:
                mtime = datetime.fromisoformat(fact["timestamp"])
            except (ValueError, TypeError, KeyError):
                continue

        # Make timezone-aware if naive
        if mtime.tzinfo is None:
            mtime = mtime.replace(tzinfo=timezone.utc)

        # Convert to relative path
        try:
            rel = str(Path(path).relative_to(project_root))
        except ValueError:
            continue

        # Keep the most recent observation per file
        if rel not in activity_map or mtime > activity_map[rel]:
            activity_map[rel] = mtime

    return activity_map if activity_map else None


# ── Configuration ────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src/yanantin/chasqui -> project root
CAIRN_DIR = PROJECT_ROOT / "docs" / "cairn"

# Models that can't follow complex instructions well enough for scouting
DEFAULT_EXCLUDE = [
    "openrouter/auto",  # Meta-router, not a real model
]

# ── Garbage detection ────────────────────────────────────────────────

def _is_degenerate_repetition(text: str, phrase_len: int = 40, threshold: int = 5) -> bool:
    """Detect degenerate repetition loops in model output.

    A model stuck in a loop repeats the same phrase hundreds of times.
    The verdict keyword may appear once at the start, making the garbage
    parse as CONFIRMED or DENIED. This catches that.

    Returns True if any substring of `phrase_len` chars repeats
    `threshold` or more times in the text.
    """
    if len(text) < phrase_len * threshold:
        return False
    # Sample phrases from the middle of the text (avoid header/footer)
    mid = len(text) // 2
    for offset in range(0, min(200, mid), 20):
        phrase = text[mid + offset : mid + offset + phrase_len]
        if len(phrase) < phrase_len:
            break
        if text.count(phrase) >= threshold:
            return True
    return False


# ── Verification dedup ───────────────────────────────────────────────

# Maximum number of verification reports for the same (file, model) pair
# before we stop dispatching more.  Three is enough to establish consensus
# without feeding a cascade when a confused claim keeps getting re-verified.
MAX_VERIFY_PER_CLAIM = 3


def _count_prior_verifications(cairn_dir: Path) -> Counter[tuple[str, str]]:
    """Count existing verification reports per (ClaimFile, ClaimBy) pair.

    Scans scout reports that carry ``Dispatch: verify`` provenance for
    their ClaimFile and ClaimBy fields.  Returns a Counter keyed by
    (claim_file, claim_by) so callers can check whether a claim has
    already been verified enough times.

    This is intentionally simple — regex on provenance headers, no full
    parse.  It needs to be fast because it runs before every verification
    batch.
    """
    counts: Counter[tuple[str, str]] = Counter()
    if not cairn_dir.is_dir():
        return counts

    _dispatch_re = re.compile(r"Dispatch:\s*verify", re.IGNORECASE)
    _file_re = re.compile(r"ClaimFile:\s*(.+)")
    _by_re = re.compile(r"ClaimBy:\s*(.+)")

    for path in cairn_dir.glob("scout_*.md"):
        try:
            # Only read the header — 1500 bytes covers the longest observed
            # provenance block (1144 bytes with long Claim text).
            with open(path, "r", encoding="utf-8") as f:
                header = f.read(1500)
        except OSError:
            continue

        if not _dispatch_re.search(header):
            continue

        file_match = _file_re.search(header)
        by_match = _by_re.search(header)
        if file_match and by_match:
            key = (file_match.group(1).strip(), by_match.group(1).strip())
            counts[key] += 1

    return counts


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
    dispatch_context: dict[str, str] | None = None,
) -> tuple[int, Path]:
    """Claim a run number and write a scout's tensor to the cairn.

    Uses filesystem-atomic numbering (Lamport bakery on POSIX) to ensure
    unique run numbers even across concurrent processes.

    dispatch_context: optional provenance fields written into the header.
    When the chef dies (process ends, stdout truncates), the report itself
    must carry enough context to reconstruct why it was dispatched.

    Returns (run_number, path).
    """
    model_short = model.id.split("/")[-1][:30].replace(" ", "_")
    run_number, path = _claim_scout_number(cairn_dir, model_short)

    # Build optional dispatch provenance lines
    context_lines = ""
    if dispatch_context:
        for key, value in dispatch_context.items():
            # Truncate long values but keep them useful
            display = value[:200] if len(value) > 200 else value
            context_lines += f"     {key}: {display}\n"

    # Wrap with provenance header
    header = f"""\
<!-- Chasqui Scout Tensor
     Run: {run_number}
     Model: {model.id} ({model.name})
     Cost: prompt=${model.prompt_cost}/M, completion=${model.completion_cost}/M
     Usage: {usage}
     Timestamp: {datetime.now(timezone.utc).isoformat()}
{context_lines}-->

"""
    path.write_text(header + content, encoding="utf-8")
    return run_number, path


# ── Scour cairn writer ───────────────────────────────────────────────

def _claim_scour_number(cairn_dir: Path, model_short: str) -> tuple[int, Path]:
    """Claim a unique scour run number using filesystem atomicity.

    Same Lamport bakery as scouts, but with scour_ prefix to keep
    the namespaces separate.

    Returns (run_number, claimed_path).
    """
    cairn_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")

    # Find the high-water mark from existing scour reports
    existing = list(cairn_dir.glob("scour_*.md"))
    numbers = []
    for f in existing:
        match = re.search(r"scour_(\d+)", f.name)
        if match:
            numbers.append(int(match.group(1)))
    candidate = max(numbers, default=0) + 1

    # Bakery loop: try to claim this number atomically
    while True:
        filename = f"scour_{candidate:04d}_{date_str}_{model_short}.md"
        path = cairn_dir / filename
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            os.close(fd)
            return candidate, path
        except FileExistsError:
            candidate += 1


def write_scour_to_cairn(
    content: str,
    model: ModelInfo,
    usage: dict[str, Any],
    target: str,
    scope: str,
    cairn_dir: Path = CAIRN_DIR,
) -> tuple[int, Path]:
    """Claim a run number and write a scourer's tensor to the cairn.

    Scour reports are named scour_NNNN_DATE_MODEL.md — distinct from
    scout reports so the two series don't collide.

    Returns (run_number, path).
    """
    model_short = model.id.split("/")[-1][:30].replace(" ", "_")
    run_number, path = _claim_scour_number(cairn_dir, model_short)

    header = f"""\
<!-- Chasqui Scour Tensor
     Run: {run_number}
     Model: {model.id} ({model.name})
     Target: {target}
     Scope: {scope}
     Cost: prompt=${model.prompt_cost}/M, completion=${model.completion_cost}/M
     Usage: {usage}
     Timestamp: {datetime.now(timezone.utc).isoformat()}
-->

"""
    path.write_text(header + content, encoding="utf-8")
    return run_number, path


# ── Retry helper ─────────────────────────────────────────────────────

MAX_DISPATCH_RETRIES = 3


async def _complete_with_retry(
    client: OpenRouterClient,
    selector: ModelSelector,
    build_prompt_fn: Callable[[ModelInfo], tuple[str, list[dict[str, str]]]],
    metadata_fn: Callable[[ModelInfo], dict[str, Any]],
    temperature: float = 0.7,
    max_tokens: int = 4000,
    max_retries: int = MAX_DISPATCH_RETRIES,
) -> tuple[ModelInfo, OpenRouterResponse]:
    """Select a model, build prompt, complete. Retry with a different model on HTTP error.

    On 400/404/500+, the failed model is removed from the selector's pool
    and a new model is selected. This handles models that have been removed
    from OpenRouter or that reject the prompt format.
    """
    last_error: Exception | None = None
    for attempt in range(max_retries):
        model = selector.select()
        system_prompt, messages = build_prompt_fn(model)
        metadata = metadata_fn(model)
        try:
            response = await client.complete(
                model=model.id,
                messages=[{"role": "system", "content": system_prompt}] + messages,
                temperature=temperature,
                max_tokens=max_tokens,
                metadata=metadata,
            )
            return model, response
        except httpx.HTTPStatusError as e:
            last_error = e
            logger.warning(
                "Model %s returned HTTP %d (attempt %d/%d), trying different model",
                model.id, e.response.status_code, attempt + 1, max_retries,
            )
            selector.models = [m for m in selector.models if m.id != model.id]
            if not selector.models:
                raise ValueError(f"No models remaining after {attempt + 1} failures") from e
    raise last_error  # type: ignore[misc]  # All retries exhausted


# ── Dispatch ─────────────────────────────────────────────────────────

async def dispatch_scour(
    target: str,
    scope: str = "introspection",
    cairn_dir: Path = CAIRN_DIR,
    project_root: Path = PROJECT_ROOT,
    exclude_patterns: list[str] | None = None,
    seed: int | None = None,
    max_tokens: int = 4000,
    temperature: float = 0.7,
) -> dict[str, Any]:
    """Dispatch a targeted scourer messenger.

    Unlike a scout that wanders freely, a scourer examines a specific
    target: a file, directory, tensor, or external codebase.

    Args:
        target: What to examine — a path or tensor spec.
        scope: One of "introspection", "external", "tensor".

    Returns a summary dict with model info, cost, path, and content length.
    """
    if scope not in VALID_SCOPES:
        return {"error": f"Invalid scope: {scope!r}. Must be one of {VALID_SCOPES}"}

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

        # 3. Build prompt factory for retry loop
        def _build_scour(m: ModelInfo) -> tuple[str, list[dict[str, str]]]:
            return format_scour_prompt(
                model=m, target=target, scope=scope,
                run_number=0, cairn_dir=cairn_dir,
            )

        try:
            _build_scour(selector.models[0])  # Validate target exists before retrying
        except (FileNotFoundError, ValueError) as e:
            return {"error": str(e)}

        # 4. Dispatch with retry on HTTP errors
        logger.info("Scourer dispatch: target=%r, scope=%s", target, scope)
        model, response = await _complete_with_retry(
            client, selector,
            build_prompt_fn=_build_scour,
            metadata_fn=lambda m: scout_metadata(m, 0, mode="scour"),
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # 5. Log raw response before parsing
        logger.info(
            "Scourer response: model=%s, content_length=%d, usage=%s",
            model.id, len(response.content), response.usage,
        )

        # 6. Write to cairn — number claimed atomically here
        run_number, path = write_scour_to_cairn(
            content=response.content,
            model=model,
            usage=response.usage,
            target=target,
            scope=scope,
            cairn_dir=cairn_dir,
        )

        return {
            "mode": "scour",
            "target": target,
            "scope": scope,
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


async def dispatch_scout(
    cairn_dir: Path = CAIRN_DIR,
    project_root: Path = PROJECT_ROOT,
    exclude_patterns: list[str] | None = None,
    seed: int | None = None,
    max_tokens: int = 4000,
    temperature: float = 0.7,
    use_coverage: bool = True,
) -> dict[str, Any]:
    """Dispatch a single scout messenger.

    1. Pull available models from OpenRouter
    2. Select one by inverse-cost weighting
    3. Build a scout prompt with coverage-weighted file selection
    4. Send the messenger
    5. Write the tensor to the cairn

    When use_coverage is True (default), file selection is weighted by
    coverage freshness: files never reviewed start at epoch 0 (maximum
    priority). Recently reviewed files still have some chance but lower
    weight. This is the watchman — it ensures new code gets reviewed.

    Returns a summary dict with model info, cost, path, and content length.
    """
    exclude = exclude_patterns or DEFAULT_EXCLUDE

    # Build coverage map if the cairn exists — the watchman
    cov_map = None
    if use_coverage and cairn_dir.is_dir():
        from yanantin.chasqui.coverage import scan_cairn_coverage
        cov_map = scan_cairn_coverage(cairn_dir)

    # Build activity map if DuckDB store exists — disk change signal
    act_map = _build_activity_map(project_root)

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

        # 3. Dispatch with retry on HTTP errors
        model, response = await _complete_with_retry(
            client, selector,
            build_prompt_fn=lambda m: format_scout_prompt(
                model=m, root=project_root, run_number=0,
                coverage_map=cov_map,
                activity_map=act_map,
            ),
            metadata_fn=lambda m: scout_metadata(m, 0),
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # 4. Write to cairn — number claimed atomically here
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

        model, response = await _complete_with_retry(
            client, selector,
            build_prompt_fn=lambda m: format_respond_prompt(
                model=m, previous_tensor_content=tensor_content,
                previous_model_id=previous_model, root=project_root,
            ),
            metadata_fn=lambda m: scout_metadata(m, 0, mode="respond"),
            temperature=temperature,
            max_tokens=max_tokens,
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


def _record_verification_edge(result: dict[str, Any], cairn_dir: Path) -> None:
    """Record a verification verdict as a cairn edge.

    Creates a lightweight JSON edge linking the verification report
    to the original scout report, with claim details as properties.
    Edges are stored in docs/cairn/edges/ — files on disk, ingestible
    later into Apacheta as CompositionEdges.

    Only called for CONFIRMED or DENIED verdicts. INDETERMINATE is
    not an edge — it's the absence of one.
    """
    import json
    from uuid import uuid4

    edges_dir = cairn_dir / "edges"
    edges_dir.mkdir(exist_ok=True)

    verdict = result["verdict"]
    relation = "confirms" if verdict == "CONFIRMED" else "denies"

    edge = {
        "id": str(uuid4()),
        "from_report": result["cairn_path"],
        "to_report": result["source_tensor"],
        "relation": relation,
        "claim_text": result["claim"],
        "claim_file": result["file_path"],
        "claim_by": result["source_model"],
        "verified_by": result["model"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Atomic write via rename
    edge_file = edges_dir / f"{relation}_{result['run_number']:04d}_{edge['id'][:8]}.json"
    tmp = edge_file.with_suffix(".tmp")
    tmp.write_text(json.dumps(edge, indent=2), encoding="utf-8")
    tmp.rename(edge_file)

    logger.info(
        "Verification edge: %s %s claim from %s about %s",
        result["model"], relation, result["source_model"], result["file_path"],
    )


async def dispatch_verify(
    claim_text: str,
    file_path: str,
    source_model: str,
    source_tensor: str,
    project_root: Path = PROJECT_ROOT,
    cairn_dir: Path = CAIRN_DIR,
    exclude_patterns: list[str] | None = None,
    seed: int | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """Dispatch a verification scout to check a specific claim.

    The judge gets the exact file referenced in the claim, not random files.
    Temperature is lower (0.3) because verification is precise work.

    Returns a summary dict with verdict, model info, and cairn path.
    """
    file_full_path = project_root / file_path
    if not file_full_path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        file_content = file_full_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        return {"error": f"Cannot read {file_path}: {e}"}

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

        model, response = await _complete_with_retry(
            client, selector,
            build_prompt_fn=lambda m: format_verify_prompt(
                model=m, claim_text=claim_text, file_path=file_path,
                file_content=file_content, source_model=source_model,
            ),
            metadata_fn=lambda m: scout_metadata(m, 0, mode="verify"),
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Write verification to cairn — with dispatch provenance
        run_number, path = write_to_cairn(
            content=response.content,
            model=model,
            usage=response.usage,
            cairn_dir=cairn_dir,
            dispatch_context={
                "Dispatch": "verify",
                "Claim": claim_text,
                "ClaimFile": file_path,
                "ClaimBy": source_model,
                "SourceTensor": source_tensor,
            },
        )

        # Detect degenerate repetition before trusting the verdict.
        # A model stuck in a loop produces garbage that may contain
        # verdict keywords by accident (scout 0983: 4000 tokens of
        # "it does mention" repeated, parsed as CONFIRMED).
        verdict = "INDETERMINATE"
        if _is_degenerate_repetition(response.content):
            verdict = "MODEL_FAILURE"
        else:
            content_upper = response.content.upper()
            if "**CONFIRMED**" in content_upper or "### VERDICT\nCONFIRMED" in content_upper:
                verdict = "CONFIRMED"
            elif "**DENIED**" in content_upper or "### VERDICT\nDENIED" in content_upper:
                verdict = "DENIED"

        result = {
            "mode": "verify",
            "verdict": verdict,
            "claim": claim_text,
            "file_path": file_path,
            "source_model": source_model,
            "source_tensor": source_tensor,
            "model": model.id,
            "model_name": model.name,
            "cost_per_million": model.total_cost_per_million,
            "run_number": run_number,
            "cairn_path": str(path),
            "content_length": len(response.content),
            "usage": response.usage,
            "pool_size": loaded_count,
        }

        # Record attestation receipt if Willay is available.
        # Attestation failure must never block verification.
        try:
            from yanantin.chasqui.attestation import record_verification

            record_verification(result)
        except ImportError:
            pass  # Willay not installed
        except Exception:
            pass  # Attestation failure never blocks verification

        # Record verification edge in the cairn.
        # Edge failure must never block verification.
        if verdict in ("CONFIRMED", "DENIED"):
            try:
                _record_verification_edge(result, cairn_dir)
            except Exception:
                pass  # Edge recording failure never blocks verification

        return result


async def dispatch_verify_cairn(
    cairn_dir: Path = CAIRN_DIR,
    project_root: Path = PROJECT_ROOT,
    max_claims: int = 5,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Extract claims from the cairn and dispatch verification scouts.

    Picks up to max_claims verifiable claims and sends a judge for each.
    """
    from yanantin.chasqui.scorer import extract_cairn_claims

    claims = extract_cairn_claims(cairn_dir, project_root)
    if not claims:
        return [{"error": "No verifiable claims found in cairn"}]

    # Dedup: skip claims that have already been verified enough times.
    # Without this, a confused claim (e.g. self-referential) that gets
    # DENIED triggers more verification, which triggers more DENIED,
    # creating a cascade.  See: 2990/9494 claims on predecessors.md.
    prior = _count_prior_verifications(cairn_dir)
    claims = [
        c for c in claims
        if prior[(c.file_path, c.source_model)] < MAX_VERIFY_PER_CLAIM
    ]
    if not claims:
        return [{"info": "All verifiable claims already at verification limit"}]

    # Select a sample of claims to verify
    import random
    selected = random.sample(claims, min(max_claims, len(claims)))

    tasks = [
        dispatch_verify(
            claim_text=c.claim_text,
            file_path=c.file_path,
            source_model=c.source_model,
            source_tensor=c.source_tensor,
            cairn_dir=cairn_dir,
            project_root=project_root,
            **kwargs,
        )
        for c in selected
    ]
    return await asyncio.gather(*tasks)


def resolve_file_reference(name: str, project_root: Path) -> str | None:
    """Resolve a bare filename to its project-relative path.

    Models often report bare filenames like 'scout.py' instead of
    'src/yanantin/chasqui/scout.py'. This searches the project tree
    to find the actual path.

    Args:
        name: Filename or path to resolve
        project_root: Project root directory

    Returns:
        Project-relative path if found, None if not found

    Strategy:
        1. If the path already exists as-is, return it unchanged
        2. Search project tree for files matching the bare name
        3. Skip .git/, __pycache__/, .venv/, node_modules/, .uv-cache/
        4. If exactly one match: return it
        5. If multiple: prefer src/ over others, then prefer shorter paths
        6. If none: return None
    """
    # First check if it already resolves
    if (project_root / name).exists():
        return name

    # Search the project tree
    skip_dirs = {".git", "__pycache__", ".venv", "node_modules", ".uv-cache", ".pytest_cache"}
    matches = []

    for dirpath, dirnames, filenames in os.walk(project_root):
        # Filter out skip_dirs in-place to avoid descending into them
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]

        if name in filenames:
            full_path = Path(dirpath) / name
            relative_path = full_path.relative_to(project_root)
            matches.append(str(relative_path))

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0]

    # Multiple matches: prefer src/ over others, then prefer shorter paths
    src_matches = [m for m in matches if m.startswith("src/")]
    if src_matches:
        return min(src_matches, key=len)
    return min(matches, key=len)


async def dispatch_investigate(
    cairn_dir: Path = CAIRN_DIR,
    project_root: Path = PROJECT_ROOT,
    max_questions: int = 5,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Investigate open questions surfaced by the analyst.

    Runs the analysis pipeline, picks the top N open questions, and
    dispatches verification scouts to check each one against the
    referenced file. Cost: ~$0.000014 × N per investigation.

    The analyst finds what consensus agrees on. This finds whether
    the things individual models noticed are real.
    """
    from yanantin.chasqui.analyst import analyze
    from yanantin.chasqui.gleaner import extract_claims_from_cairn

    claims = extract_claims_from_cairn(cairn_dir, pattern="scout_*.md", max_reports=2000)
    report = analyze(claims)

    if not report.open_questions:
        return [{"error": "No open questions found — analyst produced nothing to investigate"}]

    # Pick questions that have file references we can verify
    # Resolve bare filenames to project-relative paths first
    verifiable = []
    for q in report.open_questions:
        if not q.file_references:
            continue
        resolved_path = resolve_file_reference(q.file_references[0], project_root)
        if resolved_path and (project_root / resolved_path).exists():
            # Update the question's file reference with the resolved path
            q.file_references[0] = resolved_path
            verifiable.append(q)

    if not verifiable:
        return [{"error": f"No verifiable open questions (all {len(report.open_questions)} lack valid file refs)"}]

    # Dedup: skip questions whose (file, model) pair already has enough verifications
    prior = _count_prior_verifications(cairn_dir)
    verifiable = [
        q for q in verifiable
        if prior[(q.file_references[0], q.source_model)] < MAX_VERIFY_PER_CLAIM
    ]
    if not verifiable:
        return [{"info": "All open questions already at verification limit"}]

    selected = verifiable[:max_questions]

    tasks = [
        dispatch_verify(
            claim_text=q.claim_text,
            file_path=q.file_references[0],
            source_model=q.source_model,
            source_tensor="analyst-open-question",
            cairn_dir=cairn_dir,
            project_root=project_root,
            **kwargs,
        )
        for q in selected
    ]
    return await asyncio.gather(*tasks)


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
