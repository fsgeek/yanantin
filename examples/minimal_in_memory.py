"""Minimal Apacheta example using the in-memory backend.

Run from the repository root:

    uv run python examples/minimal_in_memory.py

Or, after installing yanantin into an environment:

    python examples/minimal_in_memory.py
"""

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.models import (
    DeclaredLoss,
    LossCategory,
    ProvenanceEnvelope,
    StrandRecord,
    TensorRecord,
)


def main() -> None:
    store = InMemoryBackend()

    tensor = TensorRecord(
        provenance=ProvenanceEnvelope(
            author_instance_id="minimal-example",
            author_model_family="human",
        ),
        preamble="A small authored memory.",
        strands=(
            StrandRecord(
                strand_index=0,
                title="Observation",
                content="The in-memory backend stores immutable tensors for local use.",
                topics=("quickstart", "apacheta"),
            ),
        ),
        declared_losses=(
            DeclaredLoss(
                what_was_lost="Persistence",
                why="The in-memory backend disappears when the process exits.",
                category=LossCategory.PRACTICAL_CONSTRAINT,
                severity=0.2,
                severity_rationale="Acceptable for examples, not for durable storage.",
            ),
        ),
        lineage_tags=("example",),
        open_questions=(
            "Which persistent backend should this deployment use?",
        ),
    )

    store.store_tensor(tensor)
    round_tripped = store.get_tensor(tensor.id)

    print(f"stored tensor: {round_tripped.id}")
    print(f"preamble: {round_tripped.preamble}")
    print(f"strand: {round_tripped.strands[0].title}")
    print(f"declared loss: {round_tripped.declared_losses[0].what_was_lost}")


if __name__ == "__main__":
    main()
