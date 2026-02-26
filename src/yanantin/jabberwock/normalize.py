"""Namespace normalization for Jabberwock aliases.

Each wabe (namespace) has a canonical form for its gimble (identifier).
Default: lowercase, stripped whitespace, NFKC Unicode normalization.
Specific wabes override when the namespace has different identity rules.

"FsGeek" and "fsgeek" must resolve identically in case-insensitive wabes.
Filesystem paths on Linux are case-sensitive; on macOS they aren't.
The normalizer registry handles this per-wabe.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable


# Type alias for normalizer functions: gimble in, canonical gimble out.
Normalizer = Callable[[str], str]


def _default_normalizer(gimble: str) -> str:
    """Default canonical form: lowercase, stripped, NFKC.

    Covers most namespace identity: usernames, email addresses,
    identifiers where case is irrelevant and whitespace is accidental.
    """
    return unicodedata.normalize("NFKC", gimble.strip().lower())


def _case_sensitive_normalizer(gimble: str) -> str:
    """Case-preserving canonical form: stripped, NFKC, but no lowering.

    For namespaces where case matters: Linux filesystem paths,
    base64-encoded identifiers, cryptographic hashes.
    """
    return unicodedata.normalize("NFKC", gimble.strip())


# Registry: wabe name -> normalizer function.
# Missing wabes fall through to the default normalizer.
_WABE_NORMALIZERS: dict[str, Normalizer] = {
    "filesystem-linux": _case_sensitive_normalizer,
    "sha256": _case_sensitive_normalizer,
    "content-hash": _case_sensitive_normalizer,
    "base64": _case_sensitive_normalizer,
}


def register_normalizer(wabe: str, normalizer: Normalizer) -> None:
    """Register a custom normalizer for a wabe.

    Overwrites any existing normalizer for that wabe.
    """
    _WABE_NORMALIZERS[wabe] = normalizer


def normalize_gimble(wabe: str, gimble: str) -> str:
    """Normalize a gimble according to its wabe's rules.

    Looks up the wabe in the registry. Falls back to default
    (lowercase, stripped, NFKC) if no wabe-specific normalizer
    is registered.
    """
    normalizer = _WABE_NORMALIZERS.get(wabe, _default_normalizer)
    return normalizer(gimble)
