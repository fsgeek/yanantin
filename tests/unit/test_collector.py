"""Unit tests for the collector/wrangler/recorder pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

import yanantin.transport.wranglers as wranglers_module
from yanantin.collector import (
    BatchWrangler,
    CollectorBase,
    DirectWrangler,
    ProviderRegistration,
    QueuedWrangler,
    RecorderBase,
    WranglerBase,
    WranglerEnvelope,
)


class SamplePayload(BaseModel):
    value: int


class DummyApachetaInterface:
    """Stand-in for ApachetaInterface to avoid importing yanantin.apacheta."""


class DummyWrangler(WranglerBase[SamplePayload]):
    def __init__(self) -> None:
        self._buffer: list[WranglerEnvelope[SamplePayload]] = []

    def deliver(self, envelope: WranglerEnvelope[SamplePayload]) -> None:  # pragma: no cover - helper only
        self._buffer.append(envelope)

    def receive(self) -> WranglerEnvelope[SamplePayload] | None:  # pragma: no cover - helper only
        return self._buffer.pop(0) if self._buffer else None

    @property
    def strategy_name(self) -> str:
        return "dummy"


@pytest.fixture
def provider_id() -> UUID:
    return uuid4()


@pytest.fixture
def envelope_factory(provider_id: UUID):
    def _factory(sequence: int, value: int | None = None) -> WranglerEnvelope[SamplePayload]:
        payload = SamplePayload(value=value if value is not None else sequence)
        return WranglerEnvelope[SamplePayload](
            data=payload,
            provider_id=provider_id,
            sequence_number=sequence,
        )

    return _factory


class TestCollectorModels:
    def test_provider_registration_is_frozen_and_roundtrips(self) -> None:
        registration = ProviderRegistration(
            provider_name="Sensor Pack",
            collector_description="Reads humidity via Modbus",
            recorder_description="Persists humidity in Apacheta",
            data_schema={"title": "SamplePayload", "type": "object"},
        )

        with pytest.raises(ValidationError):
            registration.provider_name = "mutated"  # type: ignore[attr-defined]

        dumped = registration.model_dump(mode="json")
        restored = ProviderRegistration.model_validate(dumped)
        assert restored == registration

    def test_wrangler_envelope_is_frozen_and_serializes(self, envelope_factory) -> None:
        envelope = envelope_factory(sequence=7, value=99)
        with pytest.raises(ValidationError):
            envelope.sequence_number = 0  # type: ignore[attr-defined]

        adapter = TypeAdapter(WranglerEnvelope[SamplePayload])
        serialized = adapter.dump_json(envelope)
        restored = adapter.validate_json(serialized)
        assert restored == envelope
        assert restored.data.value == 99


class TestDirectWrangler:
    def test_deliver_receive_cycle_and_provenance(self, envelope_factory) -> None:
        wrangler = DirectWrangler[SamplePayload]()
        assert wrangler.receive() is None

        original = envelope_factory(sequence=1)
        wrangler.deliver(original)
        delivered = wrangler.receive()

        assert delivered is not None
        assert delivered.sequence_number == original.sequence_number
        assert delivered.delivered_at is not None
        assert delivered.delivered_at.tzinfo is not None
        assert delivered.wrangler_strategy == "direct"
        assert original.delivered_at is None  # original remains untouched due to immutability
        assert wrangler.receive() is None


class TestBatchWrangler:
    def test_batch_wrangler_file_flow(self, tmp_path, envelope_factory, monkeypatch) -> None:
        staging = tmp_path / "collector_batch"
        wrangler = BatchWrangler(staging, SamplePayload)

        assert wrangler.receive() is None  # nonexistent directory treated as empty

        timestamps = [
            datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 10, 0, 1, tzinfo=timezone.utc),
        ]

        class FrozenDateTime:
            def __init__(self, values: list[datetime]) -> None:
                self._values = iter(values)

            def now(self, tz: timezone | None = None) -> datetime:
                return next(self._values)

        monkeypatch.setattr(wranglers_module, "datetime", FrozenDateTime(timestamps))

        first = envelope_factory(sequence=10)
        second = envelope_factory(sequence=11)
        wrangler.deliver(first)
        wrangler.deliver(second)

        tmp_files = list(staging.glob(".tmp_envelope_*.json"))
        assert tmp_files == []  # atomic rename cleaned up temporary files

        files = sorted(staging.glob("envelope_*.json"))
        assert len(files) == 2

        received_first = wrangler.receive()
        received_second = wrangler.receive()
        assert received_first is not None
        assert received_second is not None
        assert received_first.sequence_number == first.sequence_number
        assert received_second.sequence_number == second.sequence_number
        assert received_first.delivered_at is not None
        assert received_second.delivered_at is not None
        assert wrangler.receive() is None
        assert not list(staging.glob("envelope_*.json"))


class TestQueuedWrangler:
    def test_fifo_and_backpressure(self, envelope_factory) -> None:
        wrangler = QueuedWrangler[SamplePayload](maxlen=2)
        assert wrangler.receive() is None

        first = envelope_factory(sequence=1)
        second = envelope_factory(sequence=2)
        third = envelope_factory(sequence=3)

        wrangler.deliver(first)
        wrangler.deliver(second)
        assert wrangler.pending_count == 2

        wrangler.deliver(third)
        assert wrangler.pending_count == 2  # maxlen trims the oldest

        received_first = wrangler.receive()
        received_second = wrangler.receive()
        assert received_first is not None
        assert received_second is not None
        assert received_first.sequence_number == second.sequence_number
        assert received_second.sequence_number == third.sequence_number
        assert wrangler.pending_count == 0
        assert wrangler.receive() is None


class TestBaseClasses:
    @pytest.mark.parametrize(
        ("cls", "args"),
        [
            (CollectorBase, ()),
            (WranglerBase, ()),
            (RecorderBase, (DummyApachetaInterface(),)),
        ],
    )
    def test_abstract_bases_cannot_instantiate(self, cls, args) -> None:
        with pytest.raises(TypeError):
            cls(*args)  # type: ignore[misc]

    def test_stamp_delivery_populates_provenance(self, envelope_factory) -> None:
        wrangler = DummyWrangler()
        envelope = envelope_factory(sequence=42)
        stamped = wrangler.stamp_delivery(envelope)
        assert stamped.delivered_at is not None
        assert stamped.wrangler_strategy == "dummy"
        assert envelope.delivered_at is None
