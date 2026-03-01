"""Unit tests for the Chasqui -> Willay attestation adapter.

These tests verify that verification verdicts are honestly mapped to
epistemic receipts with correct T/I/F values, declared losses, and
evidence artifacts. The adapter is the bridge between Chasqui's
verification pipeline and Willay's receipt infrastructure.

Test author: separate from builder (provenance by role separation).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

willay = pytest.importorskip("willay")

from yanantin.chasqui.attestation import (
    DEFAULT_LEDGER_PATH,
    EVALUATOR_ID,
    EVALUATOR_VERSION,
    get_methodology,
    get_profile,
    record_verification,
    verdict_to_evaluation,
    verification_to_receipt,
)


# -- Helpers -----------------------------------------------------------------


def _sample_verify_result(verdict="CONFIRMED", file_path=None):
    """Return a sample dispatch_verify result dict."""
    if file_path is None:
        # Use a real file that exists so SHA-256 can be computed
        file_path = str(Path(__file__).resolve())
    return {
        "mode": "verify",
        "verdict": verdict,
        "claim": "The function handles edge cases correctly",
        "file_path": file_path,
        "source_model": "openai/gpt-4o",
        "source_tensor": "T25",
        "model": "anthropic/claude-3.5-sonnet",
        "model_name": "Claude 3.5 Sonnet",
        "cost_per_million": 3.0,
        "run_number": 1,
        "cairn_path": "/tmp/cairn/test.md",
        "content_length": 500,
        "usage": {"prompt_tokens": 100, "completion_tokens": 200},
        "pool_size": 50,
    }


# -- Verdict-to-evaluation mapping ------------------------------------------


def test_verdict_confirmed_mapping():
    """CONFIRMED -> T=0.7, I=0.3, F=0.0."""
    result = _sample_verify_result("CONFIRMED")
    evaluation = verdict_to_evaluation(
        verdict="CONFIRMED",
        claim_text=result["claim"],
        file_path=result["file_path"],
        verifier_model=result["model"],
        source_model=result["source_model"],
    )
    assert evaluation.epistemic.truth == 0.7
    assert evaluation.epistemic.indeterminacy == 0.3
    assert evaluation.epistemic.falsity == 0.0


def test_verdict_denied_mapping():
    """DENIED -> T=0.0, I=0.2, F=0.7."""
    evaluation = verdict_to_evaluation(
        verdict="DENIED",
        claim_text="test claim",
        file_path="/tmp/test.py",
        verifier_model="model-a",
        source_model="model-b",
    )
    assert evaluation.epistemic.truth == 0.0
    assert evaluation.epistemic.indeterminacy == 0.2
    assert evaluation.epistemic.falsity == 0.7


def test_verdict_indeterminate_mapping():
    """INDETERMINATE -> T=0.0, I=0.9, F=0.0."""
    evaluation = verdict_to_evaluation(
        verdict="INDETERMINATE",
        claim_text="test claim",
        file_path="/tmp/test.py",
        verifier_model="model-a",
        source_model="model-b",
    )
    assert evaluation.epistemic.truth == 0.0
    assert evaluation.epistemic.indeterminacy == 0.9
    assert evaluation.epistemic.falsity == 0.0


def test_verdict_model_failure_mapping():
    """MODEL_FAILURE -> T=0.0, I=1.0, F=0.0."""
    evaluation = verdict_to_evaluation(
        verdict="MODEL_FAILURE",
        claim_text="test claim",
        file_path="/tmp/test.py",
        verifier_model="model-a",
        source_model="model-b",
    )
    assert evaluation.epistemic.truth == 0.0
    assert evaluation.epistemic.indeterminacy == 1.0
    assert evaluation.epistemic.falsity == 0.0


def test_unknown_verdict_defaults_to_model_failure():
    """Unknown verdict string -> same as MODEL_FAILURE (T=0.0, I=1.0, F=0.0)."""
    evaluation = verdict_to_evaluation(
        verdict="NONSENSE_VERDICT",
        claim_text="test claim",
        file_path="/tmp/test.py",
        verifier_model="model-a",
        source_model="model-b",
    )
    assert evaluation.epistemic.truth == 0.0
    assert evaluation.epistemic.indeterminacy == 1.0
    assert evaluation.epistemic.falsity == 0.0


# -- Evaluation structure ---------------------------------------------------


def test_evaluation_has_declared_losses():
    """Every verdict produces an evaluation with exactly 3 declared losses."""
    for verdict in ("CONFIRMED", "DENIED", "INDETERMINATE", "MODEL_FAILURE"):
        evaluation = verdict_to_evaluation(
            verdict=verdict,
            claim_text="test",
            file_path="/tmp/test.py",
            verifier_model="m1",
            source_model="m2",
        )
        assert len(evaluation.declared_losses) == 3, (
            f"Verdict {verdict} produced {len(evaluation.declared_losses)} "
            f"declared losses, expected 3"
        )


def test_evaluation_has_open_questions():
    """Every known verdict produces an evaluation with non-empty open_questions."""
    for verdict in ("CONFIRMED", "DENIED", "INDETERMINATE", "MODEL_FAILURE"):
        evaluation = verdict_to_evaluation(
            verdict=verdict,
            claim_text="test",
            file_path="/tmp/test.py",
            verifier_model="m1",
            source_model="m2",
        )
        assert len(evaluation.open_questions) > 0, (
            f"Verdict {verdict} produced no open questions"
        )


def test_evaluation_has_evaluator_identity():
    """Evaluator ID and version match the module constants."""
    evaluation = verdict_to_evaluation(
        verdict="CONFIRMED",
        claim_text="test",
        file_path="/tmp/test.py",
        verifier_model="m1",
        source_model="m2",
    )
    assert evaluation.evaluator_id == EVALUATOR_ID
    assert evaluation.evaluator_version == EVALUATOR_VERSION


# -- Receipt structure -------------------------------------------------------


def test_receipt_structure():
    """Receipt has all required fields."""
    result = _sample_verify_result()
    receipt = verification_to_receipt(result)

    assert receipt.claim_text == result["claim"]
    assert receipt.claim_hash  # non-empty
    assert receipt.citation  # non-empty
    assert len(receipt.evidence) > 0
    assert receipt.evaluation is not None
    assert receipt.receipt_type  # non-empty


def test_receipt_claim_hash_is_sha256():
    """claim_hash = sha256(claim_text.encode('utf-8')).hexdigest()."""
    result = _sample_verify_result()
    receipt = verification_to_receipt(result)
    expected = hashlib.sha256(result["claim"].encode("utf-8")).hexdigest()
    assert receipt.claim_hash == expected


def test_receipt_citation_is_file_uri():
    """Citation starts with 'file://'."""
    result = _sample_verify_result()
    receipt = verification_to_receipt(result)
    assert receipt.citation.startswith("file://")


def test_receipt_evidence_has_file_sha256():
    """evidence[0].sha256 is a 64-char hex string (for an existing file)."""
    result = _sample_verify_result()  # uses this test file, which exists
    receipt = verification_to_receipt(result)
    sha = receipt.evidence[0].sha256
    assert len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)


def test_receipt_evidence_metadata():
    """evidence[0].metadata has verifier_model and source_model keys."""
    result = _sample_verify_result()
    receipt = verification_to_receipt(result)
    meta = receipt.evidence[0].metadata
    assert "verifier_model" in meta
    assert "source_model" in meta
    assert meta["verifier_model"] == result["model"]
    assert meta["source_model"] == result["source_model"]


def test_receipt_type():
    """receipt_type == 'cross_model_verification.v1'."""
    result = _sample_verify_result()
    receipt = verification_to_receipt(result)
    assert receipt.receipt_type == "cross_model_verification.v1"


# -- Ledger integration -----------------------------------------------------


def test_record_verification_creates_ledger(tmp_path):
    """record_verification creates a ledger file with content."""
    ledger_path = tmp_path / "test_ledger.jsonl"
    result = _sample_verify_result()
    record_verification(result, ledger_path=ledger_path)

    assert ledger_path.exists()
    content = ledger_path.read_text()
    assert len(content.strip()) > 0


def test_record_verification_hash_chain(tmp_path):
    """Two records produce a valid hash chain."""
    from willay.ledger import Ledger

    ledger_path = tmp_path / "chain_ledger.jsonl"

    result1 = _sample_verify_result("CONFIRMED")
    result2 = _sample_verify_result("DENIED")

    record_verification(result1, ledger_path=ledger_path)
    record_verification(result2, ledger_path=ledger_path)

    ledger = Ledger(ledger_path)
    valid, errors = ledger.verify_chain()
    assert valid, f"Chain verification failed: {errors}"
    assert errors == []


def test_record_verification_returns_hash(tmp_path):
    """Return value is a 64-char hex string."""
    ledger_path = tmp_path / "hash_ledger.jsonl"
    result = _sample_verify_result()
    entry_hash = record_verification(result, ledger_path=ledger_path)

    assert isinstance(entry_hash, str)
    assert len(entry_hash) == 64
    assert all(c in "0123456789abcdef" for c in entry_hash)


# -- Profile and methodology ------------------------------------------------


def test_profile_completeness():
    """get_profile() returns AttestorProfile with non-empty fields."""
    profile = get_profile()
    assert len(profile.capabilities) > 0
    assert len(profile.applicable_domains) > 0
    assert len(profile.evidence_types) > 0
    assert len(profile.declared_losses) > 0


def test_methodology_completeness():
    """get_methodology() returns MethodologyRecord with non-empty fields."""
    methodology = get_methodology()
    assert len(methodology.method_steps) > 0
    assert len(methodology.evidence_types) > 0
    assert len(methodology.applicable_scope) > 0
    assert len(methodology.declared_losses) > 0


# -- Edge case: missing file -------------------------------------------------


def test_missing_file_produces_empty_hash():
    """Nonexistent file produces sha256 of empty bytes, byte_count == 0."""
    result = _sample_verify_result(file_path="/nonexistent/path/to/file.py")
    receipt = verification_to_receipt(result)

    empty_sha = hashlib.sha256(b"").hexdigest()
    assert receipt.evidence[0].sha256 == empty_sha
    assert receipt.evidence[0].byte_count == 0
