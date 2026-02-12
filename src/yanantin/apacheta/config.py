"""Config-as-tensors — immutable configuration stored in Apacheta.

Configuration is never updated. A new config tensor is stored with
reasoning for the change, and a pointer to the config it replaces.
The correction chain shows how settings evolved over time.

Bootstrap problem: you need file-based defaults to reach the database,
and database configs override the file defaults. get_current_config
returns None when no database is available, signaling the caller to
use DEFAULT_CONFIGS.

    config = get_current_config(interface, "chasqui.pulse")
    settings = config.settings if config else DEFAULT_CONFIGS["chasqui.pulse"]
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.models.base import ApachetaBaseModel
from yanantin.apacheta.models.provenance import ProvenanceEnvelope
from yanantin.apacheta.models.tensor import KeyClaim, StrandRecord, TensorRecord

logger = logging.getLogger(__name__)

# ── Default Configurations ────────────────────────────────────────

DEFAULT_CONFIGS: dict[str, dict[str, Any]] = {
    "chasqui.pulse": {
        "min_scout_interval": 300,
        "heartbeat_interval": 21600,
        "verify_count": 3,
        "scout_max_tokens": 4000,
        "scout_temperature": 0.7,
        "verify_temperature": 0.3,
    },
}


# ── ConfigTensor Model ────────────────────────────────────────────


class ConfigTensor(ApachetaBaseModel):
    """Configuration stored as a tensor-compatible structure.

    Immutable by inheritance from ApachetaBaseModel. Each config
    records what changed, why, and what it replaced.
    """

    config_domain: str
    settings: dict[str, Any]
    reasoning: str
    previous_config_id: UUID | None = None
    provenance: ProvenanceEnvelope = Field(default_factory=ProvenanceEnvelope)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ── Storage Functions ─────────────────────────────────────────────


def _config_to_tensor(config: ConfigTensor) -> TensorRecord:
    """Convert a ConfigTensor into a TensorRecord for storage.

    Each setting becomes a KeyClaim. The reasoning becomes the
    narrative_body. Lineage tags mark this as config for the domain.
    """
    claims = tuple(
        KeyClaim(
            text=f"{key} = {value!r}",
        )
        for key, value in sorted(config.settings.items())
    )

    strand = StrandRecord(
        strand_index=0,
        title=f"Configuration: {config.config_domain}",
        content=config.reasoning,
        topics=(config.config_domain, "config"),
        key_claims=claims,
    )

    predecessors: tuple[UUID, ...] = ()
    if config.previous_config_id is not None:
        predecessors = (config.previous_config_id,)

    provenance = ProvenanceEnvelope(
        source=config.provenance.source,
        timestamp=config.timestamp,
        author_model_family=config.provenance.author_model_family,
        author_instance_id=config.provenance.author_instance_id,
        context_budget_at_write=config.provenance.context_budget_at_write,
        predecessors_in_scope=predecessors,
        interface_version=config.provenance.interface_version,
    )

    return TensorRecord(
        provenance=provenance,
        preamble=f"Config tensor for domain: {config.config_domain}",
        strands=(strand,),
        narrative_body=config.reasoning,
        lineage_tags=("config", config.config_domain),
    )


def _tensor_to_config(tensor: TensorRecord) -> ConfigTensor | None:
    """Reconstruct a ConfigTensor from a stored TensorRecord.

    Returns None if the tensor does not look like a config tensor
    (missing the "config" lineage tag or has no strands with claims).
    """
    if "config" not in tensor.lineage_tags:
        return None

    # Find the domain from lineage_tags (the tag that isn't "config")
    domain = None
    for tag in tensor.lineage_tags:
        if tag != "config":
            domain = tag
            break

    if domain is None:
        return None

    # Reconstruct settings from key claims
    settings: dict[str, Any] = {}
    for strand in tensor.strands:
        for claim in strand.key_claims:
            # Parse "key = value_repr" format
            if " = " in claim.text:
                key, value_repr = claim.text.split(" = ", 1)
                try:
                    # ast.literal_eval safely parses Python literals
                    import ast

                    settings[key] = ast.literal_eval(value_repr)
                except (ValueError, SyntaxError):
                    # If we can't parse it, store as string
                    settings[key] = value_repr

    # Find previous config id from predecessors_in_scope
    previous_config_id = None
    if tensor.provenance.predecessors_in_scope:
        previous_config_id = tensor.provenance.predecessors_in_scope[0]

    return ConfigTensor(
        config_domain=domain,
        settings=settings,
        reasoning=tensor.narrative_body,
        previous_config_id=previous_config_id,
        provenance=tensor.provenance,
        timestamp=tensor.provenance.timestamp,
    )


def store_config(
    interface: ApachetaInterface, config: ConfigTensor
) -> UUID:
    """Store a config as a TensorRecord. Returns the tensor UUID.

    The config is converted to a TensorRecord with lineage_tags
    ["config", config_domain]. Each setting becomes a KeyClaim.
    The reasoning becomes the narrative_body.
    """
    tensor = _config_to_tensor(config)
    interface.store_tensor(tensor)
    logger.info(
        "Stored config tensor %s for domain %s",
        tensor.id,
        config.config_domain,
    )
    return tensor.id


def get_current_config(
    interface: ApachetaInterface, domain: str
) -> ConfigTensor | None:
    """Get the most recent config for a domain.

    Returns None if no config tensor exists for this domain.
    The caller should fall back to DEFAULT_CONFIGS when None.

    Uses query_reading_order which returns tensors sorted by
    timestamp (oldest first), so we take the last one.
    """
    try:
        tensors = interface.query_reading_order(domain)
    except Exception:
        logger.debug(
            "Failed to query configs for domain %s", domain, exc_info=True
        )
        return None

    # Filter to only config tensors (query_reading_order matches any
    # tensor with this lineage_tag, not just config tensors)
    config_tensors = [t for t in tensors if "config" in t.lineage_tags]

    if not config_tensors:
        return None

    # query_reading_order returns oldest-first; we want the newest
    latest = config_tensors[-1]
    return _tensor_to_config(latest)


def get_config_history(
    interface: ApachetaInterface, domain: str
) -> list[ConfigTensor]:
    """Get all config tensors for a domain, newest first.

    Returns empty list if no configs exist or the database is
    unreachable.
    """
    try:
        tensors = interface.query_reading_order(domain)
    except Exception:
        logger.debug(
            "Failed to query config history for domain %s",
            domain,
            exc_info=True,
        )
        return []

    config_tensors = [t for t in tensors if "config" in t.lineage_tags]

    configs: list[ConfigTensor] = []
    for tensor in config_tensors:
        config = _tensor_to_config(tensor)
        if config is not None:
            configs.append(config)

    # Newest first
    configs.reverse()
    return configs
