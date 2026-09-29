"""Passages: the unit the find() BM25 index ranks.

A passage is one unique ``(session, dotted path, string value)`` leaf of a
stored record. The leaf rules are identical to the frozen instrument
``eval/find_quality.py`` (``record_leaves``); a parity test enforces that.

``sync_passages`` is the idempotent backfill for records written by clients
that know nothing about passages. CLI: ``python -m yanantin.apacheta.passages sync``.
"""

from __future__ import annotations

import hashlib
import re

_EXCLUDED_TOP = ("provenance", "lineage_tags")
_CYCLE_TAG = re.compile(r"^cycle-(\d+)$")


def _leaves(value, path: tuple):
    if isinstance(value, dict):
        for k, v in value.items():
            if str(k).startswith("_"):
                continue
            yield from _leaves(v, path + (str(k),))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _leaves(v, path + (str(i),))
    elif isinstance(value, str):
        yield ".".join(path), value


def passage_text(path: str, value: str) -> str:
    """Humanized path (``_`` and ``.`` to spaces) + ``": "`` + value with ``_`` to spaces."""
    return path.replace("_", " ").replace(".", " ") + ": " + value.replace("_", " ")


def derive_passages(doc: dict, record_key: str) -> list[dict]:
    """Passages of one stored (pre-obfuscation) record document.

    Session is ``provenance.author_instance_id``; a record without provenance
    is its own session, so such records never share passages.
    """
    provenance = doc.get("provenance")
    session = provenance["author_instance_id"] if provenance else record_key
    passages: dict[str, dict] = {}
    for k, v in doc.items():
        if k.startswith("_") or k in _EXCLUDED_TOP:
            continue
        for path, value in _leaves(v, (k,)):
            key = hashlib.sha256(f"{session}\0{path}\0{value}".encode()).hexdigest()[:16]
            passages.setdefault(key, {
                "_key": key,
                "session": session,
                "path": path,
                "value": value,
                "record_key": record_key,
                "text": passage_text(path, value),
            })
    return list(passages.values())


def _record_order(doc: dict):
    """Instrument order: cycle (cycle-less last), then timestamp, then key."""
    cycle = None
    for tag in doc.get("lineage_tags") or ():
        m = _CYCLE_TAG.match(str(tag))
        if m:
            cycle = int(m.group(1))
            break
    timestamp = (doc.get("provenance") or {}).get("timestamp") or ""
    return (cycle is None, cycle or 0, timestamp, doc["_key"])


def sync_passages(backend) -> int:
    """Insert every missing passage, first owner wins. Returns how many were added."""
    if not backend._map.is_transparent:
        raise RuntimeError("Passages exist only under a transparent storage map.")
    with backend._lock:
        records = backend._db.collection(backend._map.collection_name("records"))
        passages = backend._db.collection(backend._map.collection_name("passages"))
        before = passages.count()
        clear = (backend._map.deobfuscate_document(doc) for doc in records.all())
        for doc in sorted(clear, key=_record_order):
            docs = [backend._map.obfuscate_document(p)
                    for p in derive_passages(doc, doc["_key"])]
            if docs:
                passages.insert_many(
                    docs, overwrite_mode="ignore", raise_on_document_error=True
                )
        return passages.count() - before


if __name__ == "__main__":
    import argparse

    from yanantin.apacheta import connect

    parser = argparse.ArgumentParser(description="Passage index maintenance")
    parser.add_argument("command", choices=["sync"])
    parser.parse_args()
    print(f"{sync_passages(connect())} passages added")
