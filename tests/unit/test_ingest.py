"""Tests for the cold start markdown tensor parser."""

from pathlib import Path

import pytest

from yanantin.apacheta.backends.memory import InMemoryBackend
from yanantin.apacheta.ingest.markdown_parser import (
    ingest_tensor_directory,
    parse_tensor_file,
)


class TestMarkdownParser:
    def test_parse_t0_has_strands(self):
        path = Path(
            "/home/tony/.claude/projects/-home-tony-projects-ai-honesty/memory/"
            "conversation_tensor_20260207.md"
        )
        tensor = parse_tensor_file(path)
        assert len(tensor.strands) == 6
        assert tensor.provenance.author_model_family == "claude"

    def test_parse_chatgpt_tensor(self):
        path = Path(
            "/home/tony/.claude/projects/-home-tony-projects-ai-honesty/memory/"
            "conversation_tensor_20260208_chatgpt_t4.md"
        )
        tensor = parse_tensor_file(path)
        assert tensor.provenance.author_model_family == "chatgpt"
        assert len(tensor.strands) == 7

    def test_preamble_extracted(self):
        path = Path(
            "/home/tony/.claude/projects/-home-tony-projects-ai-honesty/memory/"
            "conversation_tensor_20260208_t3.md"
        )
        tensor = parse_tensor_file(path)
        assert "does not compose" in tensor.preamble.lower()

    def test_narrative_body_preserves_raw_markdown(self):
        path = Path(
            "/home/tony/.claude/projects/-home-tony-projects-ai-honesty/memory/"
            "conversation_tensor_20260207.md"
        )
        tensor = parse_tensor_file(path)
        assert "Tensor@10%" in tensor.narrative_body

    def test_ingest_directory_finds_all_tensors(self):
        directory = Path(
            "/home/tony/.claude/projects/-home-tony-projects-ai-honesty/memory/"
        )
        tensors = ingest_tensor_directory(directory)
        assert len(tensors) == 8

    def test_ingest_directory_sorted_by_timestamp(self):
        directory = Path(
            "/home/tony/.claude/projects/-home-tony-projects-ai-honesty/memory/"
        )
        tensors = ingest_tensor_directory(directory)
        timestamps = [t.provenance.timestamp for t in tensors]
        assert timestamps == sorted(timestamps)

    def test_key_claims_extracted_from_t0(self):
        path = Path(
            "/home/tony/.claude/projects/-home-tony-projects-ai-honesty/memory/"
            "conversation_tensor_20260207.md"
        )
        tensor = parse_tensor_file(path)
        total_claims = sum(len(s.key_claims) for s in tensor.strands)
        assert total_claims > 0

    def test_lineage_tags_from_metadata(self):
        path = Path(
            "/home/tony/.claude/projects/-home-tony-projects-ai-honesty/memory/"
            "conversation_tensor_20260208_t3.md"
        )
        tensor = parse_tensor_file(path)
        assert "philosophical" in tensor.lineage_tags

    def test_cold_start_roundtrip(self):
        from yanantin.apacheta.backends.memory import InMemoryBackend

        path = Path(
            "/home/tony/.claude/projects/-home-tony-projects-ai-honesty/memory/"
            "conversation_tensor_20260207.md"
        )
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
            "conversation_tensor_20260207.md",
            "conversation_tensor_20260207_session2.md",
            "conversation_tensor_20260207_session2_t6.md",
            "conversation_tensor_20260207_session3.md",
            "conversation_tensor_20260208_chatgpt_t4.md",
            "conversation_tensor_20260208_chatgpt_t5.md",
            "conversation_tensor_20260208_session2_t7.md",
            "conversation_tensor_20260208_t3.md",
        ],
    )
    def test_parse_all_known_tensors(self, filename):
        directory = Path(
            "/home/tony/.claude/projects/-home-tony-projects-ai-honesty/memory/"
        )
        tensor = parse_tensor_file(directory / filename)
        assert tensor.preamble
        assert tensor.provenance.author_model_family in {"claude", "chatgpt"}
