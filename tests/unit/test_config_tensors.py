"""Unit tests for config-as-tensors module.

Tests the ConfigTensor model, roundtrip conversion through TensorRecord,
and storage/retrieval via InMemoryBackend.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.config import (
    DEFAULT_CONFIGS,
    ConfigTensor,
    _config_to_tensor,
    _tensor_to_config,
    get_config_history,
    get_current_config,
    store_config,
)
from yanantin.apacheta.models.provenance import ProvenanceEnvelope
from yanantin.apacheta.models.tensor import TensorRecord


@pytest.fixture
def backend():
    return InMemoryBackend()


@pytest.fixture
def sample_config():
    return ConfigTensor(
        config_domain="chasqui.pulse",
        settings={
            "min_scout_interval": 300,
            "heartbeat_interval": 21600,
            "verify_count": 3,
        },
        reasoning="Initial configuration for Chasqui heartbeat.",
    )


class TestConfigTensorCreation:
    def test_config_tensor_creation(self, sample_config):
        """Construct a ConfigTensor with valid data."""
        assert sample_config.config_domain == "chasqui.pulse"
        assert sample_config.settings["min_scout_interval"] == 300
        assert sample_config.settings["heartbeat_interval"] == 21600
        assert sample_config.settings["verify_count"] == 3
        assert sample_config.reasoning == "Initial configuration for Chasqui heartbeat."
        assert sample_config.previous_config_id is None
        assert isinstance(sample_config.provenance, ProvenanceEnvelope)
        assert isinstance(sample_config.timestamp, datetime)


class TestConfigTensorRoundtrip:
    def test_config_tensor_roundtrip(self, sample_config):
        """ConfigTensor -> TensorRecord -> ConfigTensor preserves settings."""
        tensor = _config_to_tensor(sample_config)
        assert isinstance(tensor, TensorRecord)
        assert "config" in tensor.lineage_tags
        assert "chasqui.pulse" in tensor.lineage_tags

        restored = _tensor_to_config(tensor)
        assert restored is not None
        assert restored.config_domain == sample_config.config_domain
        assert restored.settings == sample_config.settings

    def test_config_with_reasoning(self, sample_config):
        """Verify reasoning survives the roundtrip as narrative_body."""
        tensor = _config_to_tensor(sample_config)
        assert tensor.narrative_body == sample_config.reasoning

        restored = _tensor_to_config(tensor)
        assert restored is not None
        assert restored.reasoning == sample_config.reasoning

    def test_settings_types_preserved(self):
        """int, float, str, bool, list values all survive roundtrip."""
        config = ConfigTensor(
            config_domain="type.test",
            settings={
                "an_int": 42,
                "a_float": 3.14,
                "a_str": "hello",
                "a_bool": True,
                "a_list": [1, 2, 3],
            },
            reasoning="Testing type preservation through ast.literal_eval.",
        )
        tensor = _config_to_tensor(config)
        restored = _tensor_to_config(tensor)

        assert restored is not None
        assert restored.settings["an_int"] == 42
        assert isinstance(restored.settings["an_int"], int)
        assert restored.settings["a_float"] == 3.14
        assert isinstance(restored.settings["a_float"], float)
        assert restored.settings["a_str"] == "hello"
        assert isinstance(restored.settings["a_str"], str)
        assert restored.settings["a_bool"] is True
        assert isinstance(restored.settings["a_bool"], bool)
        assert restored.settings["a_list"] == [1, 2, 3]
        assert isinstance(restored.settings["a_list"], list)


class TestStoreAndRetrieve:
    def test_store_and_retrieve_config(self, backend, sample_config):
        """Store a config in InMemoryBackend, retrieve with get_current_config."""
        tensor_id = store_config(backend, sample_config)
        assert tensor_id is not None

        retrieved = get_current_config(backend, "chasqui.pulse")
        assert retrieved is not None
        assert retrieved.config_domain == "chasqui.pulse"
        assert retrieved.settings == sample_config.settings
        assert retrieved.reasoning == sample_config.reasoning

    def test_unknown_domain_returns_none(self, backend):
        """get_current_config for nonexistent domain returns None."""
        result = get_current_config(backend, "nonexistent.domain")
        assert result is None


class TestConfigHistory:
    def test_config_history(self, backend):
        """Store two configs for same domain, verify get_config_history returns both newest-first."""
        config_a = ConfigTensor(
            config_domain="chasqui.pulse",
            settings={"min_scout_interval": 300},
            reasoning="First configuration.",
            provenance=ProvenanceEnvelope(
                timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
            ),
            timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        store_config(backend, config_a)

        config_b = ConfigTensor(
            config_domain="chasqui.pulse",
            settings={"min_scout_interval": 600},
            reasoning="Increased interval after load analysis.",
            provenance=ProvenanceEnvelope(
                timestamp=datetime(2026, 2, 10, tzinfo=timezone.utc),
            ),
            timestamp=datetime(2026, 2, 10, tzinfo=timezone.utc),
        )
        store_config(backend, config_b)

        history = get_config_history(backend, "chasqui.pulse")
        assert len(history) == 2
        # Newest first
        assert history[0].settings["min_scout_interval"] == 600
        assert history[1].settings["min_scout_interval"] == 300

    def test_config_immutability(self, backend):
        """Storing same config domain twice doesn't overwrite — both exist."""
        config_a = ConfigTensor(
            config_domain="test.domain",
            settings={"key": "value_a"},
            reasoning="First version.",
            provenance=ProvenanceEnvelope(
                timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        config_b = ConfigTensor(
            config_domain="test.domain",
            settings={"key": "value_b"},
            reasoning="Second version.",
            provenance=ProvenanceEnvelope(
                timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
            ),
            timestamp=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )

        id_a = store_config(backend, config_a)
        id_b = store_config(backend, config_b)

        assert id_a != id_b

        history = get_config_history(backend, "test.domain")
        assert len(history) == 2

        # Both values survive
        all_values = {h.settings["key"] for h in history}
        assert all_values == {"value_a", "value_b"}


class TestPreviousConfigChain:
    def test_previous_config_id_chain(self, backend):
        """Store config A, then config B pointing to A, verify the chain."""
        config_a = ConfigTensor(
            config_domain="chain.test",
            settings={"retry_limit": 3},
            reasoning="Initial retry config.",
            provenance=ProvenanceEnvelope(
                timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
            ),
            timestamp=datetime(2026, 2, 1, tzinfo=timezone.utc),
        )
        id_a = store_config(backend, config_a)

        config_b = ConfigTensor(
            config_domain="chain.test",
            settings={"retry_limit": 5},
            reasoning="Increased retries after observing transient failures.",
            previous_config_id=id_a,
            provenance=ProvenanceEnvelope(
                timestamp=datetime(2026, 2, 5, tzinfo=timezone.utc),
            ),
            timestamp=datetime(2026, 2, 5, tzinfo=timezone.utc),
        )
        store_config(backend, config_b)

        current = get_current_config(backend, "chain.test")
        assert current is not None
        assert current.settings["retry_limit"] == 5
        assert current.previous_config_id == id_a

        # Verify the chain through the stored tensor
        tensor_a = backend.get_tensor(id_a)
        assert tensor_a.provenance.predecessors_in_scope == ()


class TestDefaultConfigs:
    def test_default_configs_exist(self):
        """DEFAULT_CONFIGS has expected domains and keys."""
        assert "chasqui.pulse" in DEFAULT_CONFIGS

        pulse = DEFAULT_CONFIGS["chasqui.pulse"]
        assert "min_scout_interval" in pulse
        assert "heartbeat_interval" in pulse
        assert "verify_count" in pulse
        assert "scout_max_tokens" in pulse
        assert "scout_temperature" in pulse
        assert "verify_temperature" in pulse

        # Verify types are sensible
        assert isinstance(pulse["min_scout_interval"], int)
        assert isinstance(pulse["scout_temperature"], float)
