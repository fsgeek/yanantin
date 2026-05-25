"""Memory-tool harness runner.

Drives `(model × tool_variant × prompt) → CaptureRecord` over a bounded
agent loop. One CaptureRecord per LLM call; per-task UUID + turn index
tie a trajectory together. Termination reasons are recorded on the last
record of each task so post-hoc analysis can tell the difference between
"the model answered", "we ran out of turns", "the tool blew up", and
"OpenRouter said 400".

No SDK — talks to OpenRouter via the existing OpenRouterClient. Tool
implementations are plain Python callables from the variant registry.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from yanantin.apacheta.clients.openrouter import OpenRouterResponse
from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.experiments.budget import BudgetExceeded, CostBudget
from yanantin.experiments.capture import CaptureRecord, CaptureWriter
from yanantin.experiments.panel import ResolvedModel
from yanantin.experiments.prompts import PromptTemplate
from yanantin.experiments.tools.apacheta_tools import QueryBudget
from yanantin.experiments.tools.registry import ToolVariant


DEFAULT_SYSTEM_PROMPT = (
    "You are testing memory tools. Use the provided tool to answer the user's "
    "question. When you have the answer, respond with plain text — do not call "
    "the tool again."
)


@dataclass(frozen=True)
class RunnerConfig:
    experiment_id: str
    panel_id: str
    capture_dir: Path
    run_id: str
    cost_ceiling_usd: float
    max_turns: int = 6
    query_budget_per_task: int = 12
    per_call_timeout_s: float = 60.0
    max_tokens: int = 16384
    x_title: str = "yanantin:memtool"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT


def _model_id(model: ResolvedModel | str) -> str:
    """Accept either a ResolvedModel or a bare slug string."""
    return getattr(model, "id", model)


def _new_record(
    cfg: RunnerConfig,
    *,
    model_id: str,
    variant: ToolVariant,
    prompt: PromptTemplate,
    task_id: str,
    turn_idx: int,
    parent_record_id: str | None,
    request_full: dict[str, Any],
    response: OpenRouterResponse | None,
    elapsed_seconds: float,
    status: str,
    error_type: str | None = None,
    error_message: str | None = None,
    error_payload: str | None = None,
    terminated_by: str | None = None,
    tool_error_type: str | None = None,
    tool_error_message: str | None = None,
) -> CaptureRecord:
    if response is not None:
        response_parsed: dict[str, Any] | None = {
            "content": response.content,
            "tool_calls": response.tool_calls,
            "id": response.id,
            "model": response.model,
        }
        response_raw_body = json.dumps(response.raw)
        usage = response.usage
    else:
        response_parsed = None
        response_raw_body = None
        usage = {}

    # Always include these as extras (even when None) so consumers can
    # access them uniformly. Pydantic v2 'extra=allow' only exposes keys
    # that were actually set on construction; unset keys raise
    # AttributeError on access, which breaks downstream pattern-matching
    # ("did this record terminate?" must be a None check, not a hasattr).
    extra: dict[str, Any] = {
        "task_id": task_id,
        "turn_idx": turn_idx,
        "parent_record_id": parent_record_id,
        "terminated_by": terminated_by,
        "tool_error_type": tool_error_type,
        "tool_error_message": tool_error_message,
    }

    return CaptureRecord(
        record_id=str(uuid.uuid4()),
        timestamp=datetime.now(timezone.utc),
        experiment_id=cfg.experiment_id,
        panel_id=cfg.panel_id,
        tool_variant_id=variant.variant_id,
        model_id=model_id,
        prompt_template_id=prompt.content_hash,
        prompt_full=prompt.text,
        request_full=request_full,
        response_parsed=response_parsed,
        response_raw_body=response_raw_body,
        usage=usage,
        elapsed_seconds=elapsed_seconds,
        status=status,
        error_type=error_type,
        error_message=error_message,
        error_payload=error_payload,
        **extra,
    )


async def _run_task(
    cfg: RunnerConfig,
    client: Any,
    apacheta: ApachetaInterface,
    writer: CaptureWriter,
    budget: CostBudget,
    *,
    model_id: str,
    variant: ToolVariant,
    prompt: PromptTemplate,
) -> bool:
    """Run one (model, variant, prompt) task. Returns True to continue across tasks, False to stop."""
    task_id = str(uuid.uuid4())
    qbudget = QueryBudget(cfg.query_budget_per_task)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": cfg.system_prompt},
        {"role": "user", "content": prompt.text},
    ]

    prev_record_id: str | None = None
    for turn_idx in range(cfg.max_turns):
        if not budget.ok():
            return False

        surface = variant.all_schemas()
        request_full = {
            "model": model_id,
            "messages": list(messages),
            "tools": surface,
            "tool_choice": "auto",
            "max_tokens": cfg.max_tokens,
            "temperature": 0.7,
        }

        t0 = time.monotonic()
        try:
            response = await client.complete(
                model=model_id,
                messages=messages,
                tools=surface,
                tool_choice="auto",
                max_tokens=cfg.max_tokens,
                metadata={"X-Title": f"{cfg.x_title}:{cfg.experiment_id}"},
            )
            elapsed = time.monotonic() - t0
        except httpx.HTTPStatusError as e:
            elapsed = time.monotonic() - t0
            record = _new_record(
                cfg,
                model_id=model_id,
                variant=variant,
                prompt=prompt,
                task_id=task_id,
                turn_idx=turn_idx,
                parent_record_id=prev_record_id,
                request_full=request_full,
                response=None,
                elapsed_seconds=elapsed,
                status="error",
                error_type="HTTPStatusError",
                error_message=str(e),
                error_payload=e.response.text if e.response is not None else None,
                terminated_by="http_error",
            )
            writer.write(record)
            return True
        except httpx.RequestError as e:
            elapsed = time.monotonic() - t0
            record = _new_record(
                cfg,
                model_id=model_id,
                variant=variant,
                prompt=prompt,
                task_id=task_id,
                turn_idx=turn_idx,
                parent_record_id=prev_record_id,
                request_full=request_full,
                response=None,
                elapsed_seconds=elapsed,
                status="error",
                error_type="RequestError",
                error_message=str(e),
                error_payload=repr(e),
                terminated_by="http_error",
            )
            writer.write(record)
            return True

        tool_calls = response.tool_calls
        if not tool_calls:
            record = _new_record(
                cfg,
                model_id=model_id,
                variant=variant,
                prompt=prompt,
                task_id=task_id,
                turn_idx=turn_idx,
                parent_record_id=prev_record_id,
                request_full=request_full,
                response=response,
                elapsed_seconds=elapsed,
                status="ok",
                terminated_by="final_content",
            )
            writer.write(record)
            try:
                budget.add(float(response.usage.get("cost", 0.0)))
            except BudgetExceeded:
                return False
            return True

        tool_call = tool_calls[0]
        dispatch = variant.dispatch()
        try:
            called_name = tool_call["function"].get("name") or variant.function_name
            impl = dispatch.get(called_name, variant.impl)
            args = json.loads(tool_call["function"].get("arguments") or "{}")
            tool_result = impl(apacheta, args, qbudget)
            tool_error_type: str | None = None
            tool_error_message: str | None = None
        except Exception as e:  # noqa: BLE001 — tool errors captured, not raised
            tool_error_type = type(e).__name__
            tool_error_message = str(e)
            tool_result = None

        if tool_result is None:
            record = _new_record(
                cfg,
                model_id=model_id,
                variant=variant,
                prompt=prompt,
                task_id=task_id,
                turn_idx=turn_idx,
                parent_record_id=prev_record_id,
                request_full=request_full,
                response=response,
                elapsed_seconds=elapsed,
                status="ok",
                terminated_by="tool_error",
                tool_error_type=tool_error_type,
                tool_error_message=tool_error_message,
            )
            writer.write(record)
            try:
                budget.add(float(response.usage.get("cost", 0.0)))
            except BudgetExceeded:
                return False
            return True

        record = _new_record(
            cfg,
            model_id=model_id,
            variant=variant,
            prompt=prompt,
            task_id=task_id,
            turn_idx=turn_idx,
            parent_record_id=prev_record_id,
            request_full=request_full,
            response=response,
            elapsed_seconds=elapsed,
            status="ok",
            terminated_by=None,
        )
        writer.write(record)
        prev_record_id = record.record_id
        try:
            budget.add(float(response.usage.get("cost", 0.0)))
        except BudgetExceeded:
            return False

        messages.append(
            {
                "role": "assistant",
                "content": response.content or None,
                "tool_calls": tool_calls,
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.get("id", ""),
                "content": json.dumps(tool_result),
            }
        )

    # Loop hit max_turns. Records are frozen, so emit a synthetic
    # terminal record that carries terminated_by='max_turns'. Its
    # turn_idx is cfg.max_turns (one past the last real turn).
    record = _new_record(
        cfg,
        model_id=model_id,
        variant=variant,
        prompt=prompt,
        task_id=task_id,
        turn_idx=cfg.max_turns,
        parent_record_id=prev_record_id,
        request_full={},
        response=None,
        elapsed_seconds=0.0,
        status="ok",
        terminated_by="max_turns",
    )
    writer.write(record)
    return True


async def run_experiment(
    cfg: RunnerConfig,
    apacheta: ApachetaInterface,
    client: Any,
    panel_models: list[ResolvedModel | str],
    variants: list[ToolVariant],
    prompts: list[PromptTemplate],
) -> Path:
    """Drive the cartesian product. Returns the JSONL path written.

    `client` is duck-typed: anything with an async `.complete(model,
    messages, *, tools, tool_choice, max_tokens, metadata)` returning
    an OpenRouterResponse-shaped object will work — production code
    uses OpenRouterClient; tests substitute a fake.
    """
    out_path = cfg.capture_dir / f"{cfg.run_id}.jsonl"
    budget = CostBudget(cfg.cost_ceiling_usd)
    with CaptureWriter(out_path) as writer:
        for model in panel_models:
            for variant in variants:
                for prompt in prompts:
                    if not budget.ok():
                        return out_path
                    keep_going = await _run_task(
                        cfg,
                        client,
                        apacheta,
                        writer,
                        budget,
                        model_id=_model_id(model),
                        variant=variant,
                        prompt=prompt,
                    )
                    if not keep_going:
                        return out_path
    return out_path
