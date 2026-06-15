"""Tests for machine identity persistence via MachineConfigRecorder."""
from unittest.mock import patch
from uuid import UUID

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.models.entities import EntityResolution
from yanantin.machine.linux import MachineConfigCollector, MachineConfigRecorder
from yanantin.transport.models import WranglerEnvelope

FAKE_MACHINE_ID = "8ae0edf526f3453ab1abaf04e1c75a4a"


def _make_envelope():
    collector = MachineConfigCollector()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        with patch("yanantin.machine.base._get_machine_id", return_value=FAKE_MACHINE_ID):
            data = collector.collect()
    return WranglerEnvelope(data=data, provider_id=collector.get_provider_id())


def test_record_writes_entity_resolution():
    backend = InMemoryBackend()
    recorder = MachineConfigRecorder(backend)
    envelope = _make_envelope()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        recorder.record(envelope)
    entity = backend.get_entity(UUID(FAKE_MACHINE_ID))
    assert isinstance(entity, EntityResolution)
    assert entity.identity_type == "machine.linux"
    assert entity.identity_data == {}
    assert not entity.redacted


def test_entity_id_equals_machine_id():
    backend = InMemoryBackend()
    recorder = MachineConfigRecorder(backend)
    envelope = _make_envelope()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        recorder.record(envelope)
    entity = backend.get_entity(UUID(FAKE_MACHINE_ID))
    assert entity.id == UUID(FAKE_MACHINE_ID)


def test_record_is_idempotent():
    """Second call must not raise — entity already exists, skip write."""
    backend = InMemoryBackend()
    recorder = MachineConfigRecorder(backend)
    envelope = _make_envelope()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        recorder.record(envelope)
        recorder.record(envelope)  # must not raise ImmutabilityError


def test_record_writes_has_snapshot_edge():
    backend = InMemoryBackend()
    recorder = MachineConfigRecorder(backend)
    envelope = _make_envelope()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        tensor_id = recorder.record(envelope)
    edges = backend.list_provenance_edges()
    assert len(edges) == 1
    assert edges[0].relation_type == "has_snapshot"
    # Canonical entity-key form: str(UUID(...)) is hyphenated and matches how
    # store_entity keys the document. An unhyphenated endpoint would dangle.
    assert edges[0].from_ref == f"entities/{UUID(FAKE_MACHINE_ID)}"
    assert edges[0].to_ref == f"tensors/{tensor_id}"


def test_record_writes_tensor():
    backend = InMemoryBackend()
    recorder = MachineConfigRecorder(backend)
    envelope = _make_envelope()
    with patch("yanantin.machine.linux._get_machine_id", return_value=FAKE_MACHINE_ID):
        tensor_id = recorder.record(envelope)
    tensor = backend.get_tensor(tensor_id)
    assert tensor is not None
