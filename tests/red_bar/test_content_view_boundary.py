"""Red bar: the content BM25 view respects the obfuscation boundary.

The content view (yanantin.apacheta.content_view) indexes record text for BM25
ranking. Two boundary properties, both C0-critical (cf. find()'s gh #9 note that
its substring path "searches PLAINTEXT and only works under the transparent
obfuscator" — the hole this view must NOT reopen):

  1. Built through Khipu.watay, the view's DB-visible links name the PHYSICAL
     collection/field, never the semantic `content`. (watay inherits this; here
     we assert it holds for THIS view specifically.)
  2. The view is queryable ONLY through the sanctioned physical field. A query
     that names the raw semantic field `content` under an opaque obfuscator finds
     NOTHING — there is no plaintext-named lane into the index.

Live DB, config-file creds (env path silently skips in a worktree).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from tests.integration._obfuscators import PrefixObfuscator
from yanantin.apacheta.content_view import (
    CONTENT_FIELD,
    CONTENT_VIEW_NAME,
    ensure_content_view,
    search_content_bm25,
)
from yanantin.infra.config import ApachetaDBConfig, get_database

pytestmark = pytest.mark.integration


@pytest.fixture
def live_db():
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )


def _drop(db, view, coll):
    if view in {v["name"] for v in db.views()}:
        db.delete_view(view)
    if db.has_collection(coll):
        db.delete_collection(coll)


def _clean_slate(db, coll):
    """Drop any stale global content view AND the physical collection, so watay
    creates the view fresh under THIS test's obfuscator. CONTENT_VIEW_NAME is a
    fixed global name; a view left by another run/obfuscator would collide with
    watay's create-if-absent check and shadow this test's obfuscated view."""
    if CONTENT_VIEW_NAME in {v["name"] for v in db.views()}:
        db.delete_view(CONTENT_VIEW_NAME)
    if db.has_collection(coll):
        db.delete_collection(coll)


def test_content_view_links_name_physical_field_not_semantic(live_db):
    """The DB-visible view links must carry the PHYSICAL field name, never the
    semantic `content` — else the semantic name leaks into queryable metadata."""
    obf = PrefixObfuscator("zc_")
    physical_coll = obf.collection_name("records")
    physical_field = obf.field_name(CONTENT_FIELD)
    try:
        _clean_slate(live_db, physical_coll)
        live_db.create_collection(physical_coll)
        ensure_content_view(live_db, obf)

        links = live_db.view(CONTENT_VIEW_NAME)["links"]
        assert physical_coll in links
        assert "records" not in links
        fields = links[physical_coll]["fields"]
        assert physical_field in fields, "content view lost its indexed field"
        assert CONTENT_FIELD not in fields, (
            f"semantic field {CONTENT_FIELD!r} leaked into DB-visible view links "
            "— the obfuscation boundary is bypassed at the content view (gh #9)"
        )
    finally:
        _drop(live_db, CONTENT_VIEW_NAME, physical_coll)


def test_content_search_finds_nothing_through_the_raw_semantic_field(live_db):
    """Under an opaque obfuscator, content stored at the physical field is found
    by search_content_bm25 (which names the physical field) but a query naming
    the RAW semantic field finds nothing — no plaintext-named lane into the index."""
    obf = PrefixObfuscator("zc_")
    physical_coll = obf.collection_name("records")
    physical_field = obf.field_name(CONTENT_FIELD)
    key = str(uuid4())
    try:
        _clean_slate(live_db, physical_coll)
        live_db.create_collection(physical_coll)
        live_db.collection(physical_coll).truncate()
        live_db.collection(physical_coll).insert(
            {"_key": key, physical_field: "quechua ayllu yanantin substrate"}
        )
        ensure_content_view(live_db, obf)

        # Sanctioned path (names physical field) finds the doc.
        found = []
        for _ in range(20):
            found = search_content_bm25(live_db, "quechua", obf, limit=5)
            if found:
                break
            list(live_db.aql.execute("RETURN 1"))
        assert any(k == key for k, _ in found), "sanctioned BM25 query found nothing"

        # Raw-semantic-field query: names `content` directly. Under the opaque
        # obfuscator the stored field is physical, so this must find NOTHING.
        raw = list(
            live_db.aql.execute(
                f"FOR d IN {CONTENT_VIEW_NAME} "
                f"SEARCH ANALYZER(d.{CONTENT_FIELD} IN TOKENS(@t, 'text_en'), 'text_en') "
                "RETURN d._key",
                bind_vars={"t": "quechua"},
            )
        )
        assert raw == [], (
            "a query naming the raw semantic field `content` returned hits — "
            "there is a plaintext-named lane into the index (boundary bypass)"
        )
    finally:
        _drop(live_db, CONTENT_VIEW_NAME, physical_coll)
