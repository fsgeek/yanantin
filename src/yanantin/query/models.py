"""Data models for the query pipeline.

All frozen, extra="forbid" — following existing conventions from
activity/models.py. ContentFilter and QuerySpec describe what to
find. QuerySummary and QueryResult describe what was found.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ContentFilter(BaseModel):
    """A filter condition on fact.data contents.

    Dot-paths resolve nested keys: "timestamps.modified" reaches
    data["timestamps"]["modified"]. Operators are applied in Python
    against the resolved value.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str
    op: Literal["contains", "eq", "gt", "lt", "gte", "lte", "exists", "glob"]
    value: Any = None


class QuerySpec(BaseModel):
    """Complete query specification.

    Provider, time range, content filters, pagination. This is the
    structured input — CLI flags map directly to these fields.
    extra="allow" because downstream layers (NL parser, confidence
    scores, source attribution) will extend this without breaking it.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: UUID = Field(default_factory=uuid4)
    provider_id: UUID | None = None
    start: datetime | None = None
    end: datetime | None = None
    content_filters: tuple[ContentFilter, ...] = ()
    content_hash: str | None = None
    limit: int = 100
    offset: int = 0
    summarize: bool = False


class QuerySummary(BaseModel):
    """Aggregate view of query results.

    Avoids returning 1.2M rows when you just want counts and shapes.
    extra="allow" because summary shape will grow as the engine learns
    new aggregate views.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    total_count: int
    providers: dict[str, int]
    time_range: tuple[datetime, datetime] | None = None
    top_content_hashes: dict[str, int] = Field(default_factory=dict)
    sample_data_keys: tuple[str, ...] = ()


class QueryResult(BaseModel):
    """Execution output with provenance.

    Carries the spec that produced it, the matched facts (paginated),
    optional summary, and timing information. extra="allow" because
    result metadata will grow (warnings, query_plan, cache_hit) as
    the engine evolves.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    query_id: UUID
    spec: QuerySpec
    facts: tuple[dict, ...] = ()
    summary: QuerySummary | None = None
    total_matched: int = 0
    returned_count: int = 0
    execution_time_ms: float = 0.0
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
