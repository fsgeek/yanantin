<!-- Chasqui Scour Tensor
     Run: 476
     Model: google/gemma-3n-e4b-it (Google: Gemma 3n 4B)
     Target: src/yanantin/chasqui
     Scope: introspection
     Cost: prompt=$2e-08/M, completion=$4e-08/M
     Usage: {'prompt_tokens': 18586, 'completion_tokens': 1579, 'total_tokens': 20165, 'cost': 0.00043488, 'is_byok': False, 'prompt_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0, 'audio_tokens': 0, 'video_tokens': 0}, 'cost_details': {'upstream_inference_cost': 0.00043488, 'upstream_inference_prompt_cost': 0.00037172, 'upstream_inference_completions_cost': 6.316e-05}, 'completion_tokens_details': {'reasoning_tokens': 0, 'image_tokens': 0, 'audio_tokens': 0}}
     Timestamp: 2026-03-08T12:47:43.878170+00:00
-->

```python
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

from willay.models import EpistemicMetadata, Evaluation, ReceiptRecord

logger = logging.getLogger(__name__)

_WILLAY_AVAILABLE = False
try:
    from willay.models import (
        AttestorProfile,
        Evaluation,
        EvidenceArtifact,
        MethodologyRecord,
        ReceiptRecord,
    )
    from willay.ledger import Ledger

    _WILLAY_AVAILABLE = True
except ImportError:
    pass

# Constants
EVALUATOR_ID = "chasqui.evaluator.cross_model_verification"
EVALUATOR_VERSION = "v1"
DEFAULT_LEDGER_PATH = Path("~/.local/share/yanantin/verification_ledger.jsonl").expanduser()

# Shared declared losses
_common_declared_losses() = (
    DeclaredLoss(
        what_was_lost="Single-LLM verification",
        why="One model checked one file — no cross-verification, no human review",
        category=LossCategory.PRACTICAL_CONSTRAINT,
        severity=0.7,
        severity_rationale="Primary limitation of automated verification",
    ),
    DeclaredLoss(
        what_was_lost="Hallucination risk in verifier",
        why="The verifying model may hallucinate agreement or disagreement with claims",
        category=LossCategory.TRAVERSAL_BIAS,
        severity=0.6,
        severity_rationale="LLMs are known to confabulate verification results",
    ),
    DeclaredLoss(
        what_was_lost="Temporal code drift",
        why="Source file may have changed between claim extraction and verification",
        category=LossCategory.PRACTICAL_CONSTRAINT,
        severity=0.4,
        severity_rationale="Mitigated by file hashing but not eliminated",
    ),
)

_VERDICT_EPISTEMICS: dict[str, tuple[float, float, float]] = {
    "CONFIRMED": (0.7, 0.3, 0.0),
    "DENIED": (0.0, 0.2, 0.7),
    "INDETERMINATE": (0.0, 0.9, 0.0),
    "MODEL_FAILURE": (0.0, 1.0, 0.0),
}

_VERDICT_QUESTIONS: dict[str, tuple[str, ...]] = {
    "CONFIRMED": ("Would a second model agree?", "Does the code still match?"),
    "DENIED": ("Is the verifier correct in its denial?", "Has the code been updated since the claim?"),
    "INDETERMINATE": ("Would a different model reach a verdict?", "Is more context needed?"),
    "MODEL_FAILURE": ("Is this model consistently failing?", "Should this model be deprioritized?"),
}

# Public API
def verdict_to_evaluation(
    verdict: str,
    claim_text: str,
    file_path: str,
    verifier_model: str,
    source_model: str,
) -> Evaluation:
    """Map a Chasqui verdict to a Willay Evaluation with honest T/I/F."""
    if not _WILLAY_AVAILABLE:
        raise ImportError("willay is not installed")

    t, i, f = _VERDICT_EPISTEMICS.get(verdict, (0.0, 1.0, 0.0))

    return Evaluation(
        epistemic=EpistemicMetadata(truth=t, indeterminacy=i, falsity=f),
        declared_losses=_common_declared_losses(),
        open_questions=_VERDICT_QUESTIONS.get(verdict, ()),
        evaluator_id=EVALUATOR_ID,
        evaluator_version=EVALUATOR_VERSION,
    )


def verification_to_receipt(verify_result: dict[str, Any]) -> ReceiptRecord:
    """Convert a dispatch_verify result dict into a Willay ReceiptRecord."""
    if not _WILLAY_AVAILABLE:
        raise ImportError("willay is not installed")

    claim_text = verify_result["claim"]
    file_path = verify_result["file_path"]

    # Hash the claim text
    claim_hash = hashlib.sha256(claim_text.encode("utf-8")).hexdigest()

    # Hash the actual file content for evidence integrity
    file_sha256 = hashlib.sha256(b"").hexdigest()
    byte_count = 0
    try:
        file_data = Path(file_path).read_bytes()
        file_sha256 = hashlib.sha256(file_data).hexdigest()
        byte_count = len(file_data)
    except (OSError, ValueError):
        pass

    evidence = (
        EvidenceArtifact(
            uri=f"file://{file_path}",
            sha256=file_sha256,
            content_type="text/x-python",
            byte_count=byte_count,
            metadata={
                "verifier_model": verify_result["model"],
                "source_model": verify_result["source_model"],
                "source_tensor": verify_result.get("source_tensor", ""),
                "run_number": verify_result.get("run_number", 0),
            },
        ),
    )

    evaluation = verdict_to_evaluation(
        verdict=verify_result["verdict"],
        claim_text=claim_text,
        file_path=file_path,
        verifier_model=verify_result["model"],
        source_model=verify_result["source_model"],
    )

    return ReceiptRecord(
        claim_text=claim_text,
        claim_hash=claim_hash,
        citation=f"file://{file_path}",
        evidence=evidence,
        evaluation=evaluation,
        receipt_type="cross_model_verification.v1",
    )


def record_verification(
    verify_result: dict[str, Any],
    ledger_path: Path | None = None,
) -> str | None:
    """Record a verification result as an epistemic receipt.

    Top-level entry point. Constructs the receipt, appends to the
    hash-chained ledger, returns the entry hash.

    Returns None if Willay is not installed.
    """
    if not _WILLAY_AVAILABLE:
        raise ImportError("willay is not installed")

    ledger_path = ledger_path or DEFAULT_LEDGER_PATH
    receipt = verification_to_receipt(verify_result)
    ledger = _WILLAY_LEDGER(ledger_path)
    ledger.append(receipt)

    return ledger.last_entry.hash
```