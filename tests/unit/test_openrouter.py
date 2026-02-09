"""Tests for the OpenRouter API client abstraction."""

import os

import pytest

from yanantin.apacheta.clients.openrouter import (
    OpenRouterClient,
    OpenRouterResponse,
)


class TestOpenRouterClient:
    def test_requires_api_key(self):
        old = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                OpenRouterClient(api_key=None)
        finally:
            if old:
                os.environ["OPENROUTER_API_KEY"] = old

    def test_accepts_explicit_api_key(self):
        import asyncio

        client = OpenRouterClient(api_key="test-key-123")
        assert client.api_key == "test-key-123"
        asyncio.run(client.close())

    def test_base_url(self):
        assert OpenRouterClient.BASE_URL == "https://openrouter.ai/api/v1"


class TestOpenRouterResponse:
    def test_response_model(self):
        resp = OpenRouterResponse(
            id="test-123",
            model="test/model",
            content="Hello world",
            usage={"prompt_tokens": 10, "completion_tokens": 20},
            raw={"id": "test-123", "choices": []},
        )
        assert resp.content == "Hello world"
        assert resp.usage["prompt_tokens"] == 10
