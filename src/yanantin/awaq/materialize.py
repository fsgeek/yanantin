"""Materialize composition graph — wire Awaq declarations into Apacheta.

Takes CompositionDeclarations (string labels like "T0", "T15") and
converts them to CompositionEdge/NegationRecord objects with real UUIDs,
then stores them through the ApachetaInterface.

Steps:
1. Parse cairn tensors → build label→TensorRecord map
2. Ensure all referenced tensors are stored in the backend
3. Convert declarations to edges/negations
4. Store via interface

Works with any backend (InMemory for testing, ArangoDB for production,
GatewayClient for Pukara path).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from yanantin.apacheta.ingest.markdown_parser import (
    TENSOR_METADATA,
    parse_tensor_file,
)
from yanantin.apacheta.interface.abstract import ApachetaInterface
from yanantin.apacheta.interface.errors import ImmutabilityError
from yanantin.apacheta.models.composition import (
    CompositionEdge,
    NegationRecord,
    RelationType,
)
from yanantin.apacheta.models.provenance import ProvenanceEnvelope
from yanantin.apacheta.models.tensor import TensorRecord
from yanantin.awaq.weaver import CompositionDeclaration

logger = logging.getLogger(__name__)

# ── Label extraction ─────────────────────────────────────────────

_LABEL_FROM_FILENAME = re.compile(r"^(T\d+)_")


def extract_label(path: Path) -> str:
    """Extract short tensor label (T0, T1, ...) from a cairn filename.

    Uses TENSOR_METADATA for known files, falls back to parsing the
    T{N}_ prefix pattern.
    """
    meta = TENSOR_METADATA.get(path.name, {})
    if "label" in meta:
        return meta["label"]
    m = _LABEL_FROM_FILENAME.match(path.name)
    if m:
        return m.group(1)
    return path.stem


# ── Relation mapping ─────────────────────────────────────────────

# Maps Awaq relation strings to (is_edge, RelationType_or_None)
# is_edge=False means it's a NegationRecord, not a CompositionEdge
_RELATION_MAP: dict[str, tuple[bool, RelationType | None]] = {
    "composes_with": (True, RelationType.COMPOSES_WITH),
    "bridges": (True, RelationType.BRIDGES),
    "corrects": (True, RelationType.CORRECTS),
    "branches_from": (True, RelationType.BRANCHES_FROM),
    "read": (True, RelationType.COMPOSES_WITH),
    "does_not_compose_with": (False, None),
    "standalone": (False, None),  # No edge — explicit declaration of no predecessors
}


# ── Result types ─────────────────────────────────────────────────

@dataclass
class MaterializeResult:
    """Summary of materialization."""

    tensors_stored: int
    tensors_skipped: int
    edges_stored: int
    negations_stored: int
    skipped_unknown: list[str]  # labels referenced but not found
    skipped_existing: int  # edges that already existed


# ── Core logic ───────────────────────────────────────────────────

def discover_cairn_tensors(cairn_dir: Path) -> dict[str, tuple[str, TensorRecord]]:
    """Parse all cairn tensor files, return label→(filename, TensorRecord) map.

    Only includes T*_*.md files (modern naming). Deduplicates by label.
    """
    label_map: dict[str, tuple[str, TensorRecord]] = {}

    for path in sorted(cairn_dir.glob("T[0-9]*_*.md")):
        label = extract_label(path)
        if label in label_map:
            continue
        tensor = parse_tensor_file(path)
        label_map[label] = (path.name, tensor)
        logger.debug("Parsed %s → %s (UUID: %s)", path.name, label, tensor.id)

    return label_map


def ensure_tensors_stored(
    interface: ApachetaInterface,
    label_map: dict[str, tuple[str, TensorRecord]],
) -> tuple[dict[str, UUID], int, int]:
    """Store tensors in the backend, return label→UUID map.

    If a tensor already exists (ImmutabilityError), we need its UUID
    from the backend. Falls back to the parsed UUID if store succeeds.

    Returns:
        (label_to_uuid, stored_count, skipped_count)
    """
    label_to_uuid: dict[str, UUID] = {}
    stored = 0
    skipped = 0

    # First, try to map from already-stored tensors
    try:
        existing = interface.list_tensors()
        for tensor in existing:
            # Extract label from provenance.author_instance_id
            aid = tensor.provenance.author_instance_id
            if aid.endswith("-original"):
                candidate = aid[: -len("-original")]
                # Check if it's a known short label (T0, T1, ...)
                if re.match(r"^T\d+$", candidate):
                    label_to_uuid[candidate] = tensor.id
                else:
                    # Try extracting from filename-style label
                    m = _LABEL_FROM_FILENAME.match(candidate)
                    if m:
                        label_to_uuid[m.group(1)] = tensor.id
    except Exception as e:
        logger.warning("Could not list existing tensors: %s", e)

    # Store any missing tensors
    for label, (filename, tensor) in label_map.items():
        if label in label_to_uuid:
            skipped += 1
            continue
        try:
            interface.store_tensor(tensor)
            label_to_uuid[label] = tensor.id
            stored += 1
            logger.info("Stored %s as %s", label, tensor.id)
        except ImmutabilityError:
            # Already stored but we didn't find it via list
            label_to_uuid[label] = tensor.id
            skipped += 1
        except Exception as e:
            logger.error("Failed to store %s: %s", label, e)

    return label_to_uuid, stored, skipped


def declarations_to_edges(
    declarations: list[CompositionDeclaration],
    label_to_uuid: dict[str, UUID],
) -> tuple[list[CompositionEdge], list[NegationRecord], list[str]]:
    """Convert Awaq declarations to typed edge/negation objects.

    Returns:
        (edges, negations, unknown_labels)
    """
    edges: list[CompositionEdge] = []
    negations: list[NegationRecord] = []
    unknown: set[str] = set()

    for decl in declarations:
        source_uuid = label_to_uuid.get(decl.source)
        if source_uuid is None:
            unknown.add(decl.source)
            continue

        is_edge, relation_type = _RELATION_MAP.get(
            decl.relation, (True, RelationType.COMPOSES_WITH)
        )

        for target in decl.targets:
            target_uuid = label_to_uuid.get(target)
            if target_uuid is None:
                unknown.add(target)
                continue

            provenance = ProvenanceEnvelope(
                author_model_family="awaq",
                author_instance_id="materializer-v1",
                interface_version="v1",
            )

            if is_edge:
                mapping = decl.evidence if decl.relation in ("bridges", "read") else None
                edge = CompositionEdge(
                    from_tensor=source_uuid,
                    to_tensor=target_uuid,
                    relation_type=relation_type,
                    authored_mapping=mapping,
                    provenance=provenance,
                )
                edges.append(edge)
            else:
                negation = NegationRecord(
                    tensor_a=source_uuid,
                    tensor_b=target_uuid,
                    reasoning=decl.evidence,
                    provenance=provenance,
                )
                negations.append(negation)

    return edges, negations, sorted(unknown)


def store_edges(
    interface: ApachetaInterface,
    edges: list[CompositionEdge],
    negations: list[NegationRecord],
) -> tuple[int, int, int]:
    """Store edges and negations. Returns (edges_stored, negations_stored, skipped)."""
    stored_edges = 0
    stored_negations = 0
    skipped = 0

    for edge in edges:
        try:
            interface.store_composition_edge(edge)
            stored_edges += 1
        except ImmutabilityError:
            skipped += 1
        except Exception as e:
            logger.error("Failed to store edge %s→%s: %s", edge.from_tensor, edge.to_tensor, e)

    for negation in negations:
        try:
            interface.store_negation(negation)
            stored_negations += 1
        except ImmutabilityError:
            skipped += 1
        except Exception as e:
            logger.error("Failed to store negation %s↔%s: %s", negation.tensor_a, negation.tensor_b, e)

    return stored_edges, stored_negations, skipped


def materialize(
    interface: ApachetaInterface,
    declarations: list[CompositionDeclaration],
    cairn_dir: Path,
) -> MaterializeResult:
    """Full materialization pipeline.

    1. Parse cairn tensors
    2. Ensure all are stored in the backend
    3. Convert declarations to edges
    4. Store edges

    Args:
        interface: Any ApachetaInterface implementation.
        declarations: Output from Awaq's weave_corpus().
        cairn_dir: Path to docs/cairn/.

    Returns:
        MaterializeResult with counts and diagnostics.
    """
    # Step 1: Parse cairn
    label_map = discover_cairn_tensors(cairn_dir)
    logger.info("Discovered %d tensors in cairn", len(label_map))

    # Step 2: Ensure stored
    label_to_uuid, tensors_stored, tensors_skipped = ensure_tensors_stored(
        interface, label_map
    )
    logger.info(
        "Tensors: %d stored, %d skipped (already existed)",
        tensors_stored,
        tensors_skipped,
    )

    # Step 3: Convert declarations
    edges, negations, unknown = declarations_to_edges(declarations, label_to_uuid)
    logger.info(
        "Converted: %d edges, %d negations, %d unknown labels",
        len(edges),
        len(negations),
        len(unknown),
    )

    # Step 4: Store
    edges_stored, negations_stored, skipped_existing = store_edges(
        interface, edges, negations
    )
    logger.info(
        "Stored: %d edges, %d negations, %d skipped (existing)",
        edges_stored,
        negations_stored,
        skipped_existing,
    )

    return MaterializeResult(
        tensors_stored=tensors_stored,
        tensors_skipped=tensors_skipped,
        edges_stored=edges_stored,
        negations_stored=negations_stored,
        skipped_unknown=unknown,
        skipped_existing=skipped_existing,
    )
