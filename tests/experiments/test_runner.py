from __future__ import annotations

import asyncio
import importlib
import inspect
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pytest

from yanantin.apacheta.clients.openrouter import OpenRouterResponse
from yanantin.experiments.capture import load_run
from yanantin.experiments.panel import ResolvedModel
from yanantin.experiments.prompts import PromptTemplate
from yanantin.experiments.tools.registry import ToolVariant


class FakeOpenRouter:
    def __init__(self, scripted: list[OpenRouterResponse | Exception]) -> None:
        self._scripted = list(scripted)
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None,
        tool_choice: str | dict[str, Any] | None,
        max_tokens: int,
        metadata: dict[str, str] | None,
        temperature: float = 0.7,
    ) -> OpenRouterResponse:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "tools": tools,
                "tool_choice": tool_choice,
                "max_tokens": max_tokens,
                "metadata": metadata,
                "temperature": temperature,
            }
        )
        if not self._scripted:
            raise AssertionError("FakeOpenRouter queue is empty")
        item = self._scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeApacheta:
    def __getattr__(self, _name: str) -> Any:
        raise AssertionError("runner should only touch apacheta via tool impl")


@dataclass
class RecordingToolImpl:
    result: dict[str, Any] | None = None
    exc: Exception | None = None

    def __post_init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, apacheta: Any, args: dict[str, Any], budget: Any) -> dict[str, Any]:
        self.calls.append(
            {
                "apacheta": apacheta,
                "args": args,
                "budget_type": type(budget).__name__,
                "budget_remaining": getattr(budget, "remaining", None),
            }
        )
        if self.exc is not None:
            raise self.exc
        assert self.result is not None
        return self.result


def _runner_module() -> Any:
    return importlib.import_module("yanantin.experiments.runner")


def _run_maybe_async(value: Any) -> Any:
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def _mk_cfg(runner: Any, capture_dir: Path, **overrides: Any) -> Any:
    data = {
        "experiment_id": "exp-1",
        "panel_id": "panel-1",
        "capture_dir": capture_dir,
        "run_id": "run-1",
        "cost_ceiling_usd": 10.0,
        "max_turns": 6,
        "query_budget_per_task": 12,
        "max_tokens": 1234,
        "x_title": "yanantin:memtool",
        "system_prompt": "You are runner test system prompt.",
    }
    data.update(overrides)
    return runner.RunnerConfig(**data)


def _mk_model(model_id: str) -> ResolvedModel:
    return ResolvedModel(
        id=model_id,
        family="f",
        size_tier="s",
        cost_tier="c",
        prompt_cost=0.0,
        completion_cost=0.0,
        context_length=8000,
        native_max_tokens=4096,
    )


