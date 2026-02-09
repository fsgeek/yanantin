"""Epistemic metadata — T/I/F, declared losses, disagreement types."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from yanantin.apacheta.models.base import ApachetaBaseModel


class RepresentationType(str, Enum):
    """How epistemic values are represented."""

    SCALAR = "scalar"
    FUNCTIONAL = "functional"


class LossCategory(str, Enum):
    """Why something was lost."""

    CONTEXT_PRESSURE = "context_pressure"
    TRAVERSAL_BIAS = "traversal_bias"
    AUTHORIAL_CHOICE = "authorial_choice"
    PRACTICAL_CONSTRAINT = "practical_constraint"


class DisagreementType(str, Enum):
    """Whether a disagreement is about facts or frameworks.

    From the Archivist's observation: empirical disagreements can be
    resolved by evidence; definitional disagreements cannot.
    """

    EMPIRICAL = "empirical"
    DEFINITIONAL = "definitional"


class DeclaredLoss(ApachetaBaseModel):
    """What was dropped and why. The losses are mine."""

    what_was_lost: str
    why: str
    category: LossCategory


class EpistemicMetadata(ApachetaBaseModel):
    """Epistemic state of a claim, strand, or tensor.

    T/I/F are independent floats, conventionally in [0, 1] but unconstrained
    at the model level. NOT constrained to sum to 1.0. This is neutrosophic
    logic: something can be simultaneously partly true, partly indeterminate,
    and partly false. Values outside [0, 1] may represent uncalibrated raw
    scores awaiting normalization.
    """

    representation_type: RepresentationType = RepresentationType.SCALAR
    truth: float = 0.0
    indeterminacy: float = 0.0
    falsity: float = 0.0
    functional_spec: dict | None = None
    scope_boundaries: tuple[str, ...] = Field(default_factory=tuple)
    disagreement_type: DisagreementType | None = None
