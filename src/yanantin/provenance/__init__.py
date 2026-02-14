"""Provenance: evidentiary-grade timestamping for git commits.

This module integrates OpenTimestamps to provide blockchain-anchored
proof that specific commits existed at specific times. GPG signatures
prove who authored a commit; OTS proofs prove when it existed.

Each commit's proof is included in the *next* commit, forming a chain.
The chain integrity monitor in chasqui_pulse verifies completeness.

Bootstrap: a new Yanantin instance must create a genesis timestamp
before its first commit so the chain starts unbroken. Use stamp_genesis()
or manually: stamp_commit(<empty-tree-hash>, ots_dir) then include the
resulting .ots file in the first commit.

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

    # Bootstrap a new instance
    path = stamp_genesis(Path("docs/ots"))
"""

from yanantin.provenance.timestamp import (
    list_proofs,
    stamp_commit,
    stamp_genesis,
    upgrade_pending_proofs,
    verify_proof,
)

__all__ = [
    "stamp_commit",
    "stamp_genesis",
    "verify_proof",
    "list_proofs",
    "upgrade_pending_proofs",
]
