"""Llika wall probe: the gateway must be the only working graph door.

This is a behavioral falsification probe, not a source-token tripwire. It tries
the relocated bypass directly from an agent-reachable in-process context:
construct ``LlikaService(ArangoDBBackend(...), provenance)`` with the ordinary
apacheta_test credentials, then write and traverse a Llika edge without Pukara.

If that write/traverse succeeds, the boundary claim is false and this test must
go red. A correctly red result here is the honest signal until the credential
boundary exists: Pukara holds the graph backend credentials and the agent
process does not. yanantin#10, yanantin#13.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
from arango.exceptions import ArangoServerError
from tiksi.provenance import SourceIdentifier

from yanantin.apacheta.backends.arango import ArangoDBBackend
from yanantin.apacheta.interface.errors import (
    BackendAuthError,
    BackendUnreachableError,
    DatabaseNotProvisionedError,
)
from yanantin.apacheta.models import ProvenanceEnvelope
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.composition import RelationType
from yanantin.infra.config import ApachetaDBConfig
from yanantin.llika import LlikaService


pytestmark = pytest.mark.integration


def _is_unreachable(exc: BaseException) -> bool:
    return isinstance(
        exc,
        (BackendUnreachableError, DatabaseNotProvisionedError),
    ) or "Can't connect to host" in str(exc)


def _ordinary_agent_backend() -> ArangoDBBackend | None:
    if os.environ.get("APACHETA_SKIP_ARANGO"):
        pytest.skip("APACHETA_SKIP_ARANGO is set")

    cfg = ApachetaDBConfig()
    creds = cfg.get_test_credentials()
    try:
        return ArangoDBBackend(
            host=cfg.host_url,
            db_name="apacheta_test",
            username=creds["username"],
            password=creds["password"],
        )
    except BackendAuthError:
        return None
    except ConnectionError as exc:
        if _is_unreachable(exc):
            pytest.skip(
                "Live ArangoDB apacheta_test is unreachable from this environment: "
                f"{exc}"
            )
        raise


def _auth_blocked(exc: BaseException) -> bool:
    return isinstance(exc, BackendAuthError) or (
        isinstance(exc, ArangoServerError) and exc.http_code in (401, 403)
    )


def test_agent_side_process_cannot_obtain_working_llika_graph_handle() -> None:
    """[RED UNTIL CREDS WALL] Agent-side construction of the privileged graph
    backend must not produce a working Llika handle.

    The test passes only when construction or use is blocked by the credential
    boundary. It fails if the in-process agent path can store records, link
    them, and traverse the edge without Pukara.
    """
    backend = _ordinary_agent_backend()
    if backend is None:
        return

    left_id = uuid4()
    right_id = uuid4()
    start_ref = f"records/{left_id}"
    target_ref = f"records/{right_id}"
    tag = f"llika_wall_{uuid4().hex}"
    bypass_result: str | None = None

    try:
        provenance = ProvenanceEnvelope(
            source=SourceIdentifier(
                identifier=uuid4(),
                description="agent-side Llika wall falsification probe",
            ),
            author_model_family="wall-test",
        )
        service = LlikaService(backend, provenance)
        backend.store_record(
            left_id,
            ApachetaBaseModel(provenance=provenance, lineage_tags=(tag,)),
        )
        backend.store_record(
            right_id,
            ApachetaBaseModel(provenance=provenance, lineage_tags=(tag,)),
        )

        edge = service.link(
            start_ref,
            target_ref,
            RelationType.COMPOSES_WITH,
            test_tag=tag,
        )
        paths = service.walk(start_ref, "forward", depth=1)
        reached = any(
            path.steps and path.steps[-1].record_id == target_ref
            for path in paths
        )
        bypass_result = (
            f"edge_id={edge.edge_id!r}, "
            f"write_succeeded=True, traverse_reached={reached}"
        )
    except Exception as exc:
        if _auth_blocked(exc):
            return
        raise
    finally:
        db = backend._db
        if db.has_collection("llika_composition"):
            db.aql.execute(
                """
                FOR e IN llika_composition
                    FILTER e.test_tag == @tag
                    REMOVE e IN llika_composition
                """,
                bind_vars={"tag": tag},
            )
        if db.has_collection("records"):
            records = db.collection("records")
            records.delete(str(left_id), ignore_missing=True)
            records.delete(str(right_id), ignore_missing=True)
        backend.close()

    assert bypass_result is None, (
        "Relocated Llika privileged-handle bypass is reachable from the "
        "agent-side process without Pukara: "
        f"{bypass_result}. The wall must rest on credentials the agent "
        "process does not possess, not on LlikaService source shape."
    )
