import hashlib
from pathlib import Path

import pydantic
import pytest

from yanantin.experiments.prompts import (
    PromptTemplate,
    compute_template_id,
    load_template,
)


def test_compute_template_id_is_12_char_sha256_prefix():
    text = "System: answer in JSON only."
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]

    template_id = compute_template_id(text)

    assert template_id == expected
    assert len(template_id) == 12
    assert all(ch in "0123456789abcdef" for ch in template_id)


def test_prompt_template_content_hash_matches_text_hash():
    text = "You are an evaluator. Score from 1-5."
    template = PromptTemplate(template_id="eval-v1", text=text)

    assert template.description == ""
    assert template.content_hash == compute_template_id(text)


def test_prompt_template_hash_depends_only_on_text():
    text = "Shared body"
    t1 = PromptTemplate(template_id="a", description="first", text=text)
    t2 = PromptTemplate(template_id="b", description="second", text=text)

    assert t1.content_hash == t2.content_hash


def test_prompt_template_is_frozen():
    template = PromptTemplate(template_id="immut", text="fixed")

    with pytest.raises(pydantic.ValidationError):
        template.text = "changed"


def test_load_template_from_yaml_path(tmp_path: Path):
    path = tmp_path / "template.yaml"
    path.write_text(
        "\n".join(
            [
                "template_id: classify-v1",
                "description: Binary classification prompt",
                "text: |",
                "  Return only yes or no.",
                "",  # trailing newline so YAML '|' clip-style keeps a final \n
            ]
        )
    )

    template = load_template(path)

    assert isinstance(template, PromptTemplate)
    assert template.template_id == "classify-v1"
    assert template.description == "Binary classification prompt"
    assert template.text == "Return only yes or no.\n"
    assert template.content_hash == compute_template_id(template.text)


def test_load_template_accepts_str_path(tmp_path: Path):
    path = tmp_path / "template.yaml"
    path.write_text("template_id: quick\ntext: short")

    template = load_template(str(path))

    assert template.template_id == "quick"
    assert template.description == ""
    assert template.content_hash == compute_template_id("short")


def test_load_template_validation_error_on_missing_required_fields(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("description: missing required keys")

    with pytest.raises(pydantic.ValidationError):
        load_template(path)
