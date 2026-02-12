"""Tests for the Chasqui scourer dispatch module.

Tests prompt construction, file reading, tensor reading, and scope validation.
No API calls are made — only local prompt building and filesystem operations.
"""

import pytest
from pathlib import Path

from yanantin.chasqui.model_selector import ModelInfo
from yanantin.chasqui.scourer import (
    VALID_SCOPES,
    SCOURER_SYSTEM_PROMPT,
    SCOURER_INTROSPECTION_TEMPLATE,
    SCOURER_EXTERNAL_TEMPLATE,
    SCOURER_TENSOR_TEMPLATE,
    format_scour_prompt,
    _read_target_contents,
    _read_tensor_contents,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_model() -> ModelInfo:
    """A minimal ModelInfo for testing prompt construction."""
    return ModelInfo(
        id="test/mock-model-7b",
        name="Mock Model 7B",
        prompt_cost=0.10,
        completion_cost=0.20,
        context_length=32_000,
    )


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """A single Python file for target reading tests."""
    f = tmp_path / "sample.py"
    f.write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    return f


@pytest.fixture
def sample_dir(tmp_path: Path) -> Path:
    """A directory with several readable files for target reading tests."""
    d = tmp_path / "project"
    d.mkdir()
    (d / "main.py").write_text("# main\nprint('hello')\n", encoding="utf-8")
    (d / "utils.py").write_text("# utils\ndef add(a, b): return a + b\n", encoding="utf-8")
    (d / "README.md").write_text("# Project\nA sample project.\n", encoding="utf-8")
    (d / "config.toml").write_text('[project]\nname = "test"\n', encoding="utf-8")
    sub = d / "sub"
    sub.mkdir()
    (sub / "nested.py").write_text("# nested module\n", encoding="utf-8")
    return d


@pytest.fixture
def cairn_dir(tmp_path: Path) -> Path:
    """A mock cairn directory with tensor files."""
    d = tmp_path / "cairn"
    d.mkdir()
    (d / "T0_20260101_seed.md").write_text(
        "# T0: The Seed\nThis is tensor zero.\n", encoding="utf-8"
    )
    (d / "T1_20260102_thread.md").write_text(
        "# T1: The Thread\nThis is tensor one.\n", encoding="utf-8"
    )
    (d / "T15_20260210_scourer.md").write_text(
        "# T15: The Scourer\nThis is tensor fifteen.\n", encoding="utf-8"
    )
    (d / "scout_0001_20260210_mock.md").write_text(
        "<!-- Scout report -->\nSome scout observations.\n", encoding="utf-8"
    )
    return d


# ── VALID_SCOPES ─────────────────────────────────────────────────────


class TestValidScopes:
    """Verify the VALID_SCOPES constant."""

    def test_contains_expected_scopes(self):
        assert VALID_SCOPES == {"introspection", "external", "tensor", "synthesis"}

    def test_is_a_set(self):
        assert isinstance(VALID_SCOPES, set)

    def test_has_introspection(self):
        assert "introspection" in VALID_SCOPES

    def test_has_external(self):
        assert "external" in VALID_SCOPES

    def test_has_tensor(self):
        assert "tensor" in VALID_SCOPES


# ── format_scour_prompt ──────────────────────────────────────────────


class TestFormatScourPrompt:
    """Tests for the main prompt construction function."""

    def test_returns_tuple_of_system_and_messages(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        system, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
        )
        assert isinstance(system, str)
        assert isinstance(messages, list)

    def test_system_prompt_is_nonempty_string(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        system, _ = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
        )
        assert len(system) > 0
        assert system == SCOURER_SYSTEM_PROMPT

    def test_messages_has_at_least_one_entry(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
        )
        assert len(messages) >= 1

    def test_message_has_role_user(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
        )
        assert messages[0]["role"] == "user"

    def test_message_content_is_nonempty(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
        )
        assert len(messages[0]["content"]) > 0

    def test_invalid_scope_raises_value_error(self, mock_model: ModelInfo):
        with pytest.raises(ValueError, match="Invalid scope"):
            format_scour_prompt(
                model=mock_model,
                target="/some/path",
                scope="wandering",
            )

    def test_invalid_scope_mentions_valid_scopes(self, mock_model: ModelInfo):
        with pytest.raises(ValueError) as exc_info:
            format_scour_prompt(
                model=mock_model,
                target="/some/path",
                scope="bogus",
            )
        error_msg = str(exc_info.value)
        assert "bogus" in error_msg

    def test_introspection_scope_uses_introspection_template(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
        )
        content = messages[0]["content"]
        assert "introspection" in content.lower()
        assert "Introspection" in content

    def test_external_scope_uses_external_template(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="external",
        )
        content = messages[0]["content"]
        assert "external" in content.lower()
        assert "External" in content

    def test_tensor_scope_uses_tensor_template(
        self, mock_model: ModelInfo, cairn_dir: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target="T0*",
            scope="tensor",
            cairn_dir=cairn_dir,
        )
        content = messages[0]["content"]
        assert "tensor" in content.lower()
        assert "Tensor" in content

    def test_tensor_scope_requires_cairn_dir(self, mock_model: ModelInfo):
        with pytest.raises(ValueError, match="cairn_dir is required"):
            format_scour_prompt(
                model=mock_model,
                target="T0*",
                scope="tensor",
                cairn_dir=None,
            )

    def test_nonexistent_target_raises_file_not_found_for_introspection(
        self, mock_model: ModelInfo
    ):
        with pytest.raises(FileNotFoundError, match="Target not found"):
            format_scour_prompt(
                model=mock_model,
                target="/absolutely/does/not/exist/ever",
                scope="introspection",
            )

    def test_nonexistent_target_raises_file_not_found_for_external(
        self, mock_model: ModelInfo
    ):
        with pytest.raises(FileNotFoundError, match="Target not found"):
            format_scour_prompt(
                model=mock_model,
                target="/absolutely/does/not/exist/ever",
                scope="external",
            )

    def test_tensor_scope_does_not_raise_for_nonexistent_target(
        self, mock_model: ModelInfo, cairn_dir: Path
    ):
        """Tensor scope searches in cairn_dir, so a non-matching target
        does not raise FileNotFoundError — it just yields no matches."""
        system, messages = format_scour_prompt(
            model=mock_model,
            target="TXXX_nonexistent",
            scope="tensor",
            cairn_dir=cairn_dir,
        )
        content = messages[0]["content"]
        assert "no matching tensors found" in content

    def test_model_id_appears_in_user_prompt(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
        )
        assert "test/mock-model-7b" in messages[0]["content"]

    def test_model_name_appears_in_user_prompt(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
        )
        assert "Mock Model 7B" in messages[0]["content"]

    def test_cost_appears_in_user_prompt(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
        )
        content = messages[0]["content"]
        # Cost is prompt_cost + completion_cost = 0.10 + 0.20 = 0.30
        assert "0.3000" in content

    def test_run_number_appears_in_user_prompt(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
            run_number=42,
        )
        assert "#42" in messages[0]["content"]

    def test_target_path_appears_in_user_prompt(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
        )
        assert str(sample_file) in messages[0]["content"]

    def test_file_contents_included_in_prompt(
        self, mock_model: ModelInfo, sample_file: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_file),
            scope="introspection",
        )
        content = messages[0]["content"]
        assert "def hello():" in content
        assert "return 'world'" in content

    def test_directory_target_includes_file_contents(
        self, mock_model: ModelInfo, sample_dir: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target=str(sample_dir),
            scope="introspection",
        )
        content = messages[0]["content"]
        # At least some files from the directory should appear
        assert "```" in content

    def test_tensor_scope_includes_tensor_content(
        self, mock_model: ModelInfo, cairn_dir: Path
    ):
        _, messages = format_scour_prompt(
            model=mock_model,
            target="T0*",
            scope="tensor",
            cairn_dir=cairn_dir,
        )
        content = messages[0]["content"]
        assert "T0: The Seed" in content
        assert "tensor zero" in content


