"""Data models for OpenRouter API activity records.

Each row in OpenRouter's activity CSV becomes an OpenRouterActivityRow.
The full CSV becomes an OpenRouterActivity snapshot. These are raw
observations — no interpretation, no aggregation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OpenRouterActivityRow(BaseModel):
    """One API call as reported by OpenRouter's activity export.

    Fields map 1:1 to the CSV columns. We preserve everything — truncate
    nothing, fake nothing. Empty strings stay empty, not None.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    generation_id: str
    created_at: datetime
    cost_total: float = 0.0
    cost_web_search: float = 0.0
    cost_cache: float = 0.0
    cost_file_processing: float = 0.0
    byok_usage_inference: float = 0.0
    tokens_prompt: int = 0
    tokens_completion: int = 0
    tokens_reasoning: int = 0
    tokens_cached: int = 0
    model_permaslug: str = ""
    provider_name: str = ""
    variant: str = ""
    cancelled: bool = False
    streamed: bool = False
    user: str = ""
    finish_reason_raw: str = ""
    finish_reason_normalized: str = ""
    generation_time_ms: int = 0
    time_to_first_token_ms: int = 0
    app_name: str = ""
    api_key_name: str = ""

    @model_validator(mode="after")
    def _ensure_utc(self) -> Self:
        """Ensure created_at is timezone-aware."""
        if self.created_at.tzinfo is None:
            from datetime import timezone
            object.__setattr__(
                self, "created_at",
                self.created_at.replace(tzinfo=timezone.utc),
            )
        return self


class OpenRouterActivity(BaseModel):
    """A batch of OpenRouter activity rows from a CSV export.

    The collector produces this; the fact recorder decomposes it into
    individual facts. The source_file field records provenance — which
    CSV this came from.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: tuple[OpenRouterActivityRow, ...] = Field(default_factory=tuple)
    source_file: str = ""
    collected_at: datetime = Field(
        default_factory=lambda: datetime.now(__import__("datetime").timezone.utc),
    )
