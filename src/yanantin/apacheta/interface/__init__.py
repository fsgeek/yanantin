"""Apacheta abstract interface — the only API to the tensor database."""

from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.interface.errors import (
    AccessDeniedError,
    ApachetaError,
    ImmutabilityError,
    InterfaceVersionError,
    NotFoundError,
)

__all__ = [
    "AccessDeniedError",
    "ApachetaError",
    "ApachetaInterface",
    "ImmutabilityError",
    "InterfaceVersionError",
    "NotFoundError",
]
