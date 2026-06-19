from uuid import uuid4

import pytest
from pydantic import BaseModel

from yanantin.core.collection_definition import CollectionDefinition, arangodb_schema
from yanantin.core.khipu import Khipu
from yanantin.infra.config import ApachetaDBConfig, get_database


class SampleModel(BaseModel):
    name: str
    count: int


def test_arangodb_schema_wraps_model_json_schema():
    env = arangodb_schema(SampleModel)

    assert env["level"] == "strict"
    assert env["type"] == "json"
    assert env["rule"] == SampleModel.model_json_schema()
    assert "message" in env


def test_collection_definition_defaults_are_empty():
    definition = CollectionDefinition()

    assert definition.schema is None
    assert definition.indices == ()
    assert definition.views == ()
    assert definition.edge is False


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


def test_watay_creates_collection_under_obfuscated_name(live_db):
    semantic = f"test_khipu_{uuid4().hex}"

    try:
        handle = Khipu(db=live_db, obfuscator=None).watay(
            semantic,
            CollectionDefinition(),
        )

        assert handle.name == semantic
        assert live_db.has_collection(semantic)
    finally:
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)


def test_watay_applies_schema_at_creation(live_db):
    class _Doc(BaseModel):
        name: str

    semantic = f"test_khipu_{uuid4().hex}"

    try:
        Khipu(db=live_db, obfuscator=None).watay(
            semantic,
            CollectionDefinition(schema=arangodb_schema(_Doc)),
        )

        schema = live_db.collection(semantic).properties()["schema"]
        assert schema is not None
        assert schema["level"] == "strict"
    finally:
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)


def test_watay_is_idempotent(live_db):
    semantic = f"test_khipu_{uuid4().hex}"

    try:
        khipu = Khipu(db=live_db, obfuscator=None)

        first = khipu.watay(semantic, CollectionDefinition())
        second = khipu.watay(semantic, CollectionDefinition())

        assert first.name == semantic
        assert second.name == semantic
        assert live_db.has_collection(semantic)
    finally:
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)


def test_watay_creates_indices_additively(live_db):
    semantic = f"test_khipu_{uuid4().hex}"
    defn = CollectionDefinition(
        indices=(
            {"type": "persistent", "fields": ["uri"], "unique": True, "name": "uri_idx"},
        ),
    )
    khipu = Khipu(db=live_db)

    try:
        khipu.watay(semantic, defn)
        index_names = {index["name"] for index in live_db.collection(semantic).indexes()}
        assert "uri_idx" in index_names

        khipu.watay(semantic, defn)
        index_names = {index["name"] for index in live_db.collection(semantic).indexes()}
        assert "uri_idx" in index_names
    finally:
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)


def test_watay_creates_arangosearch_view(live_db):
    semantic = f"test_khipu_{uuid4().hex}"
    view_name = f"test_khipu_view_{uuid4().hex}"
    defn = CollectionDefinition(
        views=(
            {
                "name": view_name,
                "type": "arangosearch",
                "links": {
                    semantic: {
                        "fields": {
                            "label": {
                                "analyzers": ["text_en"],
                            },
                        },
                    },
                },
            },
        ),
    )
    khipu = Khipu(db=live_db)

    try:
        khipu.watay(semantic, defn)
        view_names = {view["name"] for view in live_db.views()}
        assert view_name in view_names
    finally:
        if view_name in {view["name"] for view in live_db.views()}:
            live_db.delete_view(view_name)
        if live_db.has_collection(semantic):
            live_db.delete_collection(semantic)
