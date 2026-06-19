from pydantic import BaseModel

from yanantin.core.collection_definition import CollectionDefinition, arangodb_schema


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
