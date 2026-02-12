"""Tests for the cold start markdown tensor parser."""

from pathlib import Path

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.ingest.markdown_parser import (
    ingest_tensor_directory,
    parse_tensor_file,
)

# Tensor files live in docs/cairn/ as T*_*.md (modern naming)
CAIRN_DIR = Path(__file__).resolve().parents[2] / "docs" / "cairn"


class TestMarkdownParser:
    def test_parse_t0_has_strands(self):
        path = CAIRN_DIR / "T0_20260207_bounded_verification.md"
        tensor = parse_tensor_file(path)
        assert len(tensor.strands) == 6
        assert tensor.provenance.author_model_family == "claude"

    def test_parse_chatgpt_tensor(self):
        path = CAIRN_DIR / "T4_20260208_rcs_observer.md"
        tensor = parse_tensor_file(path)
        assert tensor.provenance.author_model_family == "chatgpt"
        assert len(tensor.strands) == 7

    def test_preamble_extracted(self):
        path = CAIRN_DIR / "T3_20260208_the_finishing_school.md"
        tensor = parse_tensor_file(path)
        assert "does not compose" in tensor.preamble.lower()

    def test_narrative_body_preserves_raw_markdown(self):
        path = CAIRN_DIR / "T0_20260207_bounded_verification.md"
        tensor = parse_tensor_file(path)
        assert "Tensor@10%" in tensor.narrative_body

    def test_ingest_directory_finds_all_tensors(self):
        tensors = ingest_tensor_directory(CAIRN_DIR)
        # At least T0-T7 (original 8), plus T9+ as they're added
        assert len(tensors) >= 8

    def test_ingest_directory_sorted_by_timestamp(self):
        tensors = ingest_tensor_directory(CAIRN_DIR)
        timestamps = [t.provenance.timestamp for t in tensors]
        assert timestamps == sorted(timestamps)

    def test_key_claims_extracted_from_t0(self):
        path = CAIRN_DIR / "T0_20260207_bounded_verification.md"
        tensor = parse_tensor_file(path)
        total_claims = sum(len(s.key_claims) for s in tensor.strands)
        assert total_claims > 0

    def test_lineage_tags_from_metadata(self):
        path = CAIRN_DIR / "T3_20260208_the_finishing_school.md"
        tensor = parse_tensor_file(path)
        assert "philosophical" in tensor.lineage_tags

    def test_cold_start_roundtrip(self):
        from yanantin.apacheta.backends.memory import InMemoryBackend

        path = CAIRN_DIR / "T0_20260207_bounded_verification.md"
        tensor = parse_tensor_file(path)
        backend = InMemoryBackend()
        backend.store_tensor(tensor)
        retrieved = backend.get_tensor(tensor.id)
        assert retrieved.provenance.author_model_family == "claude"
        assert len(retrieved.strands) == len(tensor.strands)


class TestMarkdownParserInvariants:
    @pytest.mark.parametrize(
        "filename",
        [
            "T0_20260207_bounded_verification.md",
            "T1_20260207_seven_projects.md",
            "T2_20260207_calibration_recovery.md",
            "T3_20260208_the_finishing_school.md",
            "T4_20260208_rcs_observer.md",
            "T5_20260208_post_paper.md",
            "T6_20260207_built_then_saw.md",
            "T7_20260208_the_wanderer.md",
        ],
    )
    def test_parse_all_known_tensors(self, filename):
        tensor = parse_tensor_file(CAIRN_DIR / filename)
        assert tensor.preamble
        assert tensor.provenance.author_model_family in {"claude", "chatgpt"}
