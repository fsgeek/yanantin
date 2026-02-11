"""Independent tests for ApachetaGatewayClient — written by test author, not builder.

These tests probe what the builder might have gotten wrong:
- HTTP method correctness (GET vs POST)
- URL path construction and trailing slash handling
- Request body serialization (model_dump with mode="json")
- Response deserialization back to Pydantic models
- Error mapping: HTTP status codes → ApachetaError subclasses
- API key header presence/absence
- Timeout configuration
- Context manager protocol
- close() method behavior
- All 34 abstract interface methods + client-specific methods

IMPORTANT: These tests mock httpx to avoid requiring a running Pukara server.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import Mock, patch
from uuid import UUID, uuid4

import httpx
import pytest

from yanantin.apacheta.clients.gateway import ApachetaGatewayClient
from yanantin.apacheta.interface.errors import (
    AccessDeniedError,
    ApachetaError,
    ImmutabilityError,
    InterfaceVersionError,
    NotFoundError,
)
from yanantin.apacheta.models import (
    BootstrapRecord,
    CompositionEdge,
    CorrectionRecord,
    DeclaredLoss,
    DissentRecord,
    EntityResolution,
    EpistemicMetadata,
    KeyClaim,
    LossCategory,
    NegationRecord,
    ProvenanceEnvelope,
    RelationType,
    SchemaEvolutionRecord,
    StrandRecord,
    TensorRecord,
)


# ── Test Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def sample_tensor():
    """Create a sample TensorRecord for testing."""
    return TensorRecord(
        provenance=ProvenanceEnvelope(
            author_model_family="claude",
            timestamp=datetime(2026, 2, 10, tzinfo=timezone.utc),
        ),
        preamble="Test tensor",
        strands=(
            StrandRecord(
                strand_index=0,
                title="Test Strand",
                topics=("testing",),
                key_claims=(
                    KeyClaim(
                        text="Tests validate correctness",
                        epistemic=EpistemicMetadata(truth=0.95),
                    ),
                ),
            ),
        ),
        lineage_tags=("test-sequence",),
    )


@pytest.fixture
def sample_composition_edge():
    """Create a sample CompositionEdge for testing."""
    return CompositionEdge(
        from_tensor=uuid4(),
        to_tensor=uuid4(),
        relation_type=RelationType.COMPOSES_WITH,
        ordering=1,
    )


@pytest.fixture
def sample_correction():
    """Create a sample CorrectionRecord for testing."""
    return CorrectionRecord(
        target_tensor=uuid4(),
        target_strand_index=0,
        target_claim_id=uuid4(),
        original_claim="Original claim",
        corrected_claim="Corrected claim",
        evidence="New evidence emerged",
    )


@pytest.fixture
def sample_dissent():
    """Create a sample DissentRecord for testing."""
    return DissentRecord(
        target_tensor=uuid4(),
        target_claim_id=uuid4(),
        alternative_framework="Alternative framework",
        reasoning="Different perspective",
    )


@pytest.fixture
def sample_negation():
    """Create a sample NegationRecord for testing."""
    return NegationRecord(
        tensor_a=uuid4(),
        tensor_b=uuid4(),
        reasoning="These tensors conflict",
    )


@pytest.fixture
def sample_bootstrap():
    """Create a sample BootstrapRecord for testing."""
    return BootstrapRecord(
        instance_id="test-instance",
        context_budget=8000.0,
        task="Testing bootstrap",
        tensors_selected=(uuid4(), uuid4()),
        strands_selected=(0, 1),
        what_was_omitted="Some strands omitted",
    )


@pytest.fixture
def sample_evolution():
    """Create a sample SchemaEvolutionRecord for testing."""
    return SchemaEvolutionRecord(
        from_version="v1",
        to_version="v2",
        fields_added=("new_field",),
        fields_removed=("old_field",),
        migration_notes="Added new_field, removed old_field",
    )


@pytest.fixture
def sample_entity():
    """Create a sample EntityResolution for testing."""
    return EntityResolution(
        entity_uuid=uuid4(),
        identity_type="person",
        identity_data={"name": "Test User"},
        redacted=False,
    )


# ── Client Initialization Tests ──────────────────────────────────────


class TestClientInitialization:
    """Test client construction and configuration."""

    def test_init_strips_trailing_slash_from_base_url(self):
        """Verify base_url trailing slash is removed."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000/")
        assert client.base_url == "http://localhost:8000"

    def test_init_preserves_base_url_without_trailing_slash(self):
        """Verify base_url without trailing slash is preserved."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        assert client.base_url == "http://localhost:8000"

    def test_init_with_api_key_sets_header(self):
        """Verify API key is included in headers when provided."""
        client = ApachetaGatewayClient(
            base_url="http://localhost:8000",
            api_key="test-key-123",
        )
        assert client._headers == {"X-API-Key": "test-key-123"}

    def test_init_without_api_key_has_empty_headers(self):
        """Verify headers are empty when no API key is provided."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        assert client._headers == {}

    def test_init_sets_timeout(self):
        """Verify timeout is passed to httpx.Client."""
        with patch("yanantin.apacheta.clients.gateway.httpx.Client") as MockClient:
            ApachetaGatewayClient(
                base_url="http://localhost:8000",
                timeout=60.0,
            )
            MockClient.assert_called_once_with(
                base_url="http://localhost:8000",
                headers={},
                timeout=60.0,
            )

    def test_init_default_timeout_is_30_seconds(self):
        """Verify default timeout is 30 seconds."""
        with patch("yanantin.apacheta.clients.gateway.httpx.Client") as MockClient:
            ApachetaGatewayClient(base_url="http://localhost:8000")
            MockClient.assert_called_once_with(
                base_url="http://localhost:8000",
                headers={},
                timeout=30.0,
            )


