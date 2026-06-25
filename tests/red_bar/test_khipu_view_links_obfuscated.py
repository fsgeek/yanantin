"""Red bar for gh #32: Khipu must obfuscate ArangoSearch view links.

Under an opaque obfuscator, view link definitions are DB-visible metadata.
Both the collection-name key and nested field-name keys must be physical names;
leaf view properties such as analyzers stay unchanged.
"""

from uuid import uuid4

import pytest

from tests.integration._obfuscators import PrefixObfuscator
from yanantin.core.collection_definition import CollectionDefinition
from yanantin.core.khipu import Khipu
from yanantin.infra.config import ApachetaDBConfig, get_database


pytestmark = pytest.mark.integration


@pytest.fixture
def live_db():
    """A real StandardDatabase handle on apacheta_test (test-tier creds)."""
    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    return get_database(
        host=cfg.host_url,
        db_name="apacheta_test",
        username=creds["username"],
        password=creds["password"],
    )


def test_watay_obfuscates_arangosearch_view_link_collection_and_field_keys(live_db):
    semantic_coll = f"khipu_view_links_{uuid4().hex}"
    view_name = f"khipu_view_links_view_{uuid4().hex}"
    obfuscator = PrefixObfuscator("z32_")
    physical_coll = obfuscator.collection_name(semantic_coll)
    physical_label = obfuscator.field_name("label")
    physical_modified = obfuscator.field_name("modified")

    definition = CollectionDefinition(
        views=(
            {
                "name": view_name,
                "type": "arangosearch",
                "links": {
                    semantic_coll: {
                        "fields": {
                            "label": {"analyzers": ["identity"]},
                            "modified": {"analyzers": ["identity"]},
                        },
                    },
                },
            },
        ),
    )
    khipu = Khipu(db=live_db, obfuscator=obfuscator)

    try:
        khipu.watay(semantic_coll, definition)

        matching_views = [v for v in live_db.views() if v["name"] == view_name]
        assert matching_views

        view = live_db.view(view_name)
        links = view["links"]

        assert physical_coll in links
        assert semantic_coll not in links

        fields = links[physical_coll]["fields"]
        assert physical_label in fields
        assert physical_modified in fields
        assert "label" not in fields
        assert "modified" not in fields
    finally:
        if view_name in {view["name"] for view in live_db.views()}:
            live_db.delete_view(view_name)
        for collection_name in (semantic_coll, physical_coll):
            if live_db.has_collection(collection_name):
                live_db.delete_collection(collection_name)
