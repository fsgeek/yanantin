"""code_fact re-grounding: the loop closing on the substrate's claims about its own code.

The exact failure a prior instance committed three times (2026-06-30): a memory
asserts the code says X; the live tree says Y. `collection_count` re-grounds a
number against the live DB; `code_fact` re-grounds a claim-about-source against
the live working tree. Same feedback edge, different node — the second kind that
forces reground()'s dispatch (extract-on-the-second-instance).

No DB, no mocks: the ground truth is real files in this tree.
"""

from __future__ import annotations

from pathlib import Path

from yanantin.memory.regrounding import CodeFactRegrounding, reground

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_code_fact_stale_when_file_no_longer_contains_expected_string():
    """A frozen claim that a file contains a string it does NOT contain is stale.

    Reproduces the sin: the memory swears regrounding.py still says the old
    single-kind guard 'only "collection_count" is grounded'. Once code_fact
    exists, that guard is gone — so the claim must reground as stale, with the
    frozen expectation preserved beside the live reality.
    """
    claim = {
        "kind": "code_fact",
        "file": "src/yanantin/memory/regrounding.py",
        "expect": "only 'collection_count' is grounded",
        "as_of": "2026-06-30",
    }

    result = reground(claim, root=REPO_ROOT)

    assert isinstance(result, CodeFactRegrounding)
    assert result.stale is True


def test_code_fact_current_when_file_still_contains_expected_string():
    """A frozen claim that still matches the live tree is NOT stale."""
    claim = {
        "kind": "code_fact",
        "file": "src/yanantin/collector/_collector_base.py",
        "expect": "The collector is the only component that touches the raw source",
        "as_of": "2026-06-30",
    }

    result = reground(claim, root=REPO_ROOT)

    assert result.stale is False


def test_code_fact_render_shows_both_frozen_expectation_and_live_reality():
    """Before/after both visible (rule 1) — the render names the drift, not just a bool."""
    claim = {
        "kind": "code_fact",
        "file": "src/yanantin/memory/regrounding.py",
        "expect": "only 'collection_count' is grounded",
        "as_of": "2026-06-30",
    }

    rendered = reground(claim, root=REPO_ROOT).render()

    assert "only 'collection_count' is grounded" in rendered  # the frozen expectation
    assert "regrounding.py" in rendered  # where the drift is
    assert "2026-06-30" in rendered  # when it was frozen


def test_code_fact_missing_file_is_stale_not_crash():
    """A claim about a file that no longer exists is the sharpest drift, not an error.

    'memory says code is at path Y' and path Y is gone is exactly the sibling-repo
    wrong-path failure. It must reground as stale, not raise.
    """
    claim = {
        "kind": "code_fact",
        "file": "src/yanantin/memory/this_path_was_deleted.py",
        "expect": "anything",
        "as_of": "2026-06-30",
    }

    result = reground(claim, root=REPO_ROOT)

    assert result.stale is True
