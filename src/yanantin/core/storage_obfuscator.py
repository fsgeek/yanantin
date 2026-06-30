"""StorageObfuscator: contract for structural obfuscation at the storage boundary.

Lives in `core` because it is a stdlib-only, dependency-inverted contract-leaf
that registration (and every backend) depends on. Reaching back into `apacheta`
for it would be an unmotivated crossing of the one-way dependency arrow
(everything depends on core; core depends on nothing but the DB singleton and
stdlib). The protocol qualifies for core under that arrow: it imports nothing.

Backends accept this protocol. The fortress (Pukara) provides the real,
keyed implementation (SchemaMap, a compute-from-key function — no stored
table). Devices use the transparent default. The backend never imports
SchemaMap; it accepts a StorageObfuscator. Dependency inversion: yanantin
defines the contract, Pukara implements it.
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

    def field_name(self, semantic: str) -> str:
        """Map ONE semantic name to its physical/obfuscated form.

        Use for document-key obfuscation on the write path
        (``mapped_doc[field_name(k)] = v``). Do NOT use to name a field in a
        query string — there, ``field_path`` is the sanctioned primitive
        (it is what the no-literal-AQL-field red bar enforces). See
        docs/design-aql-field-mapping-guardrail.md §3.
        """
        ...

    def field_path(self, parts: tuple[str, ...]) -> str:
        """Map a (possibly nested) field path to its physical AQL form.

        THE sanctioned way to name a field inside an AQL query. Each part is
        mapped through the obfuscator, so the storage name is never written by
        hand and a query that bypasses the boundary becomes inexpressible-by-
        convention (and, via the red bar, build-failing). See
        docs/design-aql-field-mapping-guardrail.md §3.
        """
        ...
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
