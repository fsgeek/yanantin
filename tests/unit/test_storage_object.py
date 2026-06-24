from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from yanantin.collector.storage_object import StorageObject


def _valid_storage_object_kwargs():
    return {
        "object_identifier": uuid4(),
        "uri": "file:///tmp/x.txt",
        "source": uuid4(),
        "observed_at": datetime.now(timezone.utc),
    }


def test_storage_object_module_and_class_location():
    assert isinstance(StorageObject, type)
    assert StorageObject.model_config.get("extra") == "allow"


def test_required_spine_fields_present():
    kwargs = _valid_storage_object_kwargs()

    obj = StorageObject(**kwargs)

    assert isinstance(obj.object_identifier, UUID)
    assert obj.object_identifier == kwargs["object_identifier"]
    assert obj.uri == kwargs["uri"]
    assert obj.source == kwargs["source"]
    assert obj.observed_at == kwargs["observed_at"]


def test_missing_object_identifier_raises():
    kwargs = _valid_storage_object_kwargs()
    kwargs.pop("object_identifier")

    with pytest.raises(ValidationError):
        StorageObject(**kwargs)


def test_missing_uri_raises():
    kwargs = _valid_storage_object_kwargs()
    kwargs.pop("uri")

    with pytest.raises(ValidationError):
        StorageObject(**kwargs)


def test_missing_source_raises():
    kwargs = _valid_storage_object_kwargs()
    kwargs.pop("source")

    with pytest.raises(ValidationError):
        StorageObject(**kwargs)


def test_missing_observed_at_raises():
    kwargs = _valid_storage_object_kwargs()
    kwargs.pop("observed_at")

    with pytest.raises(ValidationError):
        StorageObject(**kwargs)


def test_file_timestamps_default_none():
    obj = StorageObject(**_valid_storage_object_kwargs())

    assert obj.created is None
    assert obj.modified is None
    assert obj.accessed is None
    assert obj.changed is None


def test_file_timestamps_accept_datetime():
    timestamp = datetime.now(timezone.utc)
    obj = StorageObject(
        **_valid_storage_object_kwargs(),
        created=timestamp,
        modified=timestamp,
        accessed=timestamp,
        changed=timestamp,
    )

    assert obj.created == timestamp
    assert obj.modified == timestamp
    assert obj.accessed == timestamp
    assert obj.changed == timestamp


def test_optional_size_and_label_default_none():
    obj = StorageObject(**_valid_storage_object_kwargs())

    assert obj.size is None
    assert obj.label is None


def test_optional_size_and_label_accept_values():
    obj = StorageObject(**_valid_storage_object_kwargs(), size=123, label="x.txt")

    assert obj.size == 123
    assert obj.label == "x.txt"


def test_semantic_attributes_defaults_empty_dict():
    obj = StorageObject(**_valid_storage_object_kwargs())

    assert obj.semantic_attributes == {}


def test_semantic_attributes_round_trips_arbitrary_key():
    semantic_attributes = {"mime_type": "text/plain", "page_count": 7}
    obj = StorageObject(
        **_valid_storage_object_kwargs(),
        semantic_attributes=semantic_attributes,
    )

    assert obj.semantic_attributes == semantic_attributes
    assert obj.model_dump()["semantic_attributes"] == semantic_attributes


def test_raw_defaults_empty_dict():
    obj = StorageObject(**_valid_storage_object_kwargs())

    assert obj.raw == {}


def test_raw_round_trips_blob():
    raw = {"st_ino": 999, "nested": {"a": 1}}
    obj = StorageObject(**_valid_storage_object_kwargs(), raw=raw)

    assert obj.raw == raw


def test_extra_allow_accepts_undeclared_top_level_field():
    obj = StorageObject(
        **_valid_storage_object_kwargs(),
        weird_provider_field="cloud-only",
    )

    assert obj.weird_provider_field == "cloud-only"
    assert obj.model_dump()["weird_provider_field"] == "cloud-only"


def test_to_contribution_fields_returns_model_dump_json():
    modified = datetime.now(timezone.utc)
    obj = StorageObject(
        **_valid_storage_object_kwargs(),
        modified=modified,
        weird_provider_field="cloud-only",
    )

    assert callable(obj.to_contribution_fields)
    assert obj.to_contribution_fields() == obj.model_dump(mode="json")


def test_no_canonical_timestamp_uuids_attribute():
    assert not hasattr(StorageObject, "CANONICAL_TIMESTAMP_UUIDS")
    assert "CANONICAL_TIMESTAMP_UUIDS" not in getattr(
        StorageObject,
        "model_fields",
        {},
    )
