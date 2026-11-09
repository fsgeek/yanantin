"""Abstract base for machine identity collectors."""

from __future__ import annotations

from pathlib import Path


def _get_machine_id(path: Path = Path("/etc/machine-id")) -> str:
    """Read the machine-id, or refuse.

    There is no fallback. A hostname-derived guess (the old behaviour) changes
    when the machine is renamed, and a wrong identity is worse than none:
    objects written under it are attributed to a machine that doesn't exist
    (docs/design-machine-identity-evidence.md, decision 2; Codex finding 9).
    """
    from yanantin.machine.evidence import valid_machine_id

    try:
        text = path.read_text().strip()
    except OSError as e:
        raise RuntimeError(
            f"no readable machine-id at {path} ({type(e).__name__}); yanantin will not guess an "
            "identity, because a guessed one changes when the machine is renamed") from e
    if not valid_machine_id(text):
        raise RuntimeError(f"invalid machine-id {text!r} at {path}: expected 32 hex digits, not all zeros")
    return text