# ── Context Manager Tests ─────────────────────────────────────────────


class TestContextManager:
    """Test context manager protocol."""

    def test_context_manager_returns_self(self):
        """Verify __enter__ returns the client instance."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        with client as ctx:
            assert ctx is client

    def test_context_manager_closes_on_exit(self):
        """Verify __exit__ calls close()."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        with patch.object(client._client, "close") as mock_close:
            with client:
                pass
            mock_close.assert_called_once()

    def test_close_method_closes_httpx_client(self):
        """Verify close() calls httpx.Client.close()."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        with patch.object(client._client, "close") as mock_close:
            client.close()
            mock_close.assert_called_once()


# ── Error Handling Tests ──────────────────────────────────────────────


class TestErrorHandling:
    """Test HTTP status code to exception mapping."""

    def test_409_raises_immutability_error(self):
        """Verify 409 Conflict maps to ImmutabilityError."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        response = Mock(spec=httpx.Response)
        response.status_code = 409
        response.json.return_value = {"detail": "Duplicate UUID"}

        with pytest.raises(ImmutabilityError, match="Duplicate UUID"):
            client._handle_error(response)

    def test_404_raises_not_found_error(self):
        """Verify 404 Not Found maps to NotFoundError."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        response = Mock(spec=httpx.Response)
        response.status_code = 404
        response.json.return_value = {"detail": "Tensor not found"}

        with pytest.raises(NotFoundError, match="Tensor not found"):
            client._handle_error(response)

    def test_403_raises_access_denied_error(self):
        """Verify 403 Forbidden maps to AccessDeniedError."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        response = Mock(spec=httpx.Response)
        response.status_code = 403
        response.json.return_value = {"detail": "Access denied"}

        with pytest.raises(AccessDeniedError, match="Access denied"):
            client._handle_error(response)

    def test_400_raises_interface_version_error(self):
        """Verify 400 Bad Request maps to InterfaceVersionError."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        response = Mock(spec=httpx.Response)
        response.status_code = 400
        response.json.return_value = {"detail": "Version mismatch"}

        with pytest.raises(InterfaceVersionError, match="Version mismatch"):
            client._handle_error(response)

    def test_500_raises_apacheta_error(self):
        """Verify 500 Internal Server Error maps to ApachetaError."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        response = Mock(spec=httpx.Response)
        response.status_code = 500
        response.json.return_value = {"detail": "Internal error"}

        with pytest.raises(ApachetaError, match="Internal error"):
            client._handle_error(response)

    def test_502_raises_apacheta_error(self):
        """Verify 502 Bad Gateway maps to ApachetaError."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        response = Mock(spec=httpx.Response)
        response.status_code = 502
        response.json.return_value = {"detail": "Bad gateway"}

        with pytest.raises(ApachetaError, match="Bad gateway"):
            client._handle_error(response)

    def test_error_uses_default_message_if_detail_missing(self):
        """Verify fallback messages when detail field is missing."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        response = Mock(spec=httpx.Response)
        response.status_code = 404
        response.json.return_value = {}

        with pytest.raises(NotFoundError, match="Not found"):
            client._handle_error(response)

    def test_non_error_status_code_calls_raise_for_status(self):
        """Verify other status codes delegate to httpx's raise_for_status."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        response = Mock(spec=httpx.Response)
        response.status_code = 418  # I'm a teapot
        response.json.return_value = {"detail": "Teapot"}

        client._handle_error(response)
        response.raise_for_status.assert_called_once()


# ── Version and Access Control Tests ──────────────────────────────────


class TestVersionAndAccessControl:
    """Test version reporting and access control hook."""

    def test_get_interface_version_returns_v1(self):
        """Verify get_interface_version returns the local version."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        assert client.get_interface_version() == "v1"

    def test_check_access_always_returns_true(self):
        """Verify check_access delegates to Pukara by always returning True."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        assert client.check_access("caller", "operation") is True
        assert client.check_access("caller", "operation", uuid4()) is True


# ── Store Operations Tests ────────────────────────────────────────────


class TestStoreOperations:
    """Test all store_* methods (write operations)."""

    def test_store_tensor_posts_to_correct_endpoint(self, sample_tensor):
        """Verify store_tensor sends POST to /api/v1/tensors."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_tensor(sample_tensor)

            mock_post.assert_called_once_with(
                "/api/v1/tensors",
                json=sample_tensor.model_dump(mode="json"),
            )

    def test_store_tensor_handles_409_conflict(self, sample_tensor):
        """Verify store_tensor raises ImmutabilityError on 409."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 409
        mock_response.json.return_value = {"detail": "Duplicate tensor"}

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(ImmutabilityError, match="Duplicate tensor"):
                client.store_tensor(sample_tensor)

    def test_store_composition_edge_posts_to_correct_endpoint(self, sample_composition_edge):
        """Verify store_composition_edge sends POST to /api/v1/composition-edges."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_composition_edge(sample_composition_edge)

            mock_post.assert_called_once_with(
                "/api/v1/composition-edges",
                json=sample_composition_edge.model_dump(mode="json"),
            )

    def test_store_correction_posts_to_correct_endpoint(self, sample_correction):
        """Verify store_correction sends POST to /api/v1/corrections."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_correction(sample_correction)

            mock_post.assert_called_once_with(
                "/api/v1/corrections",
                json=sample_correction.model_dump(mode="json"),
            )

    def test_store_dissent_posts_to_correct_endpoint(self, sample_dissent):
        """Verify store_dissent sends POST to /api/v1/dissents."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_dissent(sample_dissent)

            mock_post.assert_called_once_with(
                "/api/v1/dissents",
                json=sample_dissent.model_dump(mode="json"),
            )

    def test_store_negation_posts_to_correct_endpoint(self, sample_negation):
        """Verify store_negation sends POST to /api/v1/negations."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_negation(sample_negation)

            mock_post.assert_called_once_with(
                "/api/v1/negations",
                json=sample_negation.model_dump(mode="json"),
            )

    def test_store_bootstrap_posts_to_correct_endpoint(self, sample_bootstrap):
        """Verify store_bootstrap sends POST to /api/v1/bootstraps."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_bootstrap(sample_bootstrap)

            mock_post.assert_called_once_with(
                "/api/v1/bootstraps",
                json=sample_bootstrap.model_dump(mode="json"),
            )

    def test_store_evolution_posts_to_correct_endpoint(self, sample_evolution):
        """Verify store_evolution sends POST to /api/v1/evolutions."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_evolution(sample_evolution)

            mock_post.assert_called_once_with(
                "/api/v1/evolutions",
                json=sample_evolution.model_dump(mode="json"),
            )

    def test_store_entity_posts_to_correct_endpoint(self, sample_entity):
        """Verify store_entity sends POST to /api/v1/entities."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_entity(sample_entity)

            mock_post.assert_called_once_with(
                "/api/v1/entities",
                json=sample_entity.model_dump(mode="json"),
            )


