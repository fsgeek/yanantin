"""Records queries as facts in the activity stream.

Reflexivity: queries are activity data. Recording them enables
cross-instance pattern detection ("every new instance asks about
the signing key first").

NOT a FactRecorderBase subclass — no collector pipeline involved.
The query service creates facts directly from query results.
"""

from __future__ import annotations

from uuid import UUID, uuid4, uuid5, NAMESPACE_DNS

from yanantin.activity.models import FactRecord
from yanantin.activity.store import ActivityStreamStore
from yanantin.query.models import QueryResult


QUERY_PROVIDER_ID: UUID = uuid5(NAMESPACE_DNS, "yanantin.query.service")


class QueryFactRecorder:
    """Records query execution metadata as activity stream facts.

    Stores the spec, timing, and counts — NOT the result facts
    (that would be duplication). The query itself is the observation.
    """

    def __init__(self, store: ActivityStreamStore) -> None:
        self._store = store

    def record_query(self, result: QueryResult) -> UUID:
        """Store query metadata as a FactRecord. Returns the fact UUID."""
        fact_id = uuid4()

        # Serialize the spec for storage
        spec_data = result.spec.model_dump(mode="json")

        fact = FactRecord(
            id=fact_id,
            provider_id=QUERY_PROVIDER_ID,
            timestamp=result.timestamp,
            data={
                "query_id": str(result.query_id),
                "spec": spec_data,
                "total_matched": result.total_matched,
                "returned_count": result.returned_count,
                "execution_time_ms": result.execution_time_ms,
            },
        )

        self._store.store_fact(fact)
        return fact_id
