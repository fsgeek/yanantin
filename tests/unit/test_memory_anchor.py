"""Unit tests for the MemoryAnchorService.

Tests verify:
- Handle issuance sets referenced flag
- Cursor update sets updated flag
- Cursor update returns False when reference unchanged
- Write gate requires both flags (updated AND referenced)
- Flush stores anchor and advances handle
- Materialize resolves all providers (late binding)
- Materialize returns latest facts before anchor time
- Freeze creates tensor with expected strands
- Freeze tensor has provenance
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from yanantin.activity.anchor import MemoryAnchorService
from yanantin.activity.backends.memory import InMemoryActivityStreamStore
from yanantin.activity.models import FactRecord
from yanantin.apacheta.backends.memory import InMemoryBackend


# -- Fixtures ----------------------------------------------------------

@pytest.fixture
def store() -> InMemoryActivityStreamStore:
    return InMemoryActivityStreamStore()


@pytest.fixture
def service(store) -> MemoryAnchorService:
    return MemoryAnchorService(store)


@pytest.fixture
def provider_a() -> UUID:
    return uuid4()


@pytest.fixture
def provider_b() -> UUID:
    return uuid4()


@pytest.fixture
def base_time() -> datetime:
    return datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _store_fact(store, provider_id, timestamp, value=0):
    """Helper to store a fact and return it."""
    fact = FactRecord(
        provider_id=provider_id,
        timestamp=timestamp,
        data={"value": value},
    )
    store.store_fact(fact)
    return fact


# -- Flag behavior -----------------------------------------------------

class TestFlags:
    def test_get_handle_sets_referenced(self, service):
        """get_handle() should set referenced=True."""
        assert service._referenced is False
        service.get_handle()
        assert service._referenced is True

    def test_update_cursor_sets_updated(self, service, provider_a):
        """update_cursor() should set updated=True on new data."""
        assert service._updated is False
        result = service.update_cursor(provider_a, uuid4())
        assert result is True
        assert service._updated is True

    def test_update_cursor_returns_false_when_unchanged(self, service, provider_a):
        """update_cursor() with same reference should return False."""
        ref = uuid4()
        service.update_cursor(provider_a, ref)
        service._updated = False  # reset for test

        result = service.update_cursor(provider_a, ref)
        assert result is False
        assert service._updated is False


# -- Write gate --------------------------------------------------------

class TestWriteGate:
    def test_flush_requires_both_flags(self, service, provider_a):
        """Flush should return False unless both updated AND referenced."""
        # Neither flag set
        assert service.flush() is False

        # Only updated
        service.update_cursor(provider_a, uuid4())
        assert service.flush() is False

        # Reset and set only referenced
        service._updated = False
        service.get_handle()
        assert service.flush() is False

    def test_flush_stores_anchor_and_advances_handle(self, service, store, provider_a):
        """When both flags set, flush should store anchor and advance."""
        ref = uuid4()
        service.update_cursor(provider_a, ref)
        old_handle = service.get_handle()

        result = service.flush()
        assert result is True

        # Anchor should be in the store
        anchor = store.get_anchor(old_handle)
        assert anchor.handle == old_handle
        assert len(anchor.cursors) == 1
        assert anchor.cursors[0].provider == provider_a
        assert anchor.cursors[0].reference == ref

        # Handle should have advanced
        new_handle = service._handle
        assert new_handle != old_handle

        # Flags should be reset
        assert service._updated is False
        assert service._referenced is False


# -- Materialization ---------------------------------------------------

class TestMaterialize:
    def test_resolves_all_providers_late_binding(
        self, service, store, provider_a, provider_b, base_time,
    ):
        """materialize() should include providers registered after anchor creation."""
        # Store a fact for provider_a before the anchor
        _store_fact(store, provider_a, base_time, value=1)

        # Create and flush an anchor (only knows about provider_a via cursor)
        service.update_cursor(provider_a, uuid4())
        handle = service.get_handle()
        service.flush()

        # Now add a fact for provider_b (registered AFTER anchor)
        _store_fact(store, provider_b, base_time - timedelta(hours=1), value=2)

        # Materialize should discover provider_b (late binding)
        view = service.materialize(handle)
        assert provider_a in view.providers
        assert provider_b in view.providers
        assert provider_a in view.facts
        assert provider_b in view.facts

    def test_returns_latest_facts_before_anchor_time(
        self, service, store, provider_a, base_time,
    ):
        """materialize() should return the latest fact AT or BEFORE anchor time."""
        t_before = base_time - timedelta(hours=2)
        t_at = base_time - timedelta(hours=1)
        t_after = base_time + timedelta(hours=1)

        _store_fact(store, provider_a, t_before, value=1)
        _store_fact(store, provider_a, t_at, value=2)
        _store_fact(store, provider_a, t_after, value=3)

        # Create anchor — its timestamp will be "now", which is after all facts
        service.update_cursor(provider_a, uuid4())
        handle = service.get_handle()
        service.flush()

        # Get the anchor's actual timestamp
        anchor = store.get_anchor(handle)

        view = service.materialize(handle)
        # Should include the latest fact at or before anchor time
        assert provider_a in view.facts
        fact = view.facts[provider_a]
        # The anchor timestamp is "now" (after all test facts),
        # so the latest fact (value=3) should be returned
        assert fact.data["value"] == 3

    def test_materialize_no_facts_for_provider(
        self, service, store, provider_a, base_time,
    ):
        """materialize() should handle providers with no facts before anchor time."""
        # Store a fact after the anchor time
        _store_fact(store, provider_a, base_time + timedelta(hours=10), value=1)

        service.update_cursor(provider_a, uuid4())
        handle = service.get_handle()
        # Manually set a past timestamp for the test
        service._timestamp = base_time
        service.flush()

        view = service.materialize(handle)
        # Provider exists but no fact before anchor time
        assert provider_a in view.providers
        assert provider_a not in view.facts


# -- Freeze ------------------------------------------------------------

class TestFreeze:
    def test_freeze_creates_tensor_with_expected_strands(
        self, service, store, provider_a, base_time,
    ):
        """freeze() should create a tensor with summary and data strands."""
        _store_fact(store, provider_a, base_time, value=42)

        service.update_cursor(provider_a, uuid4())
        handle = service.get_handle()
        service.flush()

        apacheta = InMemoryBackend()
        tensor_id = service.freeze(handle, apacheta)

        tensor = apacheta.get_tensor(tensor_id)
        assert len(tensor.strands) == 2
        assert tensor.strands[0].title == "Anchor Summary"
        assert tensor.strands[1].title == "Anchor Data"
        assert "provider_count" in tensor.strands[0].content
        assert "fact_count" in tensor.strands[0].content

    def test_freeze_tensor_has_provenance(
        self, service, store, provider_a, base_time,
    ):
        """Frozen tensor should carry anchor-service provenance."""
        _store_fact(store, provider_a, base_time, value=1)

        service.update_cursor(provider_a, uuid4())
        handle = service.get_handle()
        service.flush()

        apacheta = InMemoryBackend()
        tensor_id = service.freeze(handle, apacheta)

        tensor = apacheta.get_tensor(tensor_id)
        assert tensor.provenance.author_model_family == "anchor-service"
        assert tensor.provenance.source.description == "Memory anchor freeze"
        assert "anchor" in tensor.lineage_tags
        assert "frozen-view" in tensor.lineage_tags