# ── Read Operations Tests ─────────────────────────────────────────────


class TestReadOperations:
    """Test all get_* and list_* methods (read operations)."""

    def test_get_tensor_sends_get_request(self, sample_tensor):
        """Verify get_tensor sends GET to /api/v1/tensors/{id}."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        tensor_id = sample_tensor.id
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_tensor.model_dump(mode="json")

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.get_tensor(tensor_id)

            mock_get.assert_called_once_with(f"/api/v1/tensors/{tensor_id}")
            assert result.id == sample_tensor.id
            assert result.preamble == sample_tensor.preamble

    def test_get_tensor_raises_not_found_on_404(self):
        """Verify get_tensor raises NotFoundError when tensor doesn't exist."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        tensor_id = uuid4()
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Tensor not found"}

        with patch.object(client._client, "get", return_value=mock_response):
            with pytest.raises(NotFoundError, match="Tensor not found"):
                client.get_tensor(tensor_id)

    def test_get_strand_sends_get_request(self, sample_tensor):
        """Verify get_strand sends GET to /api/v1/tensors/{id}/strands/{index}."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        tensor_id = sample_tensor.id
        strand_index = 0
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_tensor.model_dump(mode="json")

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.get_strand(tensor_id, strand_index)

            mock_get.assert_called_once_with(
                f"/api/v1/tensors/{tensor_id}/strands/{strand_index}"
            )
            assert result.id == sample_tensor.id

    def test_get_entity_sends_get_request(self, sample_entity):
        """Verify get_entity sends GET to /api/v1/entities/{id}."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        entity_id = sample_entity.id
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = sample_entity.model_dump(mode="json")

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.get_entity(entity_id)

            mock_get.assert_called_once_with(f"/api/v1/entities/{entity_id}")
            assert result.id == sample_entity.id
            assert result.entity_uuid == sample_entity.entity_uuid

    def test_list_tensors_sends_get_request(self, sample_tensor):
        """Verify list_tensors sends GET to /api/v1/tensors."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_tensor.model_dump(mode="json")]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.list_tensors()

            mock_get.assert_called_once_with("/api/v1/tensors")
            assert len(result) == 1
            assert result[0].id == sample_tensor.id

    def test_list_tensors_returns_empty_list(self):
        """Verify list_tensors returns empty list when no tensors exist."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch.object(client._client, "get", return_value=mock_response):
            result = client.list_tensors()
            assert result == []


