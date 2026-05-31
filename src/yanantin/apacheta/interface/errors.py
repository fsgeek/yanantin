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


# ── Backend connection failure discrimination ─────────────────────────
#
# These inherit from the builtin ConnectionError, not ApachetaError, so
# that existing `except ConnectionError` catch sites keep working while
# new code can branch on the specific cause. The whole point is that a
# rejected credential, an unreachable host, and a genuinely-missing
# database are three different problems with three different remediations
# — and the old blanket wrapper claimed all three were "must be
# provisioned by an admin", priming the wrong fix.


class BackendAuthError(ConnectionError):
    """Credentials were rejected by the database (HTTP 401/403).

    Remediation is about credentials/privilege, NOT provisioning.
    """


class BackendUnreachableError(ConnectionError):
    """Could not establish a network connection to the database host.

    Remediation is about host/port/network reachability, NOT provisioning.
    """


class DatabaseNotProvisionedError(ConnectionError):
    """The named database does not exist on a reachable, authenticated host.

    This is the one case the old blanket message was actually right about:
    an admin must provision the database.
    """
