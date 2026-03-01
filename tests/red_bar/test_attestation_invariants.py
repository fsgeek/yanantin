"""Red-bar tests: Attestation pipeline structural invariants.

These tests enforce structural properties of the attestation adapter:
1. The module exists and is importable (even without Willay)
2. Attestation never blocks verification (coordinator has try/except)
3. Evaluator ID follows naming convention
4. Every verdict mapping includes declared losses
5. Optional import pattern is correctly guarded

These exist because the "two copies of system prompt" incident showed
that unverified claims propagate with increasing confidence. Attestation
is the structural fix -- these tests ensure the fix stays in place.

Test author: separate from builder (provenance by role separation).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


# -- Module existence -------------------------------------------------------


def test_attestation_module_exists():
    """The attestation adapter module must be importable."""
    from yanantin.chasqui import attestation  # noqa: F401


def test_attestation_importable_without_willay():
    """The module defines _WILLAY_AVAILABLE and guards Willay imports with try/except.

    Even if Willay is not installed, `import yanantin.chasqui.attestation`
    must succeed. The try/except pattern around Willay imports is the
    structural guard.
    """
    source_path = Path(__file__).resolve().parents[2] / "src" / "yanantin" / "chasqui" / "attestation.py"
    tree = ast.parse(source_path.read_text())

    # Check _WILLAY_AVAILABLE is defined
    has_flag = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_WILLAY_AVAILABLE":
                    has_flag = True
    assert has_flag, (
        "attestation.py must define _WILLAY_AVAILABLE to guard "
        "optional Willay imports."
    )

    # Check there's a try/except that catches ImportError around willay imports
    found_guarded_import = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            # Look for willay imports inside the try body
            for child in ast.walk(node):
                if isinstance(child, ast.ImportFrom) and child.module and "willay" in child.module:
                    # Check that at least one handler catches ImportError
                    for handler in node.handlers:
                        if handler.type is None:
                            found_guarded_import = True
                        elif isinstance(handler.type, ast.Name) and handler.type.id == "ImportError":
                            found_guarded_import = True

    assert found_guarded_import, (
        "attestation.py must guard Willay imports with try/except ImportError. "
        "Without this guard, the module crashes on import when Willay isn't installed."
    )


# -- Coordinator attestation guard ------------------------------------------


def test_coordinator_attestation_guarded():
    """The record_verification call in coordinator.py is inside try/except.

    Attestation must never block verification. The coordinator must catch
    both ImportError (Willay not installed) and Exception (any runtime
    failure) around the attestation call.
    """
    source_path = Path(__file__).resolve().parents[2] / "src" / "yanantin" / "chasqui" / "coordinator.py"
    tree = ast.parse(source_path.read_text())

    # Find try/except blocks that contain record_verification
    found_guarded = False
    catches_import_error = False
    catches_exception = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            # Check if record_verification is called anywhere in the try body
            has_attestation_call = False
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = child.func
                    if isinstance(func, ast.Name) and func.id == "record_verification":
                        has_attestation_call = True
                    elif isinstance(func, ast.Attribute) and func.attr == "record_verification":
                        has_attestation_call = True
                # Also check for import of record_verification
                if isinstance(child, ast.ImportFrom):
                    if child.names and any(
                        alias.name == "record_verification" for alias in child.names
                    ):
                        has_attestation_call = True

            if has_attestation_call:
                found_guarded = True
                for handler in node.handlers:
                    if handler.type is None:
                        catches_import_error = True
                        catches_exception = True
                    elif isinstance(handler.type, ast.Name):
                        if handler.type.id == "ImportError":
                            catches_import_error = True
                        elif handler.type.id == "Exception":
                            catches_exception = True

    assert found_guarded, (
        "coordinator.py must wrap record_verification in try/except. "
        "Attestation failure must never block verification."
    )
    assert catches_import_error, (
        "coordinator.py must catch ImportError around record_verification. "
        "This handles the case where Willay is not installed."
    )
    assert catches_exception, (
        "coordinator.py must catch Exception around record_verification. "
        "Any runtime attestation failure must not block verification."
    )


# -- Evaluator identity conventions ----------------------------------------


def test_evaluator_id_convention():
    """EVALUATOR_ID matches pattern ^[a-z_]+\\.evaluator\\.[a-z_]+$."""
    from yanantin.chasqui.attestation import EVALUATOR_ID

    pattern = r"^[a-z_]+\.evaluator\.[a-z_]+$"
    assert re.match(pattern, EVALUATOR_ID), (
        f"EVALUATOR_ID '{EVALUATOR_ID}' doesn't match convention "
        f"'{pattern}'. Convention: <system>.evaluator.<method>"
    )


def test_evaluator_version_format():
    """EVALUATOR_VERSION matches ^v\\d+$."""
    from yanantin.chasqui.attestation import EVALUATOR_VERSION

    pattern = r"^v\d+$"
    assert re.match(pattern, EVALUATOR_VERSION), (
        f"EVALUATOR_VERSION '{EVALUATOR_VERSION}' doesn't match format "
        f"'{pattern}'. Expected: v1, v2, etc."
    )


# -- Verdict coverage -------------------------------------------------------


def test_all_verdicts_mapped():
    """_VERDICT_EPISTEMICS dict contains all four known verdicts."""
    from yanantin.chasqui.attestation import _VERDICT_EPISTEMICS

    required = {"CONFIRMED", "DENIED", "INDETERMINATE", "MODEL_FAILURE"}
    missing = required - set(_VERDICT_EPISTEMICS.keys())
    assert not missing, (
        f"_VERDICT_EPISTEMICS is missing verdicts: {missing}. "
        f"Every verdict must have a T/I/F mapping."
    )


def test_all_verdicts_have_questions():
    """_VERDICT_QUESTIONS dict contains same 4 keys as _VERDICT_EPISTEMICS."""
    from yanantin.chasqui.attestation import _VERDICT_QUESTIONS

    required = {"CONFIRMED", "DENIED", "INDETERMINATE", "MODEL_FAILURE"}
    missing = required - set(_VERDICT_QUESTIONS.keys())
    assert not missing, (
        f"_VERDICT_QUESTIONS is missing verdicts: {missing}. "
        f"Every verdict must have associated open questions."
    )


# -- Declared losses --------------------------------------------------------


def test_declared_losses_always_present():
    """_common_declared_losses() returns non-empty tuple."""
    from yanantin.chasqui.attestation import _common_declared_losses

    losses = _common_declared_losses()
    assert len(losses) > 0, (
        "_common_declared_losses() returned empty tuple. "
        "Every verification must declare what it cannot guarantee."
    )


def test_declared_losses_have_severity():
    """Every DeclaredLoss from _common_declared_losses() has severity not None."""
    from yanantin.chasqui.attestation import _common_declared_losses

    losses = _common_declared_losses()
    for loss in losses:
        assert loss.severity is not None, (
            f"DeclaredLoss '{loss.what_was_lost}' has severity=None. "
            f"All common losses must declare severity for downstream routing."
        )


# -- Graceful degradation ---------------------------------------------------


def test_record_verification_returns_none_without_willay():
    """record_verification returns None (not raises) when Willay unavailable.

    This is the graceful degradation contract: the coordinator calls
    record_verification and checks the return value, it doesn't wrap
    every call in try/except. The function itself handles missing Willay.
    """
    from unittest.mock import patch

    from yanantin.chasqui import attestation

    sample = {
        "verdict": "CONFIRMED",
        "claim": "test",
        "file_path": "/tmp/test.py",
        "source_model": "m1",
        "model": "m2",
    }

    # Force the internal import to fail by patching the local import
    with patch.dict("sys.modules", {"willay.ledger": None, "willay": None}):
        # record_verification does its own try/except ImportError on
        # `from willay.ledger import Ledger`, so patching sys.modules
        # to None will cause ImportError on the inner import.
        result = attestation.record_verification(sample)

    assert result is None, (
        "record_verification must return None when Willay is not available, "
        "not raise an exception."
    )