# ── Query Operations Tests ────────────────────────────────────────────


class TestQueryOperations:
    """Test all query_* methods."""

    def test_query_tensors_for_budget_sends_get_with_params(self, sample_tensor):
        """Verify query_tensors_for_budget sends GET with budget param."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_tensor.model_dump(mode="json")]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_tensors_for_budget(8000.0)

            mock_get.assert_called_once_with(
                "/api/v1/queries/tensors-for-budget",
                params={"budget": 8000.0},
            )
            assert len(result) == 1
            assert result[0].id == sample_tensor.id

    def test_query_operational_principles_sends_get_request(self):
        """Verify query_operational_principles sends GET request."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = ["principle1", "principle2"]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_operational_principles()

            mock_get.assert_called_once_with("/api/v1/queries/operational-principles")
            assert result == ["principle1", "principle2"]

    def test_query_project_state_sends_get_request(self):
        """Verify query_project_state sends GET request."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"state": "active", "tensors": 5}

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_project_state()

            mock_get.assert_called_once_with("/api/v1/queries/project-state")
            assert result == {"state": "active", "tensors": 5}

    def test_query_claims_about_sends_get_with_topic_param(self):
        """Verify query_claims_about sends GET with topic param."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"claim": "test claim"}]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_claims_about("testing")

            mock_get.assert_called_once_with(
                "/api/v1/queries/claims-about",
                params={"topic": "testing"},
            )
            assert result == [{"claim": "test claim"}]

    def test_query_correction_chain_sends_get_request(self, sample_correction):
        """Verify query_correction_chain sends GET with claim_id."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        claim_id = uuid4()
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_correction.model_dump(mode="json")]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_correction_chain(claim_id)

            mock_get.assert_called_once_with(f"/api/v1/queries/correction-chain/{claim_id}")
            assert len(result) == 1
            assert result[0].id == sample_correction.id

    def test_query_epistemic_status_sends_get_request(self):
        """Verify query_epistemic_status sends GET with claim_id."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        claim_id = uuid4()
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "corrected"}

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_epistemic_status(claim_id)

            mock_get.assert_called_once_with(f"/api/v1/queries/epistemic-status/{claim_id}")
            assert result == {"status": "corrected"}

    def test_query_disagreements_sends_get_request(self):
        """Verify query_disagreements sends GET request."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"disagreement": "test"}]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_disagreements()

            mock_get.assert_called_once_with("/api/v1/queries/disagreements")
            assert result == [{"disagreement": "test"}]

    def test_query_composition_graph_sends_get_request(self, sample_composition_edge):
        """Verify query_composition_graph sends GET request."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_composition_edge.model_dump(mode="json")]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_composition_graph()

            mock_get.assert_called_once_with("/api/v1/queries/composition-graph")
            assert len(result) == 1
            assert result[0].id == sample_composition_edge.id

    def test_query_lineage_sends_get_request(self, sample_tensor):
        """Verify query_lineage sends GET with tensor_id."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        tensor_id = uuid4()
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_tensor.model_dump(mode="json")]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_lineage(tensor_id)

            mock_get.assert_called_once_with(f"/api/v1/queries/lineage/{tensor_id}")
            assert len(result) == 1
            assert result[0].id == sample_tensor.id

    def test_query_bridges_sends_get_request(self, sample_composition_edge):
        """Verify query_bridges sends GET request."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_composition_edge.model_dump(mode="json")]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_bridges()

            mock_get.assert_called_once_with("/api/v1/queries/bridges")
            assert len(result) == 1

    def test_query_error_classes_sends_get_request(self):
        """Verify query_error_classes sends GET request."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"error_class": "test"}]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_error_classes()

            mock_get.assert_called_once_with("/api/v1/queries/error-classes")
            assert result == [{"error_class": "test"}]

    def test_query_open_questions_sends_get_request(self):
        """Verify query_open_questions sends GET request."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = ["question1", "question2"]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_open_questions()

            mock_get.assert_called_once_with("/api/v1/queries/open-questions")
            assert result == ["question1", "question2"]

    def test_query_unreliable_signals_sends_get_request(self):
        """Verify query_unreliable_signals sends GET request."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"signal": "unreliable"}]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_unreliable_signals()

            mock_get.assert_called_once_with("/api/v1/queries/unreliable-signals")
            assert result == [{"signal": "unreliable"}]

    def test_query_anti_patterns_sends_get_request(self):
        """Verify query_anti_patterns sends GET request."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"pattern": "anti"}]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_anti_patterns()

            mock_get.assert_called_once_with("/api/v1/queries/anti-patterns")
            assert result == [{"pattern": "anti"}]

    def test_query_authorship_sends_get_request(self):
        """Verify query_authorship sends GET with tensor_id."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        tensor_id = uuid4()
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"author": "claude"}

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_authorship(tensor_id)

            mock_get.assert_called_once_with(f"/api/v1/queries/authorship/{tensor_id}")
            assert result == {"author": "claude"}

    def test_query_cross_model_sends_get_request(self, sample_tensor):
        """Verify query_cross_model sends GET request."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_tensor.model_dump(mode="json")]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_cross_model()

            mock_get.assert_called_once_with("/api/v1/queries/cross-model")
            assert len(result) == 1

    def test_query_reading_order_sends_get_with_tag_param(self, sample_tensor):
        """Verify query_reading_order sends GET with tag param."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_tensor.model_dump(mode="json")]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_reading_order("test-sequence")

            mock_get.assert_called_once_with(
                "/api/v1/queries/reading-order",
                params={"tag": "test-sequence"},
            )
            assert len(result) == 1

    def test_query_unlearn_sends_get_with_topic_param(self):
        """Verify query_unlearn sends GET with topic param."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"impact": "high"}

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_unlearn("testing")

            mock_get.assert_called_once_with(
                "/api/v1/queries/unlearn",
                params={"topic": "testing"},
            )
            assert result == {"impact": "high"}

    def test_query_losses_sends_get_request(self):
        """Verify query_losses sends GET with tensor_id."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        tensor_id = uuid4()
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"loss": "test"}]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_losses(tensor_id)

            mock_get.assert_called_once_with(f"/api/v1/queries/losses/{tensor_id}")
            assert result == [{"loss": "test"}]

    def test_query_loss_patterns_sends_get_request(self):
        """Verify query_loss_patterns sends GET request."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [{"pattern": "test"}]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_loss_patterns()

            mock_get.assert_called_once_with("/api/v1/queries/loss-patterns")
            assert result == [{"pattern": "test"}]

    def test_query_entities_by_uuid_sends_get_request(self, sample_entity):
        """Verify query_entities_by_uuid sends GET with entity_uuid."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        entity_uuid = uuid4()
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = [sample_entity.model_dump(mode="json")]

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.query_entities_by_uuid(entity_uuid)

            mock_get.assert_called_once_with(f"/api/v1/queries/entities-by-uuid/{entity_uuid}")
            assert len(result) == 1
            assert result[0].id == sample_entity.id


# ── Count Records Tests ───────────────────────────────────────────────


class TestCountRecords:
    """Test count_records method."""

    def test_count_records_sends_get_request(self):
        """Verify count_records sends GET to /api/v1/counts."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tensors": 5,
            "edges": 3,
            "corrections": 1,
        }

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            result = client.count_records()

            mock_get.assert_called_once_with("/api/v1/counts")
            assert result == {"tensors": 5, "edges": 3, "corrections": 1}


