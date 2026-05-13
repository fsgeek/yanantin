"""OpenRouter API client for Apacheta.

Adapted from promptguard2's OpenRouter client. Adds Apacheta-specific
provenance: every API call can be stored as a TensorRecord with full
metadata about model, cost, and experiment context.

Uses httpx for async HTTP. OpenAI-compatible API at openrouter.ai.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import BaseModel, Field


class OpenRouterMessage(BaseModel):
    """A chat message in OpenRouter format."""

    role: str
    content: str


class OpenRouterResponse(BaseModel):
    """Parsed response from OpenRouter API."""

    id: str = ""
    model: str = ""
    content: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OpenRouterClient:
    """Async client for OpenRouter's OpenAI-compatible API.

    Usage::

        async with OpenRouterClient() as client:
            response = await client.complete(
                model="anthropic/claude-haiku-4.5",
                messages=[{"role": "user", "content": "Hello"}],
            )
            print(response.content)
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 120.0,
        app_title: str = "yanantin",
        site_url: str = "https://github.com/fsgeek/yanantin",
    ) -> None:
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not set. "
                "Pass api_key= or export OPENROUTER_API_KEY=..."
            )
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "X-Title": app_title,
                "HTTP-Referer": site_url,
            },
            timeout=timeout,
        )

    async def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        metadata: dict[str, str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> OpenRouterResponse:
        """Send a chat completion request.

        Args:
            model: OpenRouter model ID (e.g. "anthropic/claude-haiku-4.5")
            messages: List of role/content dicts; tool messages may carry
                tool_call_id and structured content.
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            metadata: OpenRouter metadata for experiment tracking / cost allocation
            tools: Optional list of OpenAI-format tool definitions to expose.
            tool_choice: 'auto', 'none', or a forced choice dict. Only sent
                when tools is also provided.

        Returns:
            Parsed response with content, usage, raw API response, and any
            tool_calls the model emitted.

        Raises:
            httpx.HTTPStatusError: On API errors (4xx, 5xx)
            httpx.RequestError: On network errors
        """
        request_data: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if metadata:
            request_data["metadata"] = metadata
        if tools is not None:
            request_data["tools"] = tools
            if tool_choice is not None:
                request_data["tool_choice"] = tool_choice

        response = await self._client.post("/chat/completions", json=request_data)
        response.raise_for_status()

        raw = response.json()
        content = ""
        tool_calls: list[dict[str, Any]] | None = None
        if raw.get("choices"):
            message = raw["choices"][0].get("message", {}) or {}
            content = message.get("content") or ""
            tool_calls = message.get("tool_calls") or None

        return OpenRouterResponse(
            id=raw.get("id", ""),
            model=raw.get("model", model),
            content=content,
            usage=raw.get("usage", {}),
            raw=raw,
            tool_calls=tool_calls,
        )

    async def list_models(self) -> list[dict[str, Any]]:
        """Fetch available models from OpenRouter."""
        response = await self._client.get("/models")
        response.raise_for_status()
        return response.json().get("data", [])

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> OpenRouterClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()


# Convenience function for one-shot completions
async def complete(
    model: str,
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1000,
    metadata: dict[str, str] | None = None,
    app_title: str = "yanantin",
) -> str:
    """One-shot completion. Returns content string.

    Example::

        text = await complete(
            model="anthropic/claude-haiku-4.5",
            prompt="What is epistemic honesty?",
            metadata={"experiment": "scout_chain_3"},
        )
    """
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with OpenRouterClient(app_title=app_title) as client:
        response = await client.complete(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata=metadata,
        )
        return response.content