# ── _read_target_contents ────────────────────────────────────────────


class TestReadTargetContents:
    """Tests for the filesystem target reader."""

    def test_returns_list_of_tuples(self, sample_file: Path):
        result = _read_target_contents(sample_file)
        assert isinstance(result, list)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in result)

    def test_single_file_returns_that_file(self, sample_file: Path):
        result = _read_target_contents(sample_file)
        assert len(result) == 1
        path, content = result[0]
        assert path == sample_file
        assert "def hello():" in content

    def test_directory_returns_sample_of_files(self, sample_dir: Path):
        result = _read_target_contents(sample_dir)
        assert len(result) > 0
        # All results should be from within the sample directory
        for path, content in result:
            assert str(path).startswith(str(sample_dir))
            assert isinstance(content, str)

    def test_nonexistent_path_returns_empty_list(self, tmp_path: Path):
        bogus = tmp_path / "does_not_exist.py"
        result = _read_target_contents(bogus)
        assert result == []

    def test_respects_max_lines_per_file_truncation(self, tmp_path: Path):
        f = tmp_path / "long_file.py"
        lines = [f"line_{i}" for i in range(500)]
        f.write_text("\n".join(lines), encoding="utf-8")

        result = _read_target_contents(f, max_lines_per_file=10)
        assert len(result) == 1
        _, content = result[0]
        # Should contain the first 10 lines
        assert "line_0" in content
        assert "line_9" in content
        # Should NOT contain lines beyond the limit
        assert "line_10" not in content.split("...")[0] if "..." in content else True
        # Should indicate truncation
        assert "truncated" in content

    def test_truncation_message_includes_remaining_count(self, tmp_path: Path):
        f = tmp_path / "long_file.py"
        lines = [f"line_{i}" for i in range(50)]
        f.write_text("\n".join(lines), encoding="utf-8")

        result = _read_target_contents(f, max_lines_per_file=20)
        _, content = result[0]
        # 50 lines, limited to 20, so 30 more lines truncated
        assert "30 more lines truncated" in content

    def test_directory_respects_max_files_limit(self, tmp_path: Path):
        d = tmp_path / "many_files"
        d.mkdir()
        for i in range(25):
            (d / f"file_{i:02d}.py").write_text(f"# file {i}\n", encoding="utf-8")

        result = _read_target_contents(d, max_files=5)
        assert len(result) <= 5

    def test_skips_pycache_directories(self, tmp_path: Path):
        d = tmp_path / "with_cache"
        d.mkdir()
        (d / "good.py").write_text("# good\n", encoding="utf-8")
        pycache = d / "__pycache__"
        pycache.mkdir()
        (pycache / "cached.py").write_text("# cached\n", encoding="utf-8")

        result = _read_target_contents(d)
        paths = [str(p) for p, _ in result]
        assert all("__pycache__" not in p for p in paths)

    def test_skips_git_directories(self, tmp_path: Path):
        d = tmp_path / "with_git"
        d.mkdir()
        (d / "good.py").write_text("# good\n", encoding="utf-8")
        gitdir = d / ".git"
        gitdir.mkdir()
        (gitdir / "config.txt").write_text("# git config\n", encoding="utf-8")

        result = _read_target_contents(d)
        paths = [str(p) for p, _ in result]
        assert all(".git" not in Path(p).parts for p in paths)

    def test_binary_file_returns_empty_list(self, tmp_path: Path):
        f = tmp_path / "binary.py"
        f.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")

        # Binary files will likely cause UnicodeDecodeError, returning []
        result = _read_target_contents(f)
        assert result == []

    def test_empty_directory_returns_empty_list(self, tmp_path: Path):
        d = tmp_path / "empty_dir"
        d.mkdir()

        result = _read_target_contents(d)
        assert result == []

    def test_file_content_is_string(self, sample_file: Path):
        result = _read_target_contents(sample_file)
        for _, content in result:
            assert isinstance(content, str)

    def test_path_in_result_is_path_object(self, sample_file: Path):
        result = _read_target_contents(sample_file)
        for path, _ in result:
            assert isinstance(path, Path)