# ── Serialization and Deserialization Tests ───────────────────────────


class TestSerializationRoundtrip:
    """Test that serialization/deserialization preserves data correctly."""

    def test_tensor_serialization_uses_mode_json(self, sample_tensor):
        """Verify tensors are serialized with mode='json' for JSON compatibility."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_tensor(sample_tensor)

            # Extract the actual call args
            call_args = mock_post.call_args
            sent_json = call_args[1]["json"]

            # Verify JSON-compatible types (tuples become lists, etc.)
            assert isinstance(sent_json["lineage_tags"], list)
            assert isinstance(sent_json["strands"], list)

    def test_tensor_deserialization_preserves_types(self, sample_tensor):
        """Verify tensors are correctly deserialized back to TensorRecord."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        # Simulate JSON response from API (lists instead of tuples)
        json_data = sample_tensor.model_dump(mode="json")
        mock_response.json.return_value = json_data

        with patch.object(client._client, "get", return_value=mock_response):
            result = client.get_tensor(sample_tensor.id)

            # Verify deserialized back to proper types
            assert isinstance(result, TensorRecord)
            assert isinstance(result.lineage_tags, tuple)
            assert isinstance(result.strands, tuple)
            assert result.id == sample_tensor.id

    def test_uuid_serialization_and_deserialization(self, sample_tensor):
        """Verify UUIDs are serialized as strings and deserialized back to UUID objects."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        json_data = sample_tensor.model_dump(mode="json")
        # UUIDs should be strings in JSON
        assert isinstance(json_data["id"], str)
        mock_response.json.return_value = json_data

        with patch.object(client._client, "get", return_value=mock_response):
            result = client.get_tensor(sample_tensor.id)

            # Verify deserialized back to UUID
            assert isinstance(result.id, UUID)
            assert result.id == sample_tensor.id

    def test_datetime_serialization_preserves_iso_format(self, sample_tensor):
        """Verify datetimes are serialized to ISO format strings."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_tensor(sample_tensor)

            call_args = mock_post.call_args
            sent_json = call_args[1]["json"]

            # Verify timestamp is ISO format string
            assert isinstance(sent_json["provenance"]["timestamp"], str)
            assert "2026-02-10" in sent_json["provenance"]["timestamp"]


