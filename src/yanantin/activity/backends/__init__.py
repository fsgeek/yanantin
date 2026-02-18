"""Activity stream store backends.

Three backends, same contract:
- InMemoryActivityStreamStore — dict + bisect, for tests
- DuckDBActivityStreamStore — SQL query pushdown, file-backed
- ArangoDBActivityStreamStore — AQL + persistent sorted index, production
"""

from yanantin.activity.backends.memory import InMemoryActivityStreamStore

__all__ = [
    "InMemoryActivityStreamStore",
]

# ArangoDB and DuckDB backends are not imported at package level to avoid
# requiring their dependencies (python-arango, duckdb) for all users.
# Import directly: from yanantin.activity.backends.arango import ArangoDBActivityStreamStore
# Import directly: from yanantin.activity.backends.duckdb import DuckDBActivityStreamStore
