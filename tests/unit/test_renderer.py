"""Unit tests for the markdown renderer."""

from datetime import datetime
from uuid import uuid4

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.models import (
    CorrectionRecord,
    DeclaredLoss,
    EpistemicMetadata,
    KeyClaim,
    LossCategory,
    ProvenanceEnvelope,
    StrandRecord,
    TensorRecord,
)
from yanantin.apacheta.renderer.markdown import (
    render_composition_view,
    render_correction_chain,
    render_tensor,
)


@pytest.fixture
def sample_tensor():
    return TensorRecord(
        provenance=ProvenanceEnvelope(
            author_model_family="claude",
            timestamp=datetime(2026, 2, 8),
            context_budget_at_write=0.07,
        ),
        preamble="This is not a summary.",
        strands=[
            StrandRecord(
                strand_index=0,
                title="Experimental State",
                content="800 rows of data.",
                topics=["experiment-27", "calibration"],
                key_claims=[
                    KeyClaim(
                        text="Tensor@10% > Text@30%",
                        epistemic=EpistemicMetadata(truth=0.9, indeterminacy=0.1),
                    ),
                ],
            ),
            StrandRecord(
                strand_index=1,
                title="Insights",
                content="Six observations.",
                topics=["epistemic"],
            ),
        ],
        closing="An instance that preserved what mattered",
        instructions_for_next="Don't overwrite this. Compose.",
        lineage_tags=["experimental-sequence"],
        declared_losses=[
            DeclaredLoss(
                what_was_lost="Chronological detail",
                why="Context pressure",
                category=LossCategory.CONTEXT_PRESSURE,
            ),
        ],
        open_questions=["How does the archivist query?"],
    )


class TestRenderTensor:
    def test_preserves_strand_structure(self, sample_tensor):
        output = render_tensor(sample_tensor)
        assert "## Strand 0: Experimental State" in output
        assert "## Strand 1: Insights" in output

    def test_includes_preamble(self, sample_tensor):
        output = render_tensor(sample_tensor)
        assert "This is not a summary." in output

    def test_includes_closing(self, sample_tensor):
        output = render_tensor(sample_tensor)
        assert "An instance that preserved what mattered" in output

    def test_includes_instructions(self, sample_tensor):
        output = render_tensor(sample_tensor)
        assert "Don't overwrite this. Compose." in output

    def test_includes_losses(self, sample_tensor):
        output = render_tensor(sample_tensor)
        assert "The losses are mine." in output
        assert "Chronological detail" in output

    def test_includes_open_questions(self, sample_tensor):
        output = render_tensor(sample_tensor)
        assert "How does the archivist query?" in output

    def test_metadata_flag_adds_tif(self, sample_tensor):
        output_without = render_tensor(sample_tensor, include_metadata=False)
        output_with = render_tensor(sample_tensor, include_metadata=True)
        assert "T/I/F" not in output_without
        assert "T/I/F" in output_with

    def test_metadata_includes_provenance(self, sample_tensor):
        output = render_tensor(sample_tensor, include_metadata=True)
        assert "claude" in output
        assert "7%" in output
        assert "experimental-sequence" in output

    def test_metadata_includes_claims(self, sample_tensor):
        output = render_tensor(sample_tensor, include_metadata=True)
        assert "Tensor@10% > Text@30%" in output
        assert "T=0.9" in output

    def test_strand_topics_rendered(self, sample_tensor):
        output = render_tensor(sample_tensor)
        assert "experiment-27" in output

    def test_minimal_tensor(self):
        tensor = TensorRecord()
        output = render_tensor(tensor)
        assert isinstance(output, str)


class TestRenderCompositionView:
    def test_attribution_preserved(self):
        backend = InMemoryBackend()
        t_a = TensorRecord(
            preamble="Tensor A",
            provenance=ProvenanceEnvelope(author_model_family="claude"),
        )
        t_b = TensorRecord(
            preamble="Tensor B",
            provenance=ProvenanceEnvelope(author_model_family="chatgpt"),
        )
        backend.store_tensor(t_a)
        backend.store_tensor(t_b)

        output = render_composition_view(backend, [t_a.id, t_b.id])
        assert "Composed View" in output
        assert "claude" in output
        assert "chatgpt" in output
        assert "Tensor A" in output
        assert "Tensor B" in output

    def test_respects_reading_order(self):
        backend = InMemoryBackend()
        t_a = TensorRecord(preamble="First")
        t_b = TensorRecord(preamble="Second")
        backend.store_tensor(t_a)
        backend.store_tensor(t_b)

        output = render_composition_view(
            backend, [t_a.id, t_b.id],
            reading_order=[t_b.id, t_a.id],
        )
        pos_second = output.index("Second")
        pos_first = output.index("First")
        assert pos_second < pos_first


class TestRenderCorrectionChain:
    def test_renders_corrections(self):
        backend = InMemoryBackend()
        claim_id = uuid4()
        corr = CorrectionRecord(
            target_tensor=uuid4(),
            target_claim_id=claim_id,
            original_claim="Entropy measures truth",
            corrected_claim="Entropy measures familiarity",
            evidence="Observed in T0",
        )
        backend.store_correction(corr)

        output = render_correction_chain(backend, claim_id)
        assert "Correction Chain" in output
        assert "Entropy measures truth" in output
        assert "Entropy measures familiarity" in output
        assert "Observed in T0" in output

    def test_no_corrections(self):
        backend = InMemoryBackend()
        output = render_correction_chain(backend, uuid4())
        assert "No corrections found" in output
