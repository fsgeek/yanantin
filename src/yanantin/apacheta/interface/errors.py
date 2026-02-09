"""Custom exceptions for the Apacheta interface."""


class ApachetaError(Exception):
    """Base exception for all Apacheta errors."""


class ImmutabilityError(ApachetaError):
    """Raised when attempting to overwrite an existing record."""


class AccessDeniedError(ApachetaError):
    """Raised when an operation is denied by access control."""


class NotFoundError(ApachetaError):
    """Raised when a requested record does not exist."""


class InterfaceVersionError(ApachetaError):
    """Raised on interface version mismatch."""
