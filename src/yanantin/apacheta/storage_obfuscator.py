"""StorageObfuscator: contract for structural obfuscation at the storage boundary.

Backends accept this protocol. The fortress (Pukara) provides the real
implementation. Devices use the transparent default.

Dependency inversion: yanantin defines the contract, Pukara implements it.
The backend never imports SchemaMap — it accepts a StorageObfuscator.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class StorageObfuscator(Protocol):
    """Contract for structural obfuscation at the storage boundary.

    Backends accept this protocol. The fortress (Pukara) provides
    the real implementation. Devices use the transparent default.
    """

    def collection_name(self, semantic: str) -> str: ...
    def field_name(self, semantic: str) -> str: ...
    def field_path(self, parts: tuple[str, ...]) -> str: ...
    def reverse_field(self, opaque: str) -> str: ...
    def obfuscate_document(self, doc: dict) -> dict: ...
    def deobfuscate_document(self, doc: dict) -> dict: ...

    @property
    def is_transparent(self) -> bool: ...


class TransparentObfuscator:
    """Identity mapping — the development/test default.

    All methods return their input unchanged. This is what
    runs when no fortress is in the path.
    """

    def collection_name(self, semantic: str) -> str:
        return semantic

    def field_name(self, semantic: str) -> str:
        return semantic

    def field_path(self, parts: tuple[str, ...]) -> str:
        """Translate a nested field path (e.g. ('provenance', 'timestamp'))
        to its storage-layer dotted form.

        Dots in a path are AQL separators, not part of field names. Each
        part is translated individually via field_name, then joined with
        ".". The transparent implementation maps each part to itself;
        a real obfuscator would map each part through field_name before
        joining.
        """
        return ".".join(parts)

    def reverse_field(self, opaque: str) -> str:
        return opaque

    def obfuscate_document(self, doc: dict) -> dict:
        return doc

    def deobfuscate_document(self, doc: dict) -> dict:
        return doc

    @property
    def is_transparent(self) -> bool:
        return True
