import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from yanantin.apacheta.clients.openrouter import OpenRouterClient
from yanantin.experiments.capture import CaptureRecord, CaptureWriter, load_run


@pytest.mark.integration
def test_capture_real_openrouter_call(tmp_path):
    if "OPENROUTER_API_KEY" not in os.environ:
        pytest.skip("no OPENROUTER_API_KEY")

    MODEL = "meta-llama/llama-3.2-1b-instruct"
    messages = [{"role": "user", "content": "Reply with exactly the word: pong"}]
    t0 = time.monotonic()

    async def _call():
        async with OpenRouterClient() as c:
            return await c.complete(
                model=MODEL,
                messages=messages,
                max_tokens=16,
                metadata={"X-Title": "yanantin:memtool:smoke"},
            )

    common = {
        "record_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc),
        "experiment_id": "smoke",
        "panel_id": "none",
        "tool_variant_id": "none",
        "model_id": MODEL,
        "prompt_template_id": "inline",
        "prompt_full": messages[0]["content"],
        "request_full": {"model": MODEL, "messages": messages, "max_tokens": 16},
    }

    try:
        resp = asyncio.run(_call())
        rec = CaptureRecord(
            **common,
            response_parsed={"content": resp.content, "id": resp.id, "model": resp.model},
            response_raw_body=json.dumps(resp.raw),
            usage=resp.usage,
            elapsed_seconds=time.monotonic() - t0,
            status="ok",
            error_type=None,
            error_message=None,
            error_payload=None,
        )
    except httpx.HTTPStatusError as e:
        rec = CaptureRecord(
            **common,
            response_parsed=None,
            response_raw_body=None,
            usage={},
            elapsed_seconds=time.monotonic() - t0,
            status="error",
            error_type="HTTPStatusError",
            error_message=str(e),
            error_payload=e.response.text,
        )
    except httpx.RequestError as e:
        rec = CaptureRecord(
            **common,
            response_parsed=None,
            response_raw_body=None,
            usage={},
            elapsed_seconds=time.monotonic() - t0,
            status="error",
            error_type="RequestError",
            error_message=str(e),
            error_payload=repr(e),
        )

    path = tmp_path / "smoke" / "r.jsonl"
    with CaptureWriter(path) as w:
        w.write(rec)

    loaded = load_run(path)
    assert len(loaded) == 1
    assert loaded[0].model_id == MODEL
    assert loaded[0].status in {"ok", "error"}
    if loaded[0].status == "ok":
        assert isinstance(loaded[0].response_parsed["content"], str)
        assert loaded[0].response_raw_body is not None
    if loaded[0].status == "error":
        assert loaded[0].error_payload is not None
