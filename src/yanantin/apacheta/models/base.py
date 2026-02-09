"""Base model for all Apacheta records."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ApachetaBaseModel(BaseModel):
    """Base for all Apacheta data models.

    Follows Pydantic v2 conventions. All models serialize to/from JSON
    via model_dump/model_validate. Immutable once created.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        ser_json_bytes="base64",
        validate_default=True,
    )
