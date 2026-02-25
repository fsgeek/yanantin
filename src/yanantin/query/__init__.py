"""Query pipeline for the activity stream.

Structured queries against ActivityStreamStore. Queries are also
activity data — recording them enables cross-instance pattern detection.

The query service produces structured queries as OUTPUT. The CLI
provides structured input directly. NL parsing is a future layer.
"""

from yanantin.query.engine import QueryEngine
from yanantin.query.models import ContentFilter, QueryResult, QuerySpec, QuerySummary
from yanantin.query.recorder import QueryFactRecorder

__all__ = [
    "ContentFilter",
    "QueryEngine",
    "QueryFactRecorder",
    "QueryResult",
    "QuerySpec",
    "QuerySummary",
]