def _mk_schema(name: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "test",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _mk_variant(impl: Any) -> ToolVariant:
    schema = _mk_schema("find_objects")
    return ToolVariant(
        variant_id="find_objects_v1",
        function_name="find_objects",
        schema=schema,
        impl=impl,
    )


def _mk_prompt(text: str = "find info") -> PromptTemplate:
    return PromptTemplate(template_id="tmpl-1", text=text)


def _mk_response(
    *,
    content: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    cost: float = 0.0,
    raw: dict[str, Any] | None = None,
) -> OpenRouterResponse:
    return OpenRouterResponse(
        id="resp-id",
        model="m",
        content=content,
        usage={"cost": cost},
        raw=raw or {"raw": True},
        tool_calls=tool_calls,
    )


def test_run_experiment_final_content_single_turn(tmp_path: Path) -> None:
    runner = _runner_module()
    impl = RecordingToolImpl(result={"unused": True})
    client = FakeOpenRouter([_mk_response(content="done", tool_calls=None, cost=0.01)])

    cfg = _mk_cfg(runner, tmp_path)
    variant = _mk_variant(impl)
    model = _mk_model("model-a")
    prompt = _mk_prompt("hello")

    path = _run_maybe_async(
        runner.run_experiment(cfg, FakeApacheta(), client, [model], [variant], [prompt])
    )

    assert path == tmp_path / "run-1.jsonl"
    records = load_run(path)
    assert len(records) == 1
    rec = records[0]
    assert rec.status == "ok"
    assert rec.terminated_by == "final_content"
    assert rec.turn_idx == 0
    assert rec.parent_record_id is None
    UUID(rec.task_id)

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["model"] == "model-a"
    assert call["messages"] == [
        {"role": "system", "content": cfg.system_prompt},
        {"role": "user", "content": "hello"},
    ]
    assert call["tools"] == [variant.schema]
    assert call["tool_choice"] == "auto"
    assert call["max_tokens"] == cfg.max_tokens
    assert call["metadata"] == {"X-Title": f"{cfg.x_title}:{cfg.experiment_id}"}
    assert impl.calls == []


def test_run_experiment_tool_turn_message_thread_shape(tmp_path: Path) -> None:
    runner = _runner_module()
    tool_calls = [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "find_objects", "arguments": '{"matching":{}}'},
        }
    ]
    impl = RecordingToolImpl(result={"results": [{"id": "x"}]})
    client = FakeOpenRouter(
        [
            _mk_response(content="", tool_calls=tool_calls, cost=0.02),
            _mk_response(content="all done", tool_calls=None, cost=0.03),
        ]
    )

    cfg = _mk_cfg(runner, tmp_path)
    variant = _mk_variant(impl)

    _run_maybe_async(
        runner.run_experiment(
            cfg,
            FakeApacheta(),
            client,
            [_mk_model("model-a")],
            [variant],
            [_mk_prompt("query")],
        )
    )

    assert len(impl.calls) == 1
    assert impl.calls[0]["args"] == {"matching": {}}
    assert impl.calls[0]["budget_type"] == "QueryBudget"
    assert impl.calls[0]["budget_remaining"] == cfg.query_budget_per_task

    assert len(client.calls) == 2
    followup_msgs = client.calls[1]["messages"]
    assert followup_msgs[0] == {"role": "system", "content": cfg.system_prompt}
    assert followup_msgs[1] == {"role": "user", "content": "query"}
    assert followup_msgs[2]["role"] == "assistant"
    assert followup_msgs[2]["tool_calls"] == tool_calls
    assert followup_msgs[3]["role"] == "tool"
    assert followup_msgs[3]["tool_call_id"] == "call-1"
    assert json.loads(followup_msgs[3]["content"]) == {"results": [{"id": "x"}]}

    records = load_run(tmp_path / "run-1.jsonl")
    assert len(records) == 2
    assert records[0].terminated_by is None
    assert records[1].terminated_by == "final_content"
    assert records[1].parent_record_id == records[0].record_id


def test_run_experiment_multi_tool_surface_dispatches_by_called_function_name(
    tmp_path: Path,
) -> None:
    runner = _runner_module()
    tool_calls = [
        {
            "id": "call-meta",
            "type": "function",
            "function": {
                "name": "request_capability",
                "arguments": '{"capability":"calendar"}',
            },
        }
    ]
    primary_impl = RecordingToolImpl(result={"primary": True})
    extra_impl = RecordingToolImpl(result={"requested": "calendar"})
    primary_schema = _mk_schema("query")
    extra_schema = _mk_schema("request_capability")
    variant = ToolVariant(
        variant_id="missing_affordance_v1",
        function_name="query",
        schema=primary_schema,
        impl=primary_impl,
        extra_schemas=(extra_schema,),
        extra_impls=(("request_capability", extra_impl),),
    )
    client = FakeOpenRouter(
        [
            _mk_response(content="", tool_calls=tool_calls, cost=0.02),
            _mk_response(content="done", tool_calls=None, cost=0.03),
        ]
    )

    _run_maybe_async(
        runner.run_experiment(
            _mk_cfg(runner, tmp_path),
            FakeApacheta(),
            client,
            [_mk_model("model-a")],
            [variant],
            [_mk_prompt("need a missing capability")],
        )
    )

    assert [call["tools"] for call in client.calls] == [
        [primary_schema, extra_schema],
        [primary_schema, extra_schema],
    ]
    assert primary_impl.calls == []
    assert len(extra_impl.calls) == 1
    assert extra_impl.calls[0]["args"] == {"capability": "calendar"}

    records = load_run(tmp_path / "run-1.jsonl")
    assert len(records) == 2
    assert records[0].request_full["tools"] == [primary_schema, extra_schema]
    assert records[0].terminated_by is None
    assert records[1].terminated_by == "final_content"


def test_run_experiment_single_tool_variant_uses_legacy_surface_and_impl_fallback(
    tmp_path: Path,
) -> None:
    runner = _runner_module()
    tool_calls = [
        {
            "id": "call-legacy",
            "type": "function",
            "function": {"name": "unknown_tool_name", "arguments": '{"matching":{}}'},
        }
    ]
    impl = RecordingToolImpl(result={"results": [{"id": "legacy"}]})
    variant = _mk_variant(impl)
    client = FakeOpenRouter(
        [
            _mk_response(content="", tool_calls=tool_calls, cost=0.02),
            _mk_response(content="done", tool_calls=None, cost=0.03),
        ]
    )

    _run_maybe_async(
        runner.run_experiment(
            _mk_cfg(runner, tmp_path),
            FakeApacheta(),
            client,
            [_mk_model("model-a")],
            [variant],
            [_mk_prompt("query")],
        )
    )

    assert [call["tools"] for call in client.calls] == [
        [variant.schema],
        [variant.schema],
    ]
    assert len(impl.calls) == 1
    assert impl.calls[0]["args"] == {"matching": {}}

    records = load_run(tmp_path / "run-1.jsonl")
    assert len(records) == 2
    assert records[0].request_full["tools"] == [variant.schema]
    assert records[0].terminated_by is None
    assert records[1].terminated_by == "final_content"


