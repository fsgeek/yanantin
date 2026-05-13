import copy
import json

from yanantin.experiments.tools.schemas import (
    FIND_OBJECTS_DESCRIPTION,
    FIND_OBJECTS_PARAMETERS,
    find_objects_schema,
)


VARIANT_NAMES = ("find_objects", "search", "query")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def test_name_effect_variants_are_identical_except_function_name() -> None:
    schemas = {name: find_objects_schema(name) for name in VARIANT_NAMES}

    base_name = VARIANT_NAMES[0]
    base = copy.deepcopy(schemas[base_name])
    base["function"]["name"] = "__NAME__"

    for name in VARIANT_NAMES[1:]:
        candidate = copy.deepcopy(schemas[name])
        candidate["function"]["name"] = "__NAME__"
        assert _canonical_json(candidate) == _canonical_json(base)


def test_find_objects_schema_openai_shape_and_parameter_contract() -> None:
    schema = find_objects_schema("find_objects")

    assert schema["type"] == "function"
    function = schema["function"]
    assert function["name"] == "find_objects"
    assert function["description"] == FIND_OBJECTS_DESCRIPTION
    assert function["parameters"] == FIND_OBJECTS_PARAMETERS

    parameters = function["parameters"]
    assert parameters["type"] == "object"

    properties = parameters["properties"]
    assert set(properties) == {"matching", "limit", "cursor"}

    matching = properties["matching"]
    assert matching["type"] == "object"
    assert set(matching["properties"]) == {
        "author_instance_id",
        "lineage_tag",
        "has_field",
    }
    assert matching.get("required", []) == []
    for field_name in matching["properties"]:
        assert matching["properties"][field_name] == {"type": "string"}

    assert properties["limit"] == {"type": "integer"}
    assert properties["cursor"] == {"type": ["string", "null"]}

    json.dumps(schema)


def test_find_objects_schema_returns_fresh_deep_parameters_each_call() -> None:
    first = find_objects_schema("find_objects")
    second = find_objects_schema("find_objects")

    first_params = first["function"]["parameters"]
    second_params = second["function"]["parameters"]

    assert first_params is not second_params
    assert first_params["properties"] is not second_params["properties"]
    assert (
        first_params["properties"]["matching"]
        is not second_params["properties"]["matching"]
    )
    assert (
        first_params["properties"]["matching"]["properties"]
        is not second_params["properties"]["matching"]["properties"]
    )

    first_params["properties"]["matching"]["properties"]["author_instance_id"]["type"] = (
        "integer"
    )
    first_params["properties"]["limit"]["minimum"] = 1

    third = find_objects_schema("find_objects")
    third_params = third["function"]["parameters"]

    assert (
        third_params["properties"]["matching"]["properties"]["author_instance_id"]["type"]
        == "string"
    )
    assert "minimum" not in third_params["properties"]["limit"]


def test_factory_preserves_constant_templates_when_result_is_mutated() -> None:
    description_before = FIND_OBJECTS_DESCRIPTION
    parameters_before = copy.deepcopy(FIND_OBJECTS_PARAMETERS)

    schema = find_objects_schema("query")
    schema["function"]["description"] = "mutated"
    schema["function"]["parameters"]["properties"]["limit"]["minimum"] = 99
    schema["function"]["parameters"]["properties"]["matching"]["properties"][
        "has_field"
    ]["type"] = "integer"

    assert FIND_OBJECTS_DESCRIPTION == description_before
    assert FIND_OBJECTS_PARAMETERS == parameters_before
