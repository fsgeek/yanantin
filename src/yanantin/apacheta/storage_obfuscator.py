"""Back-compat re-export. The StorageObfuscator contract MOVED to core.

The canonical home is `yanantin.core.storage_obfuscator` — it is a
stdlib-only contract-leaf the core depends on, so it lives below apacheta,
not inside it. This module re-exports it so existing import paths keep
working; new code should import from `yanantin.core.storage_obfuscator`.
"""

from __future__ import annotations

from yanantin.core.storage_obfuscator import (
    StorageObfuscator,
    TransparentObfuscator,
)

__all__ = ["StorageObfuscator", "TransparentObfuscator"]