def test_run_experiment_tool_error_terminates_task(tmp_path: Path) -> None:
    runner = _runner_module()
    tool_calls = [
        {
            "id": "call-err",
            "type": "function",
            "function": {"name": "find_objects", "arguments": "{}"},
        }
    ]
    impl = RecordingToolImpl(exc=ValueError("bad tool args"))
    client = FakeOpenRouter([_mk_response(content="", tool_calls=tool_calls, cost=0.01)])

    _run_maybe_async(
        runner.run_experiment(
            _mk_cfg(runner, tmp_path),
            FakeApacheta(),
            client,
            [_mk_model("m")],
            [_mk_variant(impl)],
            [_mk_prompt()],
        )
    )

    records = load_run(tmp_path / "run-1.jsonl")
    assert len(records) == 1
    rec = records[0]
    assert rec.status == "ok"
    assert rec.terminated_by == "tool_error"
    assert rec.tool_error_type == "ValueError"
    assert "bad tool args" in rec.tool_error_message
    assert len(client.calls) == 1


def test_run_experiment_http_status_error_captured(tmp_path: Path) -> None:
    runner = _runner_module()
    req = httpx.Request("POST", "http://x")
    resp = httpx.Response(400, text='{"error":"bad"}', request=req)
    err = httpx.HTTPStatusError("bad status", request=req, response=resp)
    client = FakeOpenRouter([err])

    _run_maybe_async(
        runner.run_experiment(
            _mk_cfg(runner, tmp_path),
            FakeApacheta(),
            client,
            [_mk_model("m")],
            [_mk_variant(RecordingToolImpl(result={"x": 1}))],
            [_mk_prompt()],
        )
    )

    records = load_run(tmp_path / "run-1.jsonl")
    assert len(records) == 1
    rec = records[0]
    assert rec.status == "error"
    assert rec.terminated_by == "http_error"
    assert rec.error_type == "HTTPStatusError"
    assert rec.error_message
    assert rec.error_payload


def test_run_experiment_emits_synthetic_max_turns_terminal_record(tmp_path: Path) -> None:
    runner = _runner_module()
    tool_calls = [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "find_objects", "arguments": "{}"},
        }
    ]
    impl = RecordingToolImpl(result={"ok": True})
    client = FakeOpenRouter(
        [
            _mk_response(content="", tool_calls=tool_calls, cost=0.01),
            _mk_response(content="", tool_calls=tool_calls, cost=0.01),
        ]
    )

    cfg = _mk_cfg(runner, tmp_path, max_turns=2)
    _run_maybe_async(
        runner.run_experiment(
            cfg,
            FakeApacheta(),
            client,
            [_mk_model("m")],
            [_mk_variant(impl)],
            [_mk_prompt()],
        )
    )

    records = load_run(tmp_path / "run-1.jsonl")
    assert len(records) == 3
    assert records[0].terminated_by is None
    assert records[1].terminated_by is None
    terminal = records[2]
    assert terminal.status == "ok"
    assert terminal.terminated_by == "max_turns"
    assert terminal.turn_idx == cfg.max_turns
    assert terminal.parent_record_id == records[1].record_id
    assert terminal.response_parsed is None


def test_run_experiment_stops_cleanly_when_budget_exceeded_after_write(
    tmp_path: Path,
) -> None:
    runner = _runner_module()
    client = FakeOpenRouter([
        _mk_response(content="done", tool_calls=None, cost=1.0),
        _mk_response(content="should-not-run", tool_calls=None, cost=0.1),
    ])

    cfg = _mk_cfg(runner, tmp_path, cost_ceiling_usd=0.5)
    out_path = _run_maybe_async(
        runner.run_experiment(
            cfg,
            FakeApacheta(),
            client,
            [_mk_model("model-a"), _mk_model("model-b")],
            [_mk_variant(RecordingToolImpl(result={"x": 1}))],
            [_mk_prompt("p")],
        )
    )

    assert out_path == tmp_path / "run-1.jsonl"
    records = load_run(out_path)
    assert len(records) == 1
    assert records[0].terminated_by == "final_content"
    assert len(client.calls) == 1