# ── Edge Cases and Special Values Tests ───────────────────────────────


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_list_response_deserialization(self):
        """Verify empty lists are handled correctly."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch.object(client._client, "get", return_value=mock_response):
            result = client.query_operational_principles()
            assert result == []

    def test_empty_dict_response_deserialization(self):
        """Verify empty dicts are handled correctly."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch.object(client._client, "get", return_value=mock_response):
            result = client.query_project_state()
            assert result == {}

    def test_unicode_in_tensor_content(self):
        """Verify Unicode characters are preserved through serialization."""
        tensor = TensorRecord(
            preamble="Unicode test: ñ é ü ç 日本語 🎉",
            strands=(
                StrandRecord(
                    strand_index=0,
                    title="Unicode Strand",
                    content="More Unicode: Λφαβητ",
                    topics=("unicode",),
                ),
            ),
        )

        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_tensor(tensor)

            call_args = mock_post.call_args
            sent_json = call_args[1]["json"]

            # Verify Unicode is preserved
            assert "ñ é ü ç" in sent_json["preamble"]
            assert "日本語 🎉" in sent_json["preamble"]

    def test_empty_string_fields(self):
        """Verify empty strings are handled correctly."""
        tensor = TensorRecord(
            preamble="",
            closing="",
            instructions_for_next="",
            narrative_body="",
        )

        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_tensor(tensor)

            call_args = mock_post.call_args
            sent_json = call_args[1]["json"]

            assert sent_json["preamble"] == ""
            assert sent_json["closing"] == ""

    def test_none_optional_fields(self):
        """Verify None values in optional fields are handled correctly."""
        tensor = TensorRecord(
            composition_equation=None,
        )

        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_tensor(tensor)

            call_args = mock_post.call_args
            sent_json = call_args[1]["json"]

            assert sent_json["composition_equation"] is None

    def test_large_tensor_with_many_strands(self):
        """Verify large tensors with many strands serialize correctly."""
        strands = tuple(
            StrandRecord(
                strand_index=i,
                title=f"Strand {i}",
                content=f"Content {i}" * 100,  # Large content
                topics=(f"topic{i}",),
            )
            for i in range(50)
        )

        tensor = TensorRecord(
            preamble="Large tensor test",
            strands=strands,
        )

        client = ApachetaGatewayClient(base_url="http://localhost:8000")
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 201

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            client.store_tensor(tensor)

            call_args = mock_post.call_args
            sent_json = call_args[1]["json"]

            assert len(sent_json["strands"]) == 50


