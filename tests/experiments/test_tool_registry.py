from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, is_dataclass

import pytest

from yanantin.experiments.tools.apacheta_tools import find_objects_impl
from yanantin.experiments.tools.registry import ToolVariant, build_name_effect_variants


def _schema(name: str) -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": "test schema",
            "parameters": {"type": "object", "properties": {}},
        },
    }


def _impl(_apacheta: object, _args: dict[str, object], _budget: object) -> dict[str, str]:
    return {"impl": "primary"}


def _extra_impl(
    _apacheta: object, _args: dict[str, object], _budget: object
) -> dict[str, str]:
    return {"impl": "extra"}


EXPECTED_VARIANTS = (
    ("find_objects_v1", "find_objects"),
    ("search_v1", "search"),
    ("query_v1", "query"),
)


def test_tool_variant_is_frozen_dataclass_with_expected_field_layout() -> None:
    assert is_dataclass(ToolVariant)

    dataclass_fields = fields(ToolVariant)
    assert [field.name for field in dataclass_fields] == [
        "variant_id",
        "function_name",
        "schema",
        "impl",
        "extra_schemas",
        "extra_impls",
    ]
    assert all(field.init for field in dataclass_fields)
    assert dataclass_fields[4].default == ()
    assert dataclass_fields[5].default == ()


def test_multi_tool_variant_advertises_all_schemas_and_dispatches_by_name() -> None:
    primary_schema = _schema("query")
    extra_schema = _schema("request_capability")
    variant = ToolVariant(
        variant_id="multi_tool_v1",
        function_name="query",
        schema=primary_schema,
        impl=_impl,
        extra_schemas=(extra_schema,),
        extra_impls=(("request_capability", _extra_impl),),
    )

    assert variant.all_schemas() == [primary_schema, extra_schema]
    assert variant.dispatch() == {
        "query": _impl,
        "request_capability": _extra_impl,
    }


def test_empty_extra_variant_preserves_single_tool_contract() -> None:
    schema = _schema("query")
    variant = ToolVariant(
        variant_id="single_tool_v1",
        function_name="query",
        schema=schema,
        impl=_impl,
    )

    assert variant.extra_schemas == ()
    assert variant.extra_impls == ()
    assert variant.all_schemas() == [schema]
    assert variant.dispatch() == {"query": _impl}


def test_build_name_effect_variants_has_expected_ids_names_and_order() -> None:
    variants = build_name_effect_variants()

    assert len(variants) == 3
    assert [(v.variant_id, v.function_name) for v in variants] == list(EXPECTED_VARIANTS)


def test_variants_share_identical_impl_callable_and_match_exported_impl() -> None:
    variants = build_name_effect_variants()

    assert variants[0].impl is variants[1].impl is variants[2].impl
    assert variants[0].impl is find_objects_impl


def test_variants_advertise_distinct_function_names_in_schema() -> None:
    variants = build_name_effect_variants()

    schema_names = [variant.schema["function"]["name"] for variant in variants]
    function_names = [variant.function_name for variant in variants]

    assert schema_names == function_names
    assert schema_names == [expected_name for _, expected_name in EXPECTED_VARIANTS]
    assert len(set(schema_names)) == len(schema_names)


def test_variant_instances_are_frozen() -> None:
    variant = build_name_effect_variants()[0]

    with pytest.raises((AttributeError, FrozenInstanceError)):
        variant.variant_id = "mutated"
