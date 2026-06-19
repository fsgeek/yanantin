"""Red bar for a negative schema-governance requirement.

Khipu.watay must never reconcile schema on a pre-existing collection. If this
trips, someone made watay apply or alter schema on an existing collection:
STOP. Schema is a property of the data, an enforcement boundary, and a
published interface; changing it is a data migration, not an init side-effect.
"""

from uuid import uuid4

import pytest
from pydantic import BaseModel

from yanantin.core.collection_definition import CollectionDefinition, arangodb_schema
from yanantin.core.khipu import Khipu
from yanantin.infra.config import ApachetaDBConfig, get_database


class _Doc(BaseModel):
    required_field: str


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


def test_watay_does_not_apply_schema_to_preexisting_schemaless_collection(live_db):
    semantic = f"khipu_rb_{uuid4().hex}"
    khipu = Khipu(db=live_db)

    try:
        khipu.watay(semantic, CollectionDefinition())
        assert live_db.collection(semantic).properties().get("schema") is None

        khipu.watay(semantic, CollectionDefinition(schema=arangodb_schema(_Doc)))

        # Applying schema here would be a migration, not an init side-effect.
        assert live_db.collection(semantic).properties().get("schema") is None
    finally:
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)
