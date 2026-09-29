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


class HashingObfuscator:
    """Opaque names with a per-test namespace; reverse lookup is test-only.

    Unlike PrefixObfuscator, no semantic word survives in a physical name.
    """

    def __init__(self, salt: str) -> None:
        self._salt = salt
        self._reverse: dict[str, str] = {}
        self.collection_names: set[str] = set()

    def _hash(self, kind: str, semantic: str) -> str:
        from hashlib import sha256

        return "h" + sha256(f"{self._salt}\0{kind}\0{semantic}".encode()).hexdigest()

    def collection_name(self, semantic: str) -> str:
        name = self._hash("collection", semantic)
        self.collection_names.add(name)
        return name

    def field_name(self, semantic: str) -> str:
        name = self._hash("field", semantic)
        self._reverse[name] = semantic
        return name

    def field_path(self, parts: tuple[str, ...]) -> str:
        return ".".join(self.field_name(part) for part in parts)

    def reverse_field(self, opaque: str) -> str:
        return self._reverse.get(opaque, opaque)

    def _transform(self, value, key_map):
        if isinstance(value, dict):
            return {
                (key if key.startswith("_") else key_map(key)): self._transform(item, key_map)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._transform(item, key_map) for item in value]
        return value

    def obfuscate_document(self, doc: dict) -> dict:
        return self._transform(doc, self.field_name)

    def deobfuscate_document(self, doc: dict) -> dict:
        return self._transform(doc, self.reverse_field)

    @property
    def is_transparent(self) -> bool:
        return False
