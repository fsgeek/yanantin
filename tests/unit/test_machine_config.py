"""Unit tests for the machine configuration collector/recorder pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.machine.linux import (
    MachineConfigCollector,
    MachineConfigData,
    MachineConfigRecorder,
    collect_and_record,
    collect_machine_config,
    render_machine_config,
    _get_machine_id,
)
from yanantin.transport.models import WranglerEnvelope


@pytest.fixture
def sample_machine_config() -> MachineConfigData:
    return MachineConfigData(
        hostname="test-host",
        fqdn="test-host.example.com",
        os_name="Linux",
        os_version="6.0.0-custom",
        os_release="6.0.0",
        architecture="x86_64",
        cpu_count=8,
        python_version="3.11.5",
        platform_string="Linux-6.0.0-custom-x86_64",
        machine_id="11112222333344445555666677778888",
        collected_at=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_envelope(sample_machine_config: MachineConfigData) -> WranglerEnvelope[MachineConfigData]:
    return WranglerEnvelope[MachineConfigData](
        data=sample_machine_config,
        provider_id=uuid4(),
    )


class TestMachineConfigData:
    def test_model_is_frozen_and_serializes(self, sample_machine_config: MachineConfigData) -> None:
        with pytest.raises(ValidationError):
            sample_machine_config.hostname = "mutated"  # type: ignore[attr-defined]

        serialized = sample_machine_config.model_dump_json()
        restored = MachineConfigData.model_validate_json(serialized)
        assert restored == sample_machine_config


class TestMachineIdHelper:
    def test_get_machine_id_returns_stable_non_empty_string(self) -> None:
        first = _get_machine_id()
        second = _get_machine_id()
        assert isinstance(first, str)
        assert first
        assert first == second


class TestMachineConfigCollector:
    def test_collect_returns_machine_config_data(self) -> None:
        collector = MachineConfigCollector()
        data = collector.collect()

        assert isinstance(data, MachineConfigData)
        assert data.machine_id == _get_machine_id()
        assert data.hostname
        assert data.collected_at.tzinfo is not None

    def test_provider_id_is_deterministic(self) -> None:
        first = MachineConfigCollector()
        second = MachineConfigCollector()

        provider_id = first.get_provider_id()
        assert isinstance(provider_id, UUID)
        assert provider_id == first.get_provider_id()
        assert provider_id == second.get_provider_id()


class TestMachineConfigRecorder:
    def test_record_stores_tensor_and_returns_uuid(self, sample_envelope: WranglerEnvelope[MachineConfigData]) -> None:
        backend = InMemoryBackend()
        recorder = MachineConfigRecorder(backend)

        tensor_id = recorder.record(sample_envelope)
        assert isinstance(tensor_id, UUID)

        stored = backend.get_tensor(tensor_id)
        assert stored.provenance.source.identifier == sample_envelope.provider_id
        assert len(stored.strands) == 2
        assert stored.strands[0].title == "Platform Identity"
        assert sample_envelope.data.hostname in stored.strands[0].content
        assert stored.strands[1].title == "System Configuration"
        assert f"os: {sample_envelope.data.os_name}" in stored.strands[1].content
        assert len(backend.list_tensors()) == 1

        # Canonical recorder also writes the machine entity and a has_snapshot
        # edge (machine entity -> tensor). The old collector.machine_config
        # recorder wrote neither; the migration adopts the edge-writing path.
        machine_uuid = UUID(sample_envelope.data.machine_id)
        entity = backend.get_entity(machine_uuid)
        assert entity.id == machine_uuid
        edges = backend.list_provenance_edges()
        assert len(edges) == 1
        assert edges[0].relation_type == "has_snapshot"
        assert edges[0].from_ref == f"entities/{machine_uuid}"
        assert edges[0].to_ref == f"tensors/{tensor_id}"


class TestConvenienceFunctions:
    def test_collect_machine_config_convenience_function(self) -> None:
        data = collect_machine_config()
        assert isinstance(data, MachineConfigData)
        assert data.machine_id == _get_machine_id()

    def test_collect_and_record_pipeline(self) -> None:
        backend = InMemoryBackend()
        tensor_id = collect_and_record(backend)

        assert isinstance(tensor_id, UUID)
        stored_ids = [tensor.id for tensor in backend.list_tensors()]
        assert tensor_id in stored_ids


class TestRenderMachineConfig:
    def test_render_machine_config_returns_expected_fields(
        self,
        sample_machine_config: MachineConfigData,
    ) -> None:
        rendered = render_machine_config(sample_machine_config)

        assert f"Hostname:    {sample_machine_config.hostname}" in rendered
        assert f"FQDN:        {sample_machine_config.fqdn}" in rendered
        assert f"Machine ID:  {sample_machine_config.machine_id}" in rendered
        assert f"OS:          {sample_machine_config.os_name} {sample_machine_config.os_release}" in rendered
        assert f"Kernel:      {sample_machine_config.os_version}" in rendered
        assert f"Arch:        {sample_machine_config.architecture}" in rendered
        assert f"CPUs:        {sample_machine_config.cpu_count}" in rendered
        assert f"Python:      {sample_machine_config.python_version}" in rendered
        assert sample_machine_config.collected_at.isoformat() in rendered
