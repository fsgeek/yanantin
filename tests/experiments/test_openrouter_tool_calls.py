import asyncio
import json
import os

import httpx
import pytest

from yanantin.apacheta.clients.openrouter import OpenRouterClient



def test_complete_omits_tools_and_tool_choice_when_none() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "resp_1",
                "model": "meta-llama/llama-3.2-1b-instruct",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"total_tokens": 1},
            },
        )

    async def _run() -> None:
        client = OpenRouterClient(api_key="test-key")
        real_client = client._client
        client._client = httpx.AsyncClient(
            base_url=OpenRouterClient.BASE_URL,
            transport=httpx.MockTransport(handler),
        )
        await real_client.aclose()
        try:
            await client.complete(
                model="meta-llama/llama-3.2-1b-instruct",
                messages=[{"role": "user", "content": "hi"}],
            )
        finally:
            await client.close()

    asyncio.run(_run())

    body = captured["json"]
    assert "tools" not in body
    assert "tool_choice" not in body



def test_complete_includes_tools_and_tool_choice_when_provided() -> None:
    captured: dict = {}
    tools = [
        {
            "type": "function",
            "function": {
                "name": "add",
                "description": "Add two integers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "integer"},
                        "b": {"type": "integer"},
                    },
                    "required": ["a", "b"],
                },
            },
        }
    ]
    tool_choice = {"type": "function", "function": {"name": "add"}}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "resp_2",
                "model": "meta-llama/llama-3.2-1b-instruct",
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"total_tokens": 1},
            },
        )

    async def _run() -> None:
        client = OpenRouterClient(api_key="test-key")
        real_client = client._client
        client._client = httpx.AsyncClient(
            base_url=OpenRouterClient.BASE_URL,
            transport=httpx.MockTransport(handler),
        )
        await real_client.aclose()
        try:
            await client.complete(
                model="meta-llama/llama-3.2-1b-instruct",
                messages=[{"role": "user", "content": "use tool"}],
                tools=tools,
                tool_choice=tool_choice,
            )
        finally:
            await client.close()

    asyncio.run(_run())

    body = captured["json"]
    assert body["tools"] == tools
    assert body["tool_choice"] == tool_choice



def test_complete_parses_tool_calls_when_content_is_none() -> None:
    tool_calls = [
        {
            "id": "call_abc",
            "type": "function",
            "function": {"name": "add", "arguments": '{"a":2,"b":3}'},
        }
    ]

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "resp_3",
                "model": "meta-llama/llama-3.2-1b-instruct",
                "choices": [{"message": {"content": None, "tool_calls": tool_calls}}],
                "usage": {"total_tokens": 7},
            },
        )

    async def _run():
        client = OpenRouterClient(api_key="test-key")
        real_client = client._client
        client._client = httpx.AsyncClient(
            base_url=OpenRouterClient.BASE_URL,
            transport=httpx.MockTransport(handler),
        )
        await real_client.aclose()
        try:
            return await client.complete(
                model="meta-llama/llama-3.2-1b-instruct",
                messages=[{"role": "user", "content": "what is 2+3?"}],
            )
        finally:
            await client.close()

    response = asyncio.run(_run())

    assert response.tool_calls == tool_calls
    assert response.content in (None, "")



def test_complete_tool_calls_default_to_none_when_absent() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "resp_4",
                "model": "meta-llama/llama-3.2-1b-instruct",
                "choices": [{"message": {"content": "plain text"}}],
                "usage": {"total_tokens": 3},
            },
        )

    async def _run():
        client = OpenRouterClient(api_key="test-key")
        real_client = client._client
        client._client = httpx.AsyncClient(
            base_url=OpenRouterClient.BASE_URL,
            transport=httpx.MockTransport(handler),
        )
        await real_client.aclose()
        try:
            return await client.complete(
                model="meta-llama/llama-3.2-1b-instruct",
                messages=[{"role": "user", "content": "hello"}],
            )
        finally:
            await client.close()

    response = asyncio.run(_run())

    assert response.tool_calls is None


@pytest.mark.integration
def test_complete_live_tool_call_roundtrip() -> None:
    if "OPENROUTER_API_KEY" not in os.environ:
        pytest.skip("no OPENROUTER_API_KEY")

    # NOTE: not every cheap model has tool-capable endpoints on OpenRouter.
    # llama-3.2-1b-instruct returns 404 "No endpoints found that support tool
    # use." gemini-2.5-flash-lite is the cheapest known-tool-capable model.
    model = "google/gemini-2.5-flash-lite"
    tools = [
        {
            "type": "function",
            "function": {
                "name": "add",
                "description": "Add two integers",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "integer"},
                        "b": {"type": "integer"},
                    },
                    "required": ["a", "b"],
                },
            },
        }
    ]

    async def _run():
        async with OpenRouterClient() as client:
            return await client.complete(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": "Call the add tool with a=2 and b=3. Do not answer directly.",
                    }
                ],
                max_tokens=64,
                temperature=0,
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "add"}},
            )

    response = asyncio.run(_run())

    assert response.model
    assert response.raw.get("choices")
    assert response.tool_calls, response.raw
    first = response.tool_calls[0]
    assert first.get("type") == "function"
    assert first.get("function", {}).get("name") == "add"
    assert isinstance(first.get("function", {}).get("arguments"), str)
