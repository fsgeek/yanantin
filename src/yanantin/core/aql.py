"""The AQL gateway: the one place yanantin executes AQL, and what each query cost.

Every query goes through run(), which returns the driver's cursor wrapped so
rows stream through unchanged (some cursors are millions of rows; nothing is
collected). When the cursor is exhausted or closed, a QueryObservation goes to
each observer registered with observe(): the query text, the database, the
collections bound with @@, the names of the other binds, rows returned,
ArangoDB's own scan/filter counts and execution time, and wall time.

Bind VALUES are never recorded: they are data. Collection binds are names.

Declared losses:
- A cursor dropped without being exhausted or closed is not observed.
- A query the server rejects raises from run() and is not observed.
- Observers are process-global, like logging handlers.
- Nothing is recorded unless someone calls observe();
  yanantin.query.recorder.AqlObservationRecorder keeps them as facts.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class QueryObservation(BaseModel):
    """What one AQL query cost, as the server and the client saw it."""

    model_config = ConfigDict(frozen=True)

    started_at: datetime
    database: str
    query: str
    collections: tuple[str, ...]
    bind_names: tuple[str, ...]
    returned: int
    exhausted: bool
    scanned_full: int | None
    scanned_index: int | None
    filtered: int | None
    full_count: int | None
    server_ms: float | None
    # From run() to exhaustion or close; includes the caller's time between rows.
    elapsed_ms: float


Observer = Callable[[QueryObservation], None]

_observers: list[Observer] = []


def observe(observer: Observer) -> Callable[[], None]:
    """Register an observer for every finished query. Returns its unsubscribe."""
    _observers.append(observer)
    return lambda: _observers.remove(observer)


def run(db, query: str, *, bind_vars: dict | None = None, **options) -> ObservedCursor:
    """Execute AQL on db (a python-arango database) and observe its cost.

    options pass through to db.aql.execute (batch_size, full_count, count, ...).
    """
    started_at = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    cursor = db.aql.execute(query, bind_vars=bind_vars, **options)
    return ObservedCursor(cursor, db.name, query, bind_vars or {}, started_at, t0)


class ObservedCursor:
    """A python-arango Cursor that reports once, when exhausted or closed.

    Iteration, next() and pop() are counted; everything else is the driver's.
    """

    def __init__(self, cursor, database: str, query: str, bind_vars: dict,
                 started_at: datetime, t0: float) -> None:
        self._cursor = cursor
        self._database = database
        self._query = query
        self._bind_vars = bind_vars
        self._started_at = started_at
        self._t0 = t0
        self._returned = 0
        self._reported = False

    def __iter__(self) -> ObservedCursor:
        return self

    def __next__(self):
        try:
            row = self._cursor.next()
        except StopIteration:
            self._report(exhausted=True)
            raise
        self._returned += 1
        return row

    next = __next__

    def pop(self):
        row = self._cursor.pop()
        self._returned += 1
        if self._cursor.empty() and not self._cursor.has_more():
            self._report(exhausted=True)
        return row

    def close(self, ignore_missing: bool = False):
        exhausted = self._cursor.empty() and not self._cursor.has_more()
        result = self._cursor.close(ignore_missing=ignore_missing)
        self._report(exhausted=exhausted)
        return result

    def __getattr__(self, name: str):
        return getattr(self._cursor, name)

    def _report(self, exhausted: bool) -> None:
        if self._reported:
            return
        self._reported = True
        stats = self._cursor.statistics() or {}
        server_s = stats.get("execution_time")
        obs = QueryObservation(
            started_at=self._started_at,
            database=self._database,
            query=self._query,
            collections=tuple(sorted(
                str(v) for k, v in self._bind_vars.items() if k.startswith("@"))),
            bind_names=tuple(sorted(k for k in self._bind_vars if not k.startswith("@"))),
            returned=self._returned,
            exhausted=exhausted,
            scanned_full=stats.get("scanned_full"),
            scanned_index=stats.get("scanned_index"),
            filtered=stats.get("filtered"),
            full_count=stats.get("fullCount"),
            server_ms=None if server_s is None else server_s * 1000,
            elapsed_ms=(time.perf_counter() - self._t0) * 1000,
        )
        for observer in list(_observers):
            try:
                observer(obs)
            except Exception:
                logger.exception("AQL observer %r failed; the query is unaffected", observer)

