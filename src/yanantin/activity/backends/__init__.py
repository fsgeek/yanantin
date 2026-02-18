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
