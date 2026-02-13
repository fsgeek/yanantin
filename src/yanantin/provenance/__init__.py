"""Provenance: evidentiary-grade timestamping for git commits.

This module integrates OpenTimestamps to provide blockchain-anchored
proof that specific commits existed at specific times. GPG signatures
prove who authored a commit; OTS proofs prove when it existed.

Usage:
    from yanantin.provenance import stamp_commit, verify_proof, list_proofs, upgrade_pending_proofs

    # Stamp a new commit
    path = stamp_commit("abc123def456...", Path("docs/ots"))

    # Verify a proof
    status = verify_proof(Path("docs/ots/abc123def4.ots"))

    # List all proofs
    proofs = list_proofs(Path("docs/ots"))

    # Upgrade pending proofs to Bitcoin-confirmed
    upgraded = upgrade_pending_proofs(Path("docs/ots"))
"""

from yanantin.provenance.timestamp import (
    list_proofs,
    stamp_commit,
    upgrade_pending_proofs,
    verify_proof,
)

__all__ = [
    "stamp_commit",
    "verify_proof",
    "list_proofs",
    "upgrade_pending_proofs",
]
