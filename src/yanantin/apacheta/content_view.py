"""Content BM25 view: native ArangoSearch ranking over the open `records` lane.

The `find()` backend today is a full-scan Python substring match — no ranking,
no analyzer (arango.py:456, "replacing this body with an ArangoSearch view is
the next slice"). This is that slice: an ArangoSearch view with the `text_en`
analyzer over record content, queried with BM25() for relevance-ranked hits.

It is the native, in-substrate replacement for the BM25 that qhaway (sqlite FTS)
and llm-memory (duckdb) provide as external scaffolding — here BM25 lives in the
apacheta store itself.

Boundary discipline: the view is created through `Khipu.watay`, so its `links`
(collection + field names) route through the obfuscator's sanctioned map exactly
like every other view (khipu._obfuscate_links). A view built by hand with raw
semantic field names would leak them into queryable DB metadata (a C0 break);
this path cannot. The red bar in tests/red_bar guards that.

Transducer-agnostic: this view indexes a `content` string on records. Whatever
produces that content (the Unstructured transducer, or a later engine) is upstream
and invisible here — the view only knows there is text to rank.
"""

from __future__ import annotations

from arango.database import StandardDatabase

from yanantin.core.collection_definition import CollectionDefinition
from yanantin.core.khipu import Khipu
from yanantin.core.storage_obfuscator import StorageObfuscator

# The semantic field on a record that holds indexable text content. Named
# semantically; Khipu routes it through the obfuscator when building the view.
CONTENT_FIELD = "content"

# Well-known semantic name of the content BM25 view.
CONTENT_VIEW_NAME = "records_content_bm25"

_ANALYZER = "text_en"


def content_view_definition() -> CollectionDefinition:
    """A CollectionDefinition whose single view is the content BM25 view over
    the `records` lane. Fed to Khipu.watay, which obfuscates the links."""
    return CollectionDefinition(
        views=(
            {
                "name": CONTENT_VIEW_NAME,
                "links": {
                    # semantic collection name; khipu obfuscates it
                    "records": {
                        "fields": {
                            # semantic field name; khipu obfuscates it
                            CONTENT_FIELD: {"analyzers": [_ANALYZER]},
                        },
                    },
                },
            },
        ),
    )


def ensure_content_view(
    db: StandardDatabase, obfuscator: StorageObfuscator | None = None
) -> None:
    """Create the content BM25 view (idempotent) through the boundary-respecting
    Khipu path. The `records` collection must already exist."""
    Khipu(db, obfuscator).watay("records", content_view_definition())


def search_content_bm25(
    db: StandardDatabase,
    terms: str,
    obfuscator: StorageObfuscator,
    limit: int = 10,
) -> list[tuple[str, float]]:
    """Return (record_key, bm25_score) tuples, highest score first.

    The query names the PHYSICAL field (via the obfuscator) because it runs
    against the DB-visible, obfuscated view — the same boundary the view was
    built under. Scores come from ArangoDB's native BM25(), so ordering is
    relevance, not scan order — the capability find() lacks today.
    """
    physical_field = obfuscator.field_path((CONTENT_FIELD,))
    aql = (
        f"FOR doc IN {CONTENT_VIEW_NAME} "
        f"SEARCH ANALYZER(doc.{physical_field} IN TOKENS(@terms, @analyzer), @analyzer) "
        "SORT BM25(doc) DESC "
        "LIMIT @limit "
        "RETURN {key: doc._key, score: BM25(doc)}"
    )
    cursor = db.aql.execute(
        aql,
        bind_vars={"terms": terms, "analyzer": _ANALYZER, "limit": limit},
    )
    return [(row["key"], row["score"]) for row in cursor]
