"""Red-bar test: Governance pipeline structural invariants.

The Chasqui scout pipeline dispatches models to review code, extracts
claims, verifies them, and surfaces consensus. These tests enforce
structural properties that keep the pipeline honest:

1. Corrupted output must be caught before it poisons verdicts
2. Dispatch must be bounded — no unbounded loops or reads
3. Verification reports must carry provenance
4. Claim extraction must deduplicate
5. File selection must be random (not hardcoded)

These exist because:
- Scout 652 produced a corrupted claim that propagated through hundreds
  of verification runs consuming resources without producing signal.
- A model stuck in a repetition loop produced output parsed as CONFIRMED.
- Random sampling with no memory of prior runs re-verified the same claims.

Both the existing guards and the absence of needed guards are checked.
"""

import ast
import inspect
import re
from pathlib import Path

from yanantin.chasqui import coordinator, analyst, gleaner, scorer


# ── Corrupted output detection ──────────────────────────────────────


def test_coordinator_has_degenerate_repetition_detection():
    """The coordinator must detect degenerate repetition before trusting verdicts.

    A model stuck in a loop repeats the same phrase hundreds of times.
    The verdict keyword may appear once at the start, making garbage
    parse as CONFIRMED or DENIED. Without detection, bad verdicts
    enter the cairn as trusted.

    This guard exists because of scout 0983: 4000 tokens of "it does
    mention" repeated, parsed as CONFIRMED.
    """
    source = inspect.getsource(coordinator)

    assert "_is_degenerate_repetition" in source, (
        "coordinator.py must contain _is_degenerate_repetition(). "
        "Without it, a model stuck in a repetition loop can produce "
        "garbage that accidentally contains verdict keywords and gets "
        "accepted as a real verdict."
    )

    # The function must be called in dispatch_verify's verdict parsing
    verify_source = inspect.getsource(coordinator.dispatch_verify)
    assert "_is_degenerate_repetition" in verify_source, (
        "dispatch_verify must call _is_degenerate_repetition() before "
        "parsing the verdict. The check exists but isn't wired into "
        "the verification path."
    )


def test_degenerate_repetition_produces_model_failure_verdict():
    """When degenerate repetition is detected, verdict must be MODEL_FAILURE.

    Not INDETERMINATE — that implies the model tried honestly and couldn't
    tell. MODEL_FAILURE means the output is garbage and shouldn't count.
    """
    verify_source = inspect.getsource(coordinator.dispatch_verify)

    # After detecting degenerate repetition, verdict should be MODEL_FAILURE
    assert "MODEL_FAILURE" in verify_source, (
        "dispatch_verify must set verdict to MODEL_FAILURE when degenerate "
        "repetition is detected. MODEL_FAILURE distinguishes garbage from "
        "genuine uncertainty (INDETERMINATE)."
    )


# ── Garbage filtering ───────────────────────────────────────────────


def test_analyst_has_garbage_filter():
    """The analyst must filter garbage claims before clustering.

    Without garbage filtering, corrupted output from broken models
    contaminates the claim pool. A single garbage-heavy model can
    dominate clusters and dilute genuine cross-model agreement.
    """
    source = inspect.getsource(analyst)

    assert "filter_garbage" in source, (
        "analyst.py must contain filter_garbage(). Without it, corrupted "
        "claims from broken models contaminate the analysis pipeline."
    )

    assert "is_garbage" in source, (
        "analyst.py must contain is_garbage(). Individual claim-level "
        "garbage detection is needed alongside model-level filtering."
    )


def test_analyst_garbage_filter_checks_model_ratio():
    """The garbage filter must exclude entire models with high garbage ratio.

    One bad claim is noise. A model with >50% garbage claims is a broken
    model. Filtering individual claims isn't enough — the model's
    non-garbage output is also suspect.
    """
    filter_source = inspect.getsource(analyst.filter_garbage)

    assert "garbage_ratio" in filter_source or "garbage_threshold" in filter_source, (
        "filter_garbage must check model-level garbage ratio, not just "
        "individual claims. A model with >50% garbage is a broken model "
        "— even its 'good' output is suspect."
    )


# ── Dispatch bounds ─────────────────────────────────────────────────


