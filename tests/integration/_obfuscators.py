"""Shared test obfuscator stand-ins for core integration tests.

A non-transparent StorageObfuscator that rewrites collection AND field names
deterministically and reversibly — the stand-in for Pukara's SchemaMap. Used by
the RegistrationService and CLI integration tests so the base catalog lands under
a unique, isolated, obfuscated collection per test (and so neither test file
duplicates the stand-in).
"""

from __future__ import annotations


class PrefixObfuscator:
    """Prefixes every collection and field name. Reversible; document keys
    starting with '_' (ArangoDB internals) pass through untouched."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    def collection_name(self, semantic: str) -> str:
        return f"{self._prefix}{semantic}"

    def field_name(self, semantic: str) -> str:
        return f"{self._prefix}{semantic}"

    def field_path(self, parts: tuple[str, ...]) -> str:
        return ".".join(self.field_name(p) for p in parts)

    def reverse_field(self, opaque: str) -> str:
        return opaque[len(self._prefix):] if opaque.startswith(self._prefix) else opaque

    def obfuscate_document(self, doc: dict) -> dict:
        return {
            (k if k.startswith("_") else self.field_name(k)): v
            for k, v in doc.items()
        }

    def deobfuscate_document(self, doc: dict) -> dict:
        return {
            (k if k.startswith("_") else self.reverse_field(k)): v
            for k, v in doc.items()
        }

    @property
    def is_transparent(self) -> bool:
        return False