# ── Integration-style Tests ───────────────────────────────────────────


class TestClientBehavior:
    """Test client behavior in realistic usage patterns."""

    def test_api_key_header_is_sent_when_configured(self, sample_tensor):
        """Verify API key header is included in all requests when set."""
        client = ApachetaGatewayClient(
            base_url="http://localhost:8000",
            api_key="secret-key-123",
        )

        # Check that the httpx.Client was created with the header
        assert client._client.headers.get("X-API-Key") == "secret-key-123"

    def test_api_key_header_absent_when_not_configured(self, sample_tensor):
        """Verify API key header is not sent when not configured."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")

        # Check that the httpx.Client has no API key header
        assert "X-API-Key" not in client._client.headers

    def test_multiple_operations_in_sequence(self, sample_tensor, sample_composition_edge):
        """Verify multiple operations can be performed in sequence."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")

        # Mock responses
        store_response = Mock(spec=httpx.Response)
        store_response.status_code = 201

        get_response = Mock(spec=httpx.Response)
        get_response.status_code = 200
        get_response.json.return_value = sample_tensor.model_dump(mode="json")

        with patch.object(client._client, "post", return_value=store_response):
            with patch.object(client._client, "get", return_value=get_response):
                # Store a tensor
                client.store_tensor(sample_tensor)

                # Store an edge
                client.store_composition_edge(sample_composition_edge)

                # Retrieve the tensor
                result = client.get_tensor(sample_tensor.id)

                assert result.id == sample_tensor.id

    def test_error_on_store_prevents_get(self, sample_tensor):
        """Verify error during store operation raises exception."""
        client = ApachetaGatewayClient(base_url="http://localhost:8000")

        error_response = Mock(spec=httpx.Response)
        error_response.status_code = 409
        error_response.json.return_value = {"detail": "Duplicate"}

        with patch.object(client._client, "post", return_value=error_response):
            with pytest.raises(ImmutabilityError):
                client.store_tensor(sample_tensor)
