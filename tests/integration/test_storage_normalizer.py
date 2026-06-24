from datetime import datetime, timezone
from uuid import uuid4

from yanantin.collector.storage.local.linux.models import (
    FileEntryData,
    FileTimestamps,
)
from yanantin.collector.storage_object import StorageObject
from yanantin.recorder.storage.local.linux.normalize import normalize_file_entry


def file_entry(
    *,
    name: str = "x.txt",
    uri: str = "file:///synthetic/root/x.txt",
) -> FileEntryData:
    modified = datetime(2026, 6, 19, 12, 30, tzinfo=timezone.utc)
    timestamps = FileTimestamps(
        created=modified,
        modified=modified,
        accessed=modified,
        changed=modified,
    )
    return FileEntryData(
        path=f"/synthetic/root/{name}",
        name=name,
        uri=uri,
        is_directory=False,
        is_symlink=False,
        size=123,
        mode=33188,
        file_attributes=("S_IFREG", "S_IRUSR"),
        timestamps=timestamps,
        inode=101,
        device=202,
        link_target=None,
    )


def test_spine_fields_map_from_file_entry():
    entry = file_entry()
    source = uuid4()

    before = datetime.now(timezone.utc)
    obj = normalize_file_entry(entry, source=source)
    after = datetime.now(timezone.utc)

    assert isinstance(obj, StorageObject)
    assert obj.modified == entry.timestamps.modified
    assert obj.created == entry.timestamps.created
    assert obj.accessed == entry.timestamps.accessed
    assert obj.changed == entry.timestamps.changed
    assert obj.label == entry.name
    assert obj.size == entry.size
    assert obj.uri == entry.uri
    assert obj.source == source
    assert isinstance(obj.observed_at, datetime)
    assert before <= obj.observed_at <= after


def test_posix_specifics_land_in_semantic_attributes():
    entry = file_entry()
    source = uuid4()

    obj = normalize_file_entry(entry, source=source)

    assert obj.semantic_attributes["inode"] == entry.inode
    assert obj.semantic_attributes["device"] == entry.device
    assert obj.semantic_attributes["mode"] == entry.mode
    assert obj.semantic_attributes["file_attributes"] == entry.file_attributes
    assert obj.semantic_attributes["link_target"] == entry.link_target


def test_raw_preserves_original_file_entry_json_dump():
    entry = file_entry()
    source = uuid4()

    obj = normalize_file_entry(entry, source=source)

    assert obj.raw == entry.model_dump(mode="json")


def test_object_identifier_is_idempotent_for_source_and_uri():
    entry = file_entry()
    same_source = uuid4()
    different_source = uuid4()
    different_uri_entry = file_entry(
        name="y.txt",
        uri="file:///synthetic/root/y.txt",
    )

    first = normalize_file_entry(entry, source=same_source)
    second = normalize_file_entry(entry, source=same_source)
    different_source_obj = normalize_file_entry(entry, source=different_source)
    different_uri_obj = normalize_file_entry(different_uri_entry, source=same_source)

    assert first.object_identifier == second.object_identifier
    assert first.object_identifier != different_source_obj.object_identifier
    assert first.object_identifier != different_uri_obj.object_identifier