def test_coordinator_has_retry_limits():
    """The coordinator must have bounded retry limits.

    Unbounded retries on HTTP errors waste resources and can hang the
    dispatch pipeline. The retry mechanism must have a hard limit.
    """
    source = inspect.getsource(coordinator)

    assert "MAX_DISPATCH_RETRIES" in source or "max_retries" in source, (
        "coordinator.py must define a retry limit. Unbounded retries "
        "on HTTP errors can hang the dispatch pipeline."
    )

    # The limit must be a reasonable number (not > 10)
    tree = ast.parse(inspect.getsource(coordinator))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "MAX_DISPATCH_RETRIES":
                    assert isinstance(node.value, ast.Constant), (
                        "MAX_DISPATCH_RETRIES must be a constant, not computed."
                    )
                    assert node.value.value <= 10, (
                        f"MAX_DISPATCH_RETRIES is {node.value.value}. "
                        f"More than 10 retries is excessive — 3-5 is reasonable."
                    )


def test_cairn_reading_has_bounds():
    """Cairn reading functions must have upper bounds on file count.

    The cairn grows without limit (1000+ reports already). Functions
    that scan the cairn must accept a max_reports parameter or similar
    bound. Reading everything unbounded is a resource risk.
    """
    # Check gleaner's extract_claims_from_cairn
    sig = inspect.signature(gleaner.extract_claims_from_cairn)
    assert "max_reports" in sig.parameters, (
        "gleaner.extract_claims_from_cairn must accept max_reports. "
        "The cairn has 1000+ reports and will grow. Unbounded reads "
        "are a resource risk."
    )

    # Check coordinator's dispatch_verify_cairn
    sig = inspect.signature(coordinator.dispatch_verify_cairn)
    assert "max_claims" in sig.parameters, (
        "coordinator.dispatch_verify_cairn must accept max_claims. "
        "Without a bound, every verifiable claim gets a scout dispatched."
    )


# ── Verification provenance ────────────────────────────────────────


def test_verify_dispatch_includes_provenance():
    """Verification scout reports must include dispatch provenance.

    When a scout verifies a claim, the cairn entry must record:
    - What claim was being verified
    - Which file was examined
    - Who made the original claim
    - Which tensor the claim came from

    Without provenance, verification reports are disconnected from
    what they verified. You can't trace a verdict back to its source.
    """
    verify_source = inspect.getsource(coordinator.dispatch_verify)

    # The dispatch_context dict should contain these keys
    for field in ("Claim", "ClaimFile", "ClaimBy", "SourceTensor"):
        assert f'"{field}"' in verify_source or f"'{field}'" in verify_source, (
            f"dispatch_verify must include '{field}' in dispatch_context. "
            f"Without it, verification reports can't be traced back to "
            f"the claim they verified."
        )


# ── Claim deduplication ────────────────────────────────────────────


def test_gleaner_deduplicates_claims():
    """The gleaner must deduplicate claims across reports.

    Without dedup, the same observation from multiple scouts (or even
    the same scout's claim propagated through verify chains) consumes
    multiple verification slots. The same claim verified 50 times
    wastes resources without adding signal.
    """
    source = inspect.getsource(gleaner)

    assert "_deduplicate_claims" in source or "deduplicate" in source.lower(), (
        "gleaner.py must contain deduplication logic. Without it, "
        "the same claim consumes multiple verification slots."
    )

    # The dedup must work at the cairn level, not just within a single report
    cairn_source = inspect.getsource(gleaner.extract_claims_from_cairn)
    assert "dedup" in cairn_source.lower() or "_deduplicate" in cairn_source, (
        "extract_claims_from_cairn must deduplicate across reports, "
        "not just within a single report. Cross-report dedup is what "
        "prevents the same claim from consuming N verification slots."
    )


# ── Random file selection ──────────────────────────────────────────


def test_scout_file_selection_is_random():
    """Scout file selection must use randomness.

    If scouts always see the same files, they produce the same
    observations. The whole point of sending multiple scouts is that
    each gets a different vantage point. Deterministic file selection
    defeats this.
    """
    from yanantin.chasqui import scout as scout_module

    select_source = inspect.getsource(scout_module.select_files_for_scout)

    assert "random" in select_source.lower(), (
        "select_files_for_scout must use randomness (e.g., random.sample). "
        "Deterministic file selection means all scouts see the same files, "
        "defeating the purpose of sending multiple scouts."
    )


# ── Coverage tracking ──────────────────────────────────────────────


