"""Accretion guards: the single-instance phase must not foreclose the
multi-instance future.

The standing decision
(pukara/docs/decisions/2026-06-06-single-principal-substrate-standing-decision.md)
defers multi-instance isolation but forbids the single-instance phase from
*foreclosing* it by accretion. That document's thesis: negative requirements
stated in prose erode — only red bars hold the line. So the prohibitions are
installed here as DORMANT red bars, not described as specs to write later. A
spec is still prose; an xfail(strict=True) test is the guard itself, installed
sleeping, with a mechanical wake-up condition.

Two of the three accretion guards are mechanically expressible and are below.
The third — "no query may be optimized on the single-author assumption" — is
NOT a data/code-shape property a test can assert generally (a query that
assumes one author looks identical to a correct one until a second author
exists); it stays a structural-review obligation in the standing decision, not
faked into a test that can't really check it.

Tracked: yanantin#13. Authored by the Pukara instance 2026-06-06, placed by a
yanantin hand (the cross-fortress write was declined on principle — author
there, place here). Verified against live code 2026-06-06: import path,
red_bar suite convention, and both dormant states (Guard 1 passes — the fields
exist; Guard 2 xfails — authorship_verified does not exist yet).
"""

import pytest

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
# xfail(strict=True): the field does not exist yet (specified in the
# GraphBackend contract, unbuilt tiksi-side). The guard is installed DORMANT.
# The day the field is added, this test passes unexpectedly → strict xfail
# flips the suite RED → a human must come make the guard real (assert it can
# never be True without a verified identity source). The wake-up is
# mechanical; nothing relies on a future instance remembering.

@pytest.mark.xfail(
    strict=True,
    reason="authorship_verified not yet on ProvenanceEnvelope (contract, "
    "unbuilt tiksi-side). When added, this xpasses → strict flips suite red "
    "→ make the guard real: forbid True without a verified identity source. "
    "yanantin#13.",
)
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
