"""Accretion guards: the single-instance phase must not foreclose the
multi-instance future.

The standing decision
(pukara/docs/decisions/2026-06-06-single-principal-substrate-standing-decision.md)
defers multi-instance isolation but forbids the single-instance phase from
*foreclosing* it by accretion. That document's thesis: negative requirements
stated in prose erode — only red bars hold the line. So the prohibitions are
installed here as red bars, not described as specs to write later.

Two of the three accretion guards are mechanically expressible and are below.
The third — "no query may be optimized on the single-author assumption" — is
NOT a data/code-shape property a test can assert generally (a query that
assumes one author looks identical to a correct one until a second author
exists); it stays a structural-review obligation in the standing decision, not
faked into a test that can't really check it.

Tracked: yanantin#13. Authored by the Pukara instance 2026-06-06, placed by a
yanantin hand (the cross-fortress write was declined on principle — author
there, place here). Guard 2 was hardened when the tiksi field landed: it is now
an active guard that the field exists, defaults false, and no yanantin-side
agent path asserts verified authorship before yanantin#13 provides an identity
source.
"""

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from tiksi.provenance import ProvenanceEnvelope


# ── Guard 1: principal-shaped fields must remain PRESENT ──────────────
#
# The accretion failure is a future instance "simplifying" the provenance
# envelope by dropping the principal-shaped fields because a single instance
# doesn't need them — quietly foreclosing the multi-instance future. This
# guard asserts the fields that make a record attributable to a distinct
# principal stay on the model. It runs TODAY (the fields exist) and goes red
# the day someone removes one. Structural, no DB needed.

def test_provenance_keeps_principal_shaped_fields():
    """author_instance_id and author_model_family must stay on the envelope.
    Removing them forecloses multi-instance attribution — the exact accretion
    the standing decision forbids. yanantin#13."""
    fields = set(ProvenanceEnvelope.model_fields)
    required_principal_fields = {"author_instance_id", "author_model_family"}
    missing = required_principal_fields - fields
    assert not missing, (
        f"ProvenanceEnvelope dropped principal-shaped field(s): {missing}. "
        "These keep a record attributable to a distinct instance. Removing "
        "them forecloses the multi-instance future (yanantin#13). If this is "
        "a deliberate rebuild, update the standing decision — do not silently "
        "drop the field."
    )


# ── Guard 2: authorship_verified must exist AND default honest ────────
#
# This used to be a strict xfail. The field landed tiksi-side, so the dormant
# guard woke up and is now real. Until yanantin#13 provides a verified identity
# source, the agent-reachable yanantin paths must leave authorship unverified.


def test_authorship_verified_exists_and_defaults_false():
    """The unverified-authorship mark must exist in the DATA and default to
    False — so a self-asserted author claim is honestly marked unverified
    where a future reader sees it, not only in a test. Until an identity
    subsystem (yanantin#13) lands, nothing may flip it to True."""
    assert "authorship_verified" in ProvenanceEnvelope.model_fields, (
        "authorship_verified missing from ProvenanceEnvelope"
    )
    # getattr, not attribute access: the field is dormant-until-built, so a
    # type checker correctly does not know it yet. This probe is the point.
    default = getattr(ProvenanceEnvelope(), "authorship_verified")
    assert default is False, (
        "authorship_verified must default False — verification is earned, "
        "never inherited. yanantin#13."
    )


def test_authorship_verified_default_cannot_be_mutated_true():
    """An agent-created default envelope cannot be flipped to verified after
    construction. yanantin#13 identity may later introduce a verified path, but
    absent that source the default object stays honestly unverified."""
    envelope = ProvenanceEnvelope()

    with pytest.raises(ValidationError):
        envelope.authorship_verified = True

    assert envelope.authorship_verified is False


def test_yanantin_agent_paths_do_not_assert_verified_authorship():
    """No yanantin-side agent path may set authorship_verified=True until a
    verified identity source exists. This is intentionally scoped to in-repo
    code paths; direct tiksi model support for True remains available for the
    future identity subsystem."""
    project_root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []

    for path in sorted((project_root / "src").rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.keyword)
                and node.arg == "authorship_verified"
                and isinstance(node.value, ast.Constant)
                and node.value.value is True
            ):
                offenders.append(f"{path.relative_to(project_root)}:{node.lineno}")
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "authorship_verified"
                        and isinstance(value, ast.Constant)
                        and value.value is True
                    ):
                        offenders.append(
                            f"{path.relative_to(project_root)}:{value.lineno}"
                        )

    assert not offenders, (
        "yanantin code sets authorship_verified=True without a verified "
        f"identity source (yanantin#13): {offenders}"
    )


# ── Guard 3 is NOT here, on purpose ───────────────────────────────────
#
# "No query may be optimized on the single-author assumption" is not a
# data/code-shape property a test can assert generally — a query that assumes
# one author looks identical to a correct query until a second author exists.
# Faking it into a test that can't really check it would be theater. It stays
# a STRUCTURAL-REVIEW obligation in the standing-decision doc. Recorded here so
# a future hand knows the omission is deliberate, not forgotten. If a
# mechanical expression is later found (e.g. a lint flagging queries lacking an
# author/tenant scope once the boundary exists), add it then.
_GUARD_3_IS_A_REVIEW_OBLIGATION_SEE_STANDING_DECISION = True