def test_scout_dispatch_has_max_claims_or_questions_bound():
    """Investigation and verification dispatch must bound their scope.

    dispatch_investigate and dispatch_verify_cairn both select claims
    to dispatch scouts for. Both must have an upper bound on how many
    scouts get dispatched per invocation. Without bounds, a single
    invocation could dispatch hundreds of scouts.
    """
    investigate_sig = inspect.signature(coordinator.dispatch_investigate)
    assert "max_questions" in investigate_sig.parameters, (
        "dispatch_investigate must accept max_questions to bound "
        "the number of scouts dispatched per invocation."
    )

    verify_cairn_sig = inspect.signature(coordinator.dispatch_verify_cairn)
    assert "max_claims" in verify_cairn_sig.parameters, (
        "dispatch_verify_cairn must accept max_claims to bound "
        "the number of scouts dispatched per invocation."
    )


# ── Structural: modules that must exist ────────────────────────────


def test_governance_modules_exist():
    """The governance pipeline requires these modules to function.

    If any of these are removed or renamed without updating the
    pipeline, dispatch silently breaks or falls back to no filtering.
    """
    from yanantin.chasqui import coordinator as _coord  # noqa: F811
    from yanantin.chasqui import analyst as _analyst  # noqa: F811
    from yanantin.chasqui import gleaner as _gleaner  # noqa: F811
    from yanantin.chasqui import scorer as _scorer  # noqa: F811
    from yanantin.chasqui import scout as _scout  # noqa: F811
    from yanantin.chasqui import model_selector as _selector  # noqa: F841
    from yanantin.chasqui import coverage as _coverage  # noqa: F841

    # Each module must be importable — if this test passes, the
    # governance pipeline's import chain is intact.


# ── Coverage freshness ──────────────────────────────────────────────


def test_coverage_tracker_exists():
    """The coverage tracker must exist as a chasqui module.

    Without coverage tracking, scout dispatch uses uniform random
    file selection. New code can go unreviewed indefinitely while
    popular files get reviewed repeatedly. The watchman sleeps.
    """
    from yanantin.chasqui import coverage
    assert hasattr(coverage, "scan_cairn_coverage"), (
        "coverage module must have scan_cairn_coverage(). "
        "This is the function that scans the cairn to learn which "
        "files have been reviewed and when."
    )
    assert hasattr(coverage, "coverage_weights"), (
        "coverage module must have coverage_weights(). "
        "This computes selection weights so unreviewed files "
        "get maximum priority."
    )


def test_scout_dispatch_supports_coverage_weighting():
    """dispatch_scout must support coverage-weighted file selection.

    The use_coverage parameter controls whether the watchman is active.
    When True (default), file selection is weighted by coverage freshness.
    Files never reviewed start at epoch 0 — maximum priority.
    """
    sig = inspect.signature(coordinator.dispatch_scout)
    assert "use_coverage" in sig.parameters, (
        "dispatch_scout must accept use_coverage parameter. "
        "This is the switch for coverage-weighted file selection."
    )
    # Default should be True — the watchman is on by default
    default = sig.parameters["use_coverage"].default
    assert default is True, (
        f"dispatch_scout use_coverage defaults to {default}. "
        f"It should default to True — the watchman should be on by default."
    )


def test_select_files_accepts_coverage_map():
    """select_files_for_scout must accept a coverage_map parameter.

    This is the integration point: the scout file selection function
    must support weighted selection based on coverage freshness.
    Without this parameter, the watchman can't steer file selection.
    """
    from yanantin.chasqui.scout import select_files_for_scout
    sig = inspect.signature(select_files_for_scout)
    assert "coverage_map" in sig.parameters, (
        "select_files_for_scout must accept coverage_map. "
        "Without it, file selection can't be weighted by freshness."
    )


def test_analyst_separates_original_from_verification_claims():
    """The analyst must distinguish original observations from verification meta-claims.

    Verification claims (scouts reviewing other scouts) are not original
    observations. If they're mixed into the topological insight pool,
    they inflate agreement counts. A claim verified by 5 scouts looks
    like 6 models agreeing, but only 1 model made the original observation.
    """
    source = inspect.getsource(analyst)

    assert "is_verification_meta" in source, (
        "analyst.py must contain is_verification_meta(). Without it, "
        "verification meta-claims (scouts reviewing scouts) are mixed "
        "with original observations, inflating agreement counts."
    )

    assert "verification_ratio" in source, (
        "analyst.py must track verification_ratio per claim group. "
        "This is how topological insights separate original cross-model "
        "agreement from verification echo chambers."
    )
