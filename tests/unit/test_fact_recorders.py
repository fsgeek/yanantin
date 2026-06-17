"""Unit tests for the fact recorders.

Tests the pipeline: synthetic collector -> wrangler -> fact recorder -> store.
Each recorder decomposes batch data into individual facts with appropriate
timestamps and content hashes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.recorder.base import FactRecorderBase
from yanantin.collector.storage.local.checksum import SyntheticChecksumCollector
from yanantin.recorder.storage.local.checksum import ChecksumFactRecorder
from yanantin.collector.storage.cloud.dropbox import SyntheticDropboxCollector
from yanantin.recorder.storage.cloud.dropbox.fact_recorder import DropboxFactRecorder
from yanantin.collector.storage.local.linux import SyntheticFilesystemCollector
from yanantin.recorder.storage.local.linux.fact_recorder import FilesystemFactRecorder
from yanantin.collector.activity.linux import SyntheticFsEventCollector
from yanantin.recorder.activity.linux.fact_recorder import FsEventFactRecorder
from yanantin.transport.models import WranglerEnvelope
from yanantin.transport.wranglers import DirectWrangler


# -- Fixtures ----------------------------------------------------------

@pytest.fixture
def activity_store() -> InMemoryActivityStreamStore:
    return InMemoryActivityStreamStore()


def _collect_and_wrangle(collector):
    """Run a collector through a DirectWrangler and return the received envelope."""
    data = collector.collect()
    envelope = WranglerEnvelope(
        data=data,
        provider_id=collector.get_provider_id(),
    )
    wrangler = DirectWrangler()
    wrangler.deliver(envelope)
    received = wrangler.receive()
    assert received is not None
    return received


# -- Filesystem fact recorder ------------------------------------------

class TestFilesystemFactRecorder:
    def test_stores_one_fact_per_entry(self, activity_store):
        collector = SyntheticFilesystemCollector(seed=42)
        envelope = _collect_and_wrangle(collector)
        recorder = FilesystemFactRecorder(activity_store)

        count = recorder.record_facts(envelope)
        expected_entries = len(envelope.data.entries)

        assert count == expected_entries
        assert activity_store.count_facts() == expected_entries

    def test_fact_timestamp_matches_modified_time(self, activity_store):
        collector = SyntheticFilesystemCollector(seed=42)
        envelope = _collect_and_wrangle(collector)
        recorder = FilesystemFactRecorder(activity_store)

        recorder.record_facts(envelope)

        # Query the first provider's facts
        provider_id = envelope.provider_id
        facts = activity_store.query_range(provider_id)
        assert len(facts) > 0

        # Each fact's timestamp should match a modified time from the entries
        entry_mtimes = {e.timestamps.modified for e in envelope.data.entries}
        for fact in facts:
            assert fact.timestamp in entry_mtimes

    def test_fact_has_content_hash(self, activity_store):
        collector = SyntheticFilesystemCollector(seed=42)
        envelope = _collect_and_wrangle(collector)
        recorder = FilesystemFactRecorder(activity_store)

        recorder.record_facts(envelope)

        facts = activity_store.query_range(envelope.provider_id)
        for fact in facts:
            assert fact.content_hash != ""
            assert len(fact.content_hash) == 16  # SHA-256 prefix


# -- Checksum fact recorder --------------------------------------------

class TestChecksumFactRecorder:
    def test_stores_one_fact(self, activity_store):
        collector = SyntheticChecksumCollector(seed=42)
        envelope = _collect_and_wrangle(collector)
        recorder = ChecksumFactRecorder(activity_store)

        count = recorder.record_facts(envelope)
        assert count == 1
        assert activity_store.count_facts() == 1

    def test_fact_timestamp_matches_collected_at(self, activity_store):
        collector = SyntheticChecksumCollector(seed=42)
        envelope = _collect_and_wrangle(collector)
        recorder = ChecksumFactRecorder(activity_store)

        recorder.record_facts(envelope)

        facts = activity_store.query_range(envelope.provider_id)
        assert len(facts) == 1
        assert facts[0].timestamp == envelope.data.collected_at

    def test_fact_data_contains_checksums(self, activity_store):
        collector = SyntheticChecksumCollector(seed=42)
        envelope = _collect_and_wrangle(collector)
        recorder = ChecksumFactRecorder(activity_store)

        recorder.record_facts(envelope)

        facts = activity_store.query_range(envelope.provider_id)
        assert "checksums" in facts[0].data
        assert "file_path" in facts[0].data


# -- Filesystem event fact recorder ------------------------------------

class TestFsEventFactRecorder:
    def test_stores_one_fact_per_event(self, activity_store):
        collector = SyntheticFsEventCollector(seed=42)
        envelope = _collect_and_wrangle(collector)
        recorder = FsEventFactRecorder(activity_store)

        count = recorder.record_facts(envelope)
        expected_events = len(envelope.data.events)

        assert count == expected_events
        assert activity_store.count_facts() == expected_events

    def test_fact_timestamp_matches_detected_at(self, activity_store):
        collector = SyntheticFsEventCollector(seed=42)
        envelope = _collect_and_wrangle(collector)
        recorder = FsEventFactRecorder(activity_store)

        recorder.record_facts(envelope)

        facts = activity_store.query_range(envelope.provider_id)
        event_times = {e.detected_at for e in envelope.data.events}
        for fact in facts:
            assert fact.timestamp in event_times


# -- Dropbox fact recorder ---------------------------------------------

class TestDropboxFactRecorder:
    def test_stores_one_fact_per_entry(self, activity_store):
        collector = SyntheticDropboxCollector(seed=42)
        envelope = _collect_and_wrangle(collector)
        recorder = DropboxFactRecorder(activity_store)

        count = recorder.record_facts(envelope)
        expected_entries = len(envelope.data.entries)

        assert count == expected_entries
        assert activity_store.count_facts() == expected_entries

    def test_file_fact_uses_modified_time(self, activity_store):
        collector = SyntheticDropboxCollector(seed=42)
        envelope = _collect_and_wrangle(collector)
        recorder = DropboxFactRecorder(activity_store)

        recorder.record_facts(envelope)

        facts = activity_store.query_range(envelope.provider_id)
        # Files should use modified_time, folders use collected_at
        for fact in facts:
            entry_type = fact.data.get("entry_type")
            if entry_type == "file":
                # File entries should have a modified_time
                assert fact.data.get("modified_time") is not None


# -- Content hash determinism ------------------------------------------

class TestContentHashDeterminism:
    def test_fact_content_hash_is_deterministic(self, activity_store):
        """Same input data should produce the same content hash."""
        collector = SyntheticChecksumCollector(seed=42)
        envelope = _collect_and_wrangle(collector)

        recorder1 = ChecksumFactRecorder(activity_store)
        recorder1.record_facts(envelope)

        store2 = InMemoryActivityStreamStore()
        recorder2 = ChecksumFactRecorder(store2)
        # Re-wrangle with same collector to get same data
        collector2 = SyntheticChecksumCollector(seed=42)
        envelope2 = _collect_and_wrangle(collector2)
        recorder2.record_facts(envelope2)

        facts1 = activity_store.query_range(envelope.provider_id)
        facts2 = store2.query_range(envelope2.provider_id)

        assert len(facts1) == len(facts2)
        assert facts1[0].content_hash == facts2[0].content_hash


# -- Recorder identity -------------------------------------------------

class TestRecorderIdentity:
    def test_filesystem_fact_recorder_has_stable_id(self, activity_store):
        r1 = FilesystemFactRecorder(activity_store)
        r2 = FilesystemFactRecorder(activity_store)
        assert r1.get_recorder_id() == r2.get_recorder_id()

    def test_checksum_fact_recorder_has_stable_id(self, activity_store):
        r1 = ChecksumFactRecorder(activity_store)
        r2 = ChecksumFactRecorder(activity_store)
        assert r1.get_recorder_id() == r2.get_recorder_id()

    def test_fs_event_fact_recorder_has_stable_id(self, activity_store):
        r1 = FsEventFactRecorder(activity_store)
        r2 = FsEventFactRecorder(activity_store)
        assert r1.get_recorder_id() == r2.get_recorder_id()

    def test_dropbox_fact_recorder_has_stable_id(self, activity_store):
        r1 = DropboxFactRecorder(activity_store)
        r2 = DropboxFactRecorder(activity_store)
        assert r1.get_recorder_id() == r2.get_recorder_id()

    def test_fact_recorders_have_distinct_ids(self, activity_store):
        ids = {
            FilesystemFactRecorder(activity_store).get_recorder_id(),
            ChecksumFactRecorder(activity_store).get_recorder_id(),
            FsEventFactRecorder(activity_store).get_recorder_id(),
            DropboxFactRecorder(activity_store).get_recorder_id(),
        }
        assert len(ids) == 4
