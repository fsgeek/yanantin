"""Unstructured content transducer: file -> structured content elements.

Ported from Indaleko (semantic/collectors/unstructured) — the CONTRACT, not the
baggage. Indaleko's version carried INDALEKO_ROOT bootstrapping, configparser
.ini config, icecream logging, and Windows-path munging; none of that comes
across. What ports is the 18-line contract that ran inside the container:

    partition(file) -> elements -> elements_to_dicts -> [{type, text, ...}]

and the host-side mechanism: pull the stock image, run it against a bind-mounted
file via the `docker` Python SDK, collect the structured output.

Transducer-agnostic slot: this emits a `content` string (the concatenated
element text) that the content BM25 view indexes. A later engine (Docling — see
the freshness-check memory) swaps in here without touching the view or find path.

Docker gating: `docker_available()` is the narrow guard. When the daemon is
unreachable (e.g. DOCKER_HOST points at a dead endpoint), callers/tests skip the
live-run NARROWLY rather than silently passing — green-from-inside a broken
docker env is not authoritative.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_UNSTRUCTURED_IMAGE = "downloads.unstructured.io/unstructured-io/unstructured"
_MEM_LIMIT = "5g"

# The in-container script: exactly Indaleko's docker_script.py contract, reduced
# to a single file (no JSONL batch wrapper — one file per invocation keeps the
# host side simple; batching is a later optimization, cf. the Indaleko batch scar).
_IN_CONTAINER_SCRIPT = (
    "import json,sys;"
    "from unstructured.partition.auto import partition;"
    "from unstructured.staging.base import elements_to_dicts;"
    "els=partition(sys.argv[1]);"
    "print(json.dumps(elements_to_dicts(els)))"
)


@dataclass(frozen=True)
class ContentFact:
    """Transducer output for one file: the indexable text plus the structured
    elements it came from. `content` is what the BM25 view indexes; `elements`
    is the full structure, kept (don't-throw-anything-away)."""

    uri: str
    content: str
    elements: tuple[dict, ...] = field(default_factory=tuple)


def docker_available() -> bool:
    """True iff a docker daemon is reachable. The narrow gate for live runs."""
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


def _elements_to_content_fact(uri: str, elements: list[dict]) -> ContentFact:
    """Fold Unstructured's element dicts into a ContentFact. `content` is the
    concatenated element text — the string the BM25 analyzer tokenizes."""
    text = "\n".join(
        e["text"] for e in elements if isinstance(e.get("text"), str) and e["text"]
    )
    return ContentFact(uri=uri, content=text, elements=tuple(elements))


def unstructured_available() -> bool:
    """True iff the `unstructured` package can partition in-process (no daemon)."""
    try:
        from unstructured.partition.auto import partition  # noqa: F401

        return True
    except Exception:
        return False


def transduce_in_process(file_path: Path) -> ContentFact:
    """Run Unstructured over one file IN-PROCESS — the pip package directly, no
    docker. The same partition() contract Indaleko ran in a container; the
    container was dependency-isolation transport, not the transducer. This is the
    simpler default (CLAUDE.md §2). Raises ImportError if `unstructured` (or the
    per-format extra, e.g. unstructured[md]) is not installed.
    """
    from unstructured.partition.auto import partition
    from unstructured.staging.base import elements_to_dicts

    resolved = file_path.resolve()
    elements = elements_to_dicts(partition(str(resolved)))
    return _elements_to_content_fact(resolved.as_uri(), elements)


def transduce(file_path: Path, image: str = _UNSTRUCTURED_IMAGE) -> ContentFact:
    """Run Unstructured over one file in the stock container; return a ContentFact.

    The docker TRANSPORT — dependency isolation, per Indaleko. For the simpler
    in-process path (no daemon), use transduce_in_process(). Raises RuntimeError
    if docker is unreachable — callers gate on docker_available().
    """
    import docker

    if not docker_available():
        raise RuntimeError(
            "docker daemon unreachable — cannot run the Unstructured transducer "
            "(check DOCKER_HOST / Docker Desktop WSL integration)"
        )

    resolved = file_path.resolve()
    client = docker.from_env()
    # Bind-mount the file's directory read-only; run the container against it.
    mount_dir = str(resolved.parent)
    container_path = f"/data/{resolved.name}"
    raw = client.containers.run(
        image=image,
        command=["python3", "-c", _IN_CONTAINER_SCRIPT, container_path],
        volumes={mount_dir: {"bind": "/data", "mode": "ro"}},
        mem_limit=_MEM_LIMIT,
        remove=True,
        stdout=True,
        stderr=False,
    )
    elements = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
    return _elements_to_content_fact(resolved.as_uri(), elements)
