"""Evidence references: each status from real files and a real git repository.

Spec: docs/superpowers/specs/2026-10-14-evidence-references.md.
"""

import hashlib
import subprocess
from pathlib import Path

import pytest

from yanantin import evidence


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _topic(path, name, evidence_yaml="", extra=""):
    path.write_text(
        f"---\nname: {name}\ntype: project\n{extra}"
        + (f"evidence:\n{evidence_yaml}" if evidence_yaml else "")
        + "---\nbody\n"
    )


@pytest.fixture
def repos(tmp_path):
    root = tmp_path / "repos"
    repo = root / "sib"
    repo.mkdir(parents=True)
    run = lambda *a: subprocess.run(a, cwd=repo, check=True, capture_output=True, text=True)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@example.com")
    run("git", "config", "user.name", "t")
    run("git", "config", "commit.gpgsign", "false")
    (repo / "result.md").write_text("AUTO ends at 1 strand\n")
    run("git", "add", ".")
    run("git", "commit", "-q", "-m", "result")
    commit = run("git", "rev-parse", "HEAD").stdout.strip()
    return root, commit


def test_git_commit_and_file(tmp_path, repos):
    root, commit = repos
    mem = tmp_path / "mem"; mem.mkdir()
    good = _sha(b"AUTO ends at 1 strand\n")
    _topic(mem / "a.md", "a",
           f"  - ref: git:sib@{commit}\n"
           f"  - ref: git:sib@{commit}:result.md\n    sha256: {good}\n"
           f"  - ref: git:sib@{commit}:result.md\n    sha256: {'ab' * 32}\n"
           f"  - ref: git:sib@{'f' * 40}\n"
           f"  - ref: git:sib@{commit}:nope.md\n    sha256: {good}\n"
           f"  - ref: git:absent@{commit}\n"
           f"  - ref: git:sib@{commit}:result.md\n")
    results = evidence.check_dir(mem, repos=root)
    assert [r.status for r in results] == [
        "intact", "intact", "changed", "missing", "missing", "unavailable", "unpinned"]


def test_khipumaq_episode_digest(tmp_path):
    mem = tmp_path / "mem"; mem.mkdir()
    ep = {"user_message": "did you see it?", "response": "yes"}
    digest = _sha("did you see it?\0yes".encode())
    _topic(mem / "a.md", "a",
           f"  - ref: khipumaq:k1\n    sha256: {digest}\n"
           f"  - ref: khipumaq:k1\n    sha256: {'ab' * 32}\n"
           f"  - ref: khipumaq:gone\n    sha256: {digest}\n")
    results = evidence.check_dir(mem, fetch_episode=lambda key: {"k1": ep}.get(key))
    assert [r.status for r in results] == ["intact", "changed", "missing"]


def test_khipumaq_unreachable_is_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("KHIPUMAQ_CONFIG", str(tmp_path / "no-such.ini"))
    mem = tmp_path / "mem"; mem.mkdir()
    _topic(mem / "a.md", "a", f"  - ref: khipumaq:k1\n    sha256: {'ab' * 32}\n")
    [result] = evidence.check_dir(mem)
    assert result.status == "unavailable"


def test_memory_refs_withdrawn_and_superseded(tmp_path):
    mem = tmp_path / "mem"; mem.mkdir()
    (mem / "old.md").write_text("---\nname: old\n---\nclaim\n")
    (mem / "stale.md").write_text("---\nname: stale\n---\nplan\n")
    old = _sha((mem / "old.md").read_bytes())
    stale = _sha((mem / "stale.md").read_bytes())
    _topic(mem / "fix.md", "fix", extra="retracts:\n- old\n")
    _topic(mem / "new.md", "new", extra="supersedes: '[[stale]]'\n")
    _topic(mem / "cites.md", "cites",
           f"  - ref: memory:old\n    sha256: {old}\n"
           f"  - ref: memory:stale\n    sha256: {stale}\n"
           f"  - ref: memory:fix\n    sha256: {'ab' * 32}\n"
           f"  - ref: memory:nobody\n    sha256: {old}\n")
    results = [r for r in evidence.check_dir(mem) if r.file == "cites.md"]
    assert [(r.status, r.note) for r in results] == [
        ("intact", "withdrawn"), ("intact", "superseded"), ("changed", ""), ("missing", "")]


def test_unknown_scheme_and_files_without_evidence(tmp_path):
    mem = tmp_path / "mem"; mem.mkdir()
    (mem / "MEMORY.md").write_text("# index, no frontmatter\n")
    _topic(mem / "plain.md", "plain")
    _topic(mem / "odd.md", "odd", "  - ref: https://example.com/x\n")
    [result] = evidence.check_dir(mem)
    assert (result.file, result.status) == ("odd.md", "unknown")


def test_pin_produces_an_entry_that_checks_intact(tmp_path, repos):
    root, commit = repos
    mem = tmp_path / "mem"; mem.mkdir()
    (mem / "old.md").write_text("---\nname: old\n---\nclaim\n")
    entries = [evidence.pin(f"git:sib@{commit}:result.md", repos=root),
               evidence.pin("memory:old", memory_dir=mem)]
    _topic(mem / "cites.md", "cites", "".join(
        f"  - ref: {e['ref']}\n    sha256: {e['sha256']}\n" for e in entries))
    assert {r.status for r in evidence.check_dir(mem, repos=root)} == {"intact"}


def test_cli_exit_code(tmp_path, repos, capsys):
    root, commit = repos
    mem = tmp_path / "mem"; mem.mkdir()
    _topic(mem / "a.md", "a", f"  - ref: git:sib@{commit}\n")
    assert evidence.main(["check", str(mem), "--repos", str(root)]) == 0
    assert "evidence intact" in capsys.readouterr().out
    _topic(mem / "b.md", "b", f"  - ref: git:sib@{'f' * 40}\n")
    assert evidence.main(["check", str(mem), "--repos", str(root)]) == 1


def test_shared_fixtures_match_expected():
    """tests/fixtures/evidence is offered to qhaway's tests; expected.tsv is the contract."""
    fixtures = Path(__file__).parent.parent / "fixtures" / "evidence"
    expected = [tuple(line.split("\t")) for line in
                (fixtures / "expected.tsv").read_text().splitlines()]
    got = [(r.file, r.ref, r.status, r.note) for r in evidence.check_dir(fixtures)]
    assert got == expected