# ── _read_tensor_contents ────────────────────────────────────────────


class TestReadTensorContents:
    """Tests for the cairn tensor reader."""

    def test_finds_tensor_by_exact_filename(self, cairn_dir: Path):
        result = _read_tensor_contents("T0_20260101_seed.md", cairn_dir)
        assert len(result) == 1
        path, content = result[0]
        assert path.name == "T0_20260101_seed.md"
        assert "T0: The Seed" in content

    def test_finds_tensor_by_glob_pattern(self, cairn_dir: Path):
        result = _read_tensor_contents("T1*", cairn_dir)
        assert len(result) >= 1
        # T1 and T15 both match T1*
        names = {p.name for p, _ in result}
        assert "T1_20260102_thread.md" in names

    def test_finds_multiple_tensors_by_glob(self, cairn_dir: Path):
        result = _read_tensor_contents("T*", cairn_dir)
        # Should find T0, T1, T15 at minimum
        assert len(result) >= 3

    def test_returns_empty_list_for_nonmatching_pattern(self, cairn_dir: Path):
        result = _read_tensor_contents("ZZZZ_nonexistent*", cairn_dir)
        assert result == []

    def test_finds_tensor_by_prefix_without_glob(self, cairn_dir: Path):
        """The function tries target, then target.md, then target* as prefix."""
        result = _read_tensor_contents("T15", cairn_dir)
        assert len(result) >= 1
        names = {p.name for p, _ in result}
        assert "T15_20260210_scourer.md" in names

    def test_absolute_path_read_directly(self, cairn_dir: Path):
        target = str(cairn_dir / "T0_20260101_seed.md")
        result = _read_tensor_contents(target, cairn_dir)
        assert len(result) == 1
        assert "T0: The Seed" in result[0][1]

    def test_returns_list_of_tuples(self, cairn_dir: Path):
        result = _read_tensor_contents("T0*", cairn_dir)
        assert isinstance(result, list)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in result)

    def test_content_is_string(self, cairn_dir: Path):
        result = _read_tensor_contents("T0*", cairn_dir)
        for _, content in result:
            assert isinstance(content, str)

    def test_respects_max_lines_per_file(self, tmp_path: Path):
        cairn = tmp_path / "long_cairn"
        cairn.mkdir()
        long_lines = [f"tensor line {i}" for i in range(500)]
        (cairn / "T99_20260101_long.md").write_text(
            "\n".join(long_lines), encoding="utf-8"
        )

        result = _read_tensor_contents("T99*", cairn, max_lines_per_file=10)
        assert len(result) == 1
        _, content = result[0]
        assert "tensor line 0" in content
        assert "tensor line 9" in content
        assert "truncated" in content

    def test_skips_directories_in_glob_results(self, cairn_dir: Path):
        # Create a directory that matches the glob
        (cairn_dir / "T_directory").mkdir()
        result = _read_tensor_contents("T*", cairn_dir)
        # All results should be files, not directories
        for path, _ in result:
            assert path.is_file()

    def test_empty_cairn_returns_empty(self, tmp_path: Path):
        empty_cairn = tmp_path / "empty_cairn"
        empty_cairn.mkdir()
        result = _read_tensor_contents("T*", empty_cairn)
        assert result == []
