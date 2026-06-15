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
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.composition import (
    BootstrapRecord,
    CompositionEdge,
    CorrectionRecord,
    DissentRecord,
    NegationRecord,
    SchemaEvolutionRecord,
)
from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.composition import RelationType
from yanantin.apacheta.models.entities import EntityResolution
from yanantin.apacheta.models.tensor import TensorRecord
from yanantin.llika.models import EdgeResult, PathResult, PathStep


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

    # ── Generic Operations ────────────────────────────────────────

    def store_record(self, record_id: UUID, record: ApachetaBaseModel) -> None:
        data = record.model_dump(mode="json")
        data["id"] = str(record_id)
        response = self._client.post("/api/v1/records", json=data)
        if response.status_code != 201:
            self._handle_error(response)

    def get_record(self, record_id: UUID) -> ApachetaBaseModel:
        response = self._client.get(f"/api/v1/records/{record_id}")
        if response.status_code != 200:
            self._handle_error(response)
        return ApachetaBaseModel.model_validate(response.json())

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

    def store_provenance_edge(self, edge) -> None:
        # Pukara has no provenance-edge route yet. When it grows one, this
        # gains a proper HTTP-call implementation in a coordinated PR
        # (mirrors the open-record stubs below).
        raise NotImplementedError(
            "Provenance edges not yet available via Pukara gateway (route pending)."
        )

    def list_provenance_edges(self) -> list:
        raise NotImplementedError(
            "Provenance edges not yet available via Pukara gateway (route pending)."
        )

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

    # ── Llika graph verbs (behind Pukara) ────────────────────────
    # Mirror pukara/routes/llika.py exactly. id-shape is mixed per-verb
    # (yanantin#10 SEAM 1): link/walk/neighbors take "collection/<uuid>"
    # slash-form refs; get takes a bare UUID (records-only). The frozen
    # result dataclasses (EdgeResult/PathResult/PathStep) are reconstructed
    # from the route JSON so callers get the same types as the in-process
    # GraphBackend.

    @staticmethod
    def _path_result_from_json(data: dict) -> PathResult:
        return PathResult(
            start_id=data["start_id"],
            steps=tuple(
                PathStep(
                    record_id=s["record_id"],
                    relation_type=s["relation_type"],
                    field_names=tuple(s["field_names"]),
                )
                for s in data["steps"]
            ),
        )

    def link(
        self,
        from_ref: str,
        to_ref: str,
        relation_type: RelationType,
        provenance: ProvenanceEnvelope,
        **fields: Any,
    ) -> EdgeResult:
        body = {
            "from_ref": from_ref,
            "to_ref": to_ref,
            "relation_type": relation_type.value,
            "provenance": provenance.model_dump(mode="json"),
            **fields,
        }
        response = self._client.post("/api/v1/llika/link", json=body)
        if response.status_code != 201:
            self._handle_error(response)
        data = response.json()
        return EdgeResult(
            edge_id=data["edge_id"],
            from_id=data["from_id"],
            to_id=data["to_id"],
            relation_type=data["relation_type"],
            created_at=data["created_at"],
        )

    def walk(
        self,
        start_id: str,
        direction: str,
        depth: int,
        relation_types: list[str] | None = None,
        max_results: int = 50,
    ) -> list[PathResult]:
        body = {
            "start_id": start_id,
            "direction": direction,
            "depth": depth,
            "relation_types": relation_types,
            "max_results": max_results,
        }
        response = self._client.post("/api/v1/llika/walk", json=body)
        if response.status_code != 200:
            self._handle_error(response)
        return [self._path_result_from_json(r) for r in response.json()]

    def neighbors(
        self,
        start_id: str,
        direction: str,
        relation_types: list[str] | None = None,
    ) -> list[PathResult]:
        body = {
            "start_id": start_id,
            "direction": direction,
            "relation_types": relation_types,
        }
        response = self._client.post("/api/v1/llika/neighbors", json=body)
        if response.status_code != 200:
            self._handle_error(response)
        return [self._path_result_from_json(r) for r in response.json()]

    def get(self, record_id: UUID) -> ApachetaBaseModel:
        """Read a single record by UUID through the llika get route.

        Distinct from get_record (which hits /api/v1/records/{id}); the llika
        surface exposes its own get endpoint riding the same backend method.
        """
        response = self._client.get(f"/api/v1/llika/get/{record_id}")
        if response.status_code != 200:
            self._handle_error(response)
        return ApachetaBaseModel.model_validate(response.json())

    # ── Open-Record Queries (deferred) ───────────────────────────
    # Pukara has no routes for these yet. When it grows them, this file
    # gains a proper HTTP-call implementation in a coordinated PR.

    _OPEN_NOT_IMPLEMENTED = (
        "Open-record queries not yet available via Pukara gateway (routes pending)."
    )

    def list_open_records(
        self,
        limit: int | None = None,
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        raise NotImplementedError(self._OPEN_NOT_IMPLEMENTED)

    def query_open_by_author_instance(
        self,
        author_instance_id: str,
        limit: int | None = None,
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        raise NotImplementedError(self._OPEN_NOT_IMPLEMENTED)

    def query_open_by_lineage_tag(
        self,
        tag: str,
        limit: int | None = None,
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        raise NotImplementedError(self._OPEN_NOT_IMPLEMENTED)

    def query_open_has_field(
        self,
        field: str,
        limit: int | None = None,
    ) -> list[tuple[UUID, ApachetaBaseModel]]:
        raise NotImplementedError(self._OPEN_NOT_IMPLEMENTED)

    def list_author_instances(self) -> list[str]:
        raise NotImplementedError(self._OPEN_NOT_IMPLEMENTED)

    # ── Record Counts ────────────────────────────────────────────

    def count_records(self) -> dict[str, int]:
        response = self._client.get("/api/v1/counts")
        if response.status_code != 200:
            self._handle_error(response)
        return response.json()
