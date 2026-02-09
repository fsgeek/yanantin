"""Unit tests for the Apacheta abstract interface."""

import pytest

from yanantin.apacheta.interface import (
    AccessDeniedError,
    ApachetaError,
    ApachetaInterface,
    ImmutabilityError,
    InterfaceVersionError,
    NotFoundError,
)
from yanantin.apacheta.interface.abstract import INTERFACE_VERSION


class TestInterfaceABC:
    def test_cannot_instantiate(self):
        """ABC cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ApachetaInterface()

    def test_version_exposed(self):
        """INTERFACE_VERSION is a module-level constant."""
        assert INTERFACE_VERSION == "v1"


class TestExceptions:
    def test_hierarchy(self):
        """All custom exceptions inherit from ApachetaError."""
        assert issubclass(ImmutabilityError, ApachetaError)
        assert issubclass(AccessDeniedError, ApachetaError)
        assert issubclass(NotFoundError, ApachetaError)
        assert issubclass(InterfaceVersionError, ApachetaError)

    def test_apacheta_error_is_exception(self):
        assert issubclass(ApachetaError, Exception)

    def test_raise_immutability(self):
        with pytest.raises(ImmutabilityError):
            raise ImmutabilityError("tensor already exists")

    def test_raise_not_found(self):
        with pytest.raises(NotFoundError):
            raise NotFoundError("no such tensor")
