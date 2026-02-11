"""HTTP client for Pukara gateway — implements ApachetaInterface over HTTP.

Thin client that maps interface methods to Pukara's FastAPI endpoints.
Uses httpx for HTTP calls. Synchronous to match the interface contract.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from yanantin.apacheta.interface.abstract import ApachetaInterface, INTERFACE_VERSION
from yanantin.apacheta.interface.errors import (
    AccessDeniedError,
    ApachetaError,
    ImmutabilityError,
    InterfaceVersionError,
    NotFoundError,
)
from yanantin.apacheta.models.composition import (
    BootstrapRecord,
    CompositionEdge,
    CorrectionRecord,
    DissentRecord,
    NegationRecord,
    SchemaEvolutionRecord,
)
from yanantin.apacheta.models.entities import EntityResolution
from yanantin.apacheta.models.tensor import TensorRecord


class ApachetaGatewayClient(ApachetaInterface):
    """HTTP client that implements ApachetaInterface via Pukara gateway.

    Maps each interface method to the corresponding Pukara HTTP endpoint.
    Converts between Pydantic models and JSON for HTTP transport.
    Raises appropriate ApachetaError subclasses on HTTP errors.

    Args:
        base_url: Base URL of the Pukara gateway (e.g., "http://localhost:8000")
        api_key: Optional API key for authentication (passed as X-API-Key header)
        timeout: Request timeout in seconds (default: 30.0)
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._headers = {"X-API-Key": api_key} if api_key else {}
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=self._headers,
            timeout=timeout,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> ApachetaGatewayClient:
        """Support context manager protocol."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Close client on context exit."""
        self.close()

    def _handle_error(self, response: httpx.Response) -> None:
        """Convert HTTP errors to ApachetaError subclasses."""
        if response.status_code == 409:
            raise ImmutabilityError(response.json().get("detail", "Conflict"))
        elif response.status_code == 404:
            raise NotFoundError(response.json().get("detail", "Not found"))
        elif response.status_code == 403:
            raise AccessDeniedError(response.json().get("detail", "Access denied"))
        elif response.status_code == 400:
            raise InterfaceVersionError(response.json().get("detail", "Bad request"))
        elif response.status_code >= 500:
            raise ApachetaError(response.json().get("detail", "Server error"))
        else:
            response.raise_for_status()

    # ── Version ──────────────────────────────────────────────────

    def get_interface_version(self) -> str:
        """Returns the local interface version (not the remote one).

        The interface version is a property of the client implementation,
        not something fetched from the server. To get the server's version,
        use GET /api/v1/version directly.
        """
        return INTERFACE_VERSION

    # ── Access Control Hook ──────────────────────────────────────

    def check_access(self, caller: str, operation: str, target: UUID | None = None) -> bool:
        """Always returns True — access control is handled by Pukara."""
        return True

    # ── Write Operations ─────────────────────────────────────────

    def store_tensor(self, tensor: TensorRecord) -> None:
        response = self._client.post(
            "/api/v1/tensors",
            json=tensor.model_dump(mode="json"),
        )
        if response.status_code != 201:
            self._handle_error(response)

    def store_composition_edge(self, edge: CompositionEdge) -> None:
        response = self._client.post(
            "/api/v1/composition-edges",
            json=edge.model_dump(mode="json"),
        )
        if response.status_code != 201:
            self._handle_error(response)

    def store_correction(self, correction: CorrectionRecord) -> None:
        response = self._client.post(
            "/api/v1/corrections",
            json=correction.model_dump(mode="json"),
        )
        if response.status_code != 201:
            self._handle_error(response)

    def store_dissent(self, dissent: DissentRecord) -> None:
        response = self._client.post(
            "/api/v1/dissents",
            json=dissent.model_dump(mode="json"),
        )
        if response.status_code != 201:
            self._handle_error(response)

    def store_negation(self, negation: NegationRecord) -> None:
        response = self._client.post(
            "/api/v1/negations",
            json=negation.model_dump(mode="json"),
        )
        if response.status_code != 201:
            self._handle_error(response)

    def store_bootstrap(self, bootstrap: BootstrapRecord) -> None:
        response = self._client.post(
            "/api/v1/bootstraps",
            json=bootstrap.model_dump(mode="json"),
        )
        if response.status_code != 201:
            self._handle_error(response)

    def store_evolution(self, evolution: SchemaEvolutionRecord) -> None:
        response = self._client.post(
            "/api/v1/evolutions",
            json=evolution.model_dump(mode="json"),
        )
        if response.status_code != 201:
            self._handle_error(response)

    def store_entity(self, entity: EntityResolution) -> None:
        response = self._client.post(
            "/api/v1/entities",
            json=entity.model_dump(mode="json"),
        )
        if response.status_code != 201:
            self._handle_error(response)

    # ── Read Operations ──────────────────────────────────────────

    def get_tensor(self, tensor_id: UUID) -> TensorRecord:
        response = self._client.get(f"/api/v1/tensors/{tensor_id}")
        if response.status_code != 200:
            self._handle_error(response)
        return TensorRecord.model_validate(response.json())

    def get_strand(self, tensor_id: UUID, strand_index: int) -> TensorRecord:
        response = self._client.get(
            f"/api/v1/tensors/{tensor_id}/strands/{strand_index}"
        )
        if response.status_code != 200:
            self._handle_error(response)
        return TensorRecord.model_validate(response.json())

    def get_entity(self, entity_id: UUID) -> EntityResolution:
        response = self._client.get(f"/api/v1/entities/{entity_id}")
        if response.status_code != 200:
            self._handle_error(response)
        return EntityResolution.model_validate(response.json())

    def list_tensors(self) -> list[TensorRecord]:
        response = self._client.get("/api/v1/tensors")
        if response.status_code != 200:
            self._handle_error(response)
        return [TensorRecord.model_validate(t) for t in response.json()]

    # ── Query Operations ─────────────────────────────────────────

    def query_tensors_for_budget(self, budget: float) -> list[TensorRecord]:
        response = self._client.get(
            "/api/v1/queries/tensors-for-budget",
            params={"budget": budget},
        )
        if response.status_code != 200:
            self._handle_error(response)
        return [TensorRecord.model_validate(t) for t in response.json()]

    def query_operational_principles(self) -> list[str]:
        response = self._client.get("/api/v1/queries/operational-principles")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_project_state(self) -> dict:
        response = self._client.get("/api/v1/queries/project-state")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_claims_about(self, topic: str) -> list[dict]:
        response = self._client.get(
            "/api/v1/queries/claims-about",
            params={"topic": topic},
        )
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_correction_chain(self, claim_id: UUID) -> list[CorrectionRecord]:
        response = self._client.get(f"/api/v1/queries/correction-chain/{claim_id}")
        if response.status_code != 200:
            self._handle_error(response)
        return [CorrectionRecord.model_validate(c) for c in response.json()]

    def query_epistemic_status(self, claim_id: UUID) -> dict:
        response = self._client.get(f"/api/v1/queries/epistemic-status/{claim_id}")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_disagreements(self) -> list[dict]:
        response = self._client.get("/api/v1/queries/disagreements")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_composition_graph(self) -> list[CompositionEdge]:
        response = self._client.get("/api/v1/queries/composition-graph")
        if response.status_code != 200:
            self._handle_error(response)
        return [CompositionEdge.model_validate(e) for e in response.json()]

    def query_lineage(self, tensor_id: UUID) -> list[TensorRecord]:
        response = self._client.get(f"/api/v1/queries/lineage/{tensor_id}")
        if response.status_code != 200:
            self._handle_error(response)
        return [TensorRecord.model_validate(t) for t in response.json()]

    def query_bridges(self) -> list[CompositionEdge]:
        response = self._client.get("/api/v1/queries/bridges")
        if response.status_code != 200:
            self._handle_error(response)
        return [CompositionEdge.model_validate(e) for e in response.json()]

    def query_error_classes(self) -> list[dict]:
        response = self._client.get("/api/v1/queries/error-classes")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_open_questions(self) -> list[str]:
        response = self._client.get("/api/v1/queries/open-questions")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_unreliable_signals(self) -> list[dict]:
        response = self._client.get("/api/v1/queries/unreliable-signals")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_anti_patterns(self) -> list[dict]:
        response = self._client.get("/api/v1/queries/anti-patterns")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_authorship(self, tensor_id: UUID) -> dict:
        response = self._client.get(f"/api/v1/queries/authorship/{tensor_id}")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_cross_model(self) -> list[TensorRecord]:
        response = self._client.get("/api/v1/queries/cross-model")
        if response.status_code != 200:
            self._handle_error(response)
        return [TensorRecord.model_validate(t) for t in response.json()]

    def query_reading_order(self, lineage_tag: str) -> list[TensorRecord]:
        response = self._client.get(
            "/api/v1/queries/reading-order",
            params={"tag": lineage_tag},
        )
        if response.status_code != 200:
            self._handle_error(response)
        return [TensorRecord.model_validate(t) for t in response.json()]

    def query_unlearn(self, topic: str) -> dict:
        response = self._client.get(
            "/api/v1/queries/unlearn",
            params={"topic": topic},
        )
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_losses(self, tensor_id: UUID) -> list[dict]:
        response = self._client.get(f"/api/v1/queries/losses/{tensor_id}")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_loss_patterns(self) -> list[dict]:
        response = self._client.get("/api/v1/queries/loss-patterns")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()

    def query_entities_by_uuid(self, entity_uuid: UUID) -> list[EntityResolution]:
        response = self._client.get(f"/api/v1/queries/entities-by-uuid/{entity_uuid}")
        if response.status_code != 200:
            self._handle_error(response)
        return [EntityResolution.model_validate(e) for e in response.json()]

    # ── Record Counts ────────────────────────────────────────────

    def count_records(self) -> dict[str, int]:
        response = self._client.get("/api/v1/counts")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()
