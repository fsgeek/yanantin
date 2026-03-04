#!/usr/bin/env python3
"""Pipeline health check and attestation for the Chasqui scout pipeline.

Analyzes three dimensions of pipeline health:

1. **Coverage steering** — Is the watchman working? Are scouts reviewing
   new files, or is the random walk stuck on predecessors.md?

2. **Verification cascades** — Are confused claims generating infinite
   verification loops? The predecessors.md cascade (2990/9494 claims)
   taught us this matters.

3. **Claim distribution** — Is any single file hoarding >25% of all
   claims? That's a sign the gleaner is stuck, not that the file is
   actually 25% of the project.

Writes an attestation to .claude/pipeline_health.json when --attest
is passed. The pre-commit hook reads that file and blocks commits
if the attestation is stale.

Usage:
    uv run python tools/pipeline_health.py          # report only
    uv run python tools/pipeline_health.py --attest # write attestation
    uv run python tools/pipeline_health.py --attest --freshness-hours 48
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Project root: tools/ is one level below
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CAIRN_DIR = PROJECT_ROOT / "docs" / "cairn"
ATTESTATION_PATH = PROJECT_ROOT / ".claude" / "pipeline_health.json"

# Thresholds
MAX_VERIFY_PER_CLAIM = 3
CLAIM_CONCENTRATION_THRESHOLD = 0.25  # 25% of total claims on one file


# ── Coverage check ────────────────────────────────────────────────────

def check_coverage() -> dict:
    """Run the coverage tracker and summarize results.

    Returns a check result dict with status, details, and raw data.
    """
    from yanantin.chasqui.coverage import (
        scan_cairn_coverage,
        coverage_report,
        stalest_files,
        unreviewed_files,
    )

    if not CAIRN_DIR.is_dir():
        return {
            "status": "fail",
            "details": f"Cairn directory does not exist: {CAIRN_DIR}",
            "total_files": 0,
            "unreviewed_count": 0,
            "stalest": [],
            "steering_working": False,
        }

    cov_map = scan_cairn_coverage(CAIRN_DIR)
    report = coverage_report(cov_map, PROJECT_ROOT)
    unreviewed = unreviewed_files(cov_map, PROJECT_ROOT)
    stalest = stalest_files(cov_map, PROJECT_ROOT, n=10)

    total_files = len(report)
    unreviewed_count = len(unreviewed)

    # Coverage steering is working if at least some files have non-None
    # (non-epoch-zero) timestamps — meaning scouts have actually
    # reviewed things and the coverage map reflects it.
    reviewed_count = sum(1 for ts in report.values() if ts is not None)
    steering_working = reviewed_count > 0

    # Status logic:
    # - fail: no coverage data at all (steering broken)
    # - warn: >50% of files unreviewed
    # - pass: steering is working and coverage is reasonable
    if not steering_working:
        status = "fail"
        details = "No files have coverage timestamps. Steering is not working."
    elif unreviewed_count > total_files * 0.5:
        status = "warn"
        details = (
            f"{unreviewed_count}/{total_files} files unreviewed "
            f"({unreviewed_count / total_files:.0%}). "
            f"Steering is working but coverage is thin."
        )
    else:
        status = "pass"
        details = (
            f"{reviewed_count}/{total_files} files have coverage. "
            f"{unreviewed_count} unreviewed."
        )

    # Format stalest for JSON serialization
    stalest_serializable = []
    for path, ts in stalest:
        stalest_serializable.append({
            "path": path,
            "last_reviewed": ts.isoformat() if ts else None,
        })

    return {
        "status": status,
        "details": details,
        "total_files": total_files,
        "unreviewed_count": unreviewed_count,
        "reviewed_count": reviewed_count,
        "stalest": stalest_serializable,
        "steering_working": steering_working,
    }


# ── Verification cascade check ───────────────────────────────────────

def check_verification_cascades() -> dict:
    """Scan for verification report cascades.

    A cascade is when the same (claim_file, claim_by) pair has been
    verified more than MAX_VERIFY_PER_CLAIM times. This means the
    pipeline is wasting API calls re-verifying the same confused claim.

    Returns a check result dict.
    """
    if not CAIRN_DIR.is_dir():
        return {
            "status": "fail",
            "details": "Cairn directory does not exist.",
            "cascading_pairs": [],
            "total_verification_reports": 0,
        }

    # Reuse the coordinator's verification counting logic
    _dispatch_re = re.compile(r"Dispatch:\s*verify", re.IGNORECASE)
    _file_re = re.compile(r"ClaimFile:\s*(.+)")
    _by_re = re.compile(r"ClaimBy:\s*(.+)")

    counts: Counter[tuple[str, str]] = Counter()

    for path in CAIRN_DIR.glob("scout_*.md"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                header = f.read(1500)
        except OSError:
            continue

        if not _dispatch_re.search(header):
            continue

        file_match = _file_re.search(header)
        by_match = _by_re.search(header)
        if file_match and by_match:
            key = (file_match.group(1).strip(), by_match.group(1).strip())
            counts[key] += 1

    total_verifications = sum(counts.values())

    # Find cascading pairs (over the limit)
    cascading = [
        {"claim_file": k[0], "claim_by": k[1], "count": v}
        for k, v in counts.most_common()
        if v > MAX_VERIFY_PER_CLAIM
    ]

    # Top verified pairs (for the report, regardless of cascade status)
    most_verified = [
        {"claim_file": k[0], "claim_by": k[1], "count": v}
        for k, v in counts.most_common(5)
    ]

    if cascading:
        status = "warn"
        details = (
            f"{len(cascading)} claim pairs exceed verification limit "
            f"({MAX_VERIFY_PER_CLAIM}). "
            f"Worst: {cascading[0]['claim_file']} by {cascading[0]['claim_by']} "
            f"({cascading[0]['count']}x)."
        )
    else:
        status = "pass"
        details = (
            f"{total_verifications} verification reports across "
            f"{len(counts)} claim pairs. No cascades."
        )

    return {
        "status": status,
        "details": details,
        "cascading_pairs": cascading,
        "most_verified": most_verified,
        "total_verification_reports": total_verifications,
    }


# ── Claim distribution check ─────────────────────────────────────────

def check_claim_distribution() -> dict:
    """Check whether claims are concentrated on a single file.

    The predecessors.md problem: one file can attract a disproportionate
    share of claims, drowning out coverage of everything else. If any
    file has >25% of all claims, that's a distribution problem.

    Returns a check result dict.
    """
    if not CAIRN_DIR.is_dir():
        return {
            "status": "fail",
            "details": "Cairn directory does not exist.",
            "file_claim_counts": [],
            "total_claims": 0,
        }

    try:
        from yanantin.chasqui.gleaner import extract_claims_from_cairn
    except ImportError as e:
        return {
            "status": "fail",
            "details": f"Cannot import gleaner: {e}",
            "file_claim_counts": [],
            "total_claims": 0,
        }

    # Extract claims from the cairn — use a reasonable limit
    claims = extract_claims_from_cairn(
        CAIRN_DIR, pattern="scout_*.md", max_reports=200
    )

    if not claims:
        return {
            "status": "pass",
            "details": "No claims found in cairn. Nothing to check.",
            "file_claim_counts": [],
            "total_claims": 0,
        }

    # Count claims per primary file reference
    file_counts: Counter[str] = Counter()
    for claim in claims:
        if claim.file_references:
            # Use the first reference, strip line numbers
            ref = claim.file_references[0].rsplit(":", 1)[0]
            file_counts[ref] += 1

    total_with_refs = sum(file_counts.values())
    if total_with_refs == 0:
        return {
            "status": "pass",
            "details": f"{len(claims)} claims but none with file references.",
            "file_claim_counts": [],
            "total_claims": len(claims),
        }

    # Check concentration
    top_file, top_count = file_counts.most_common(1)[0]
    concentration = top_count / total_with_refs

    top_files = [
        {"file": f, "count": c, "pct": round(c / total_with_refs * 100, 1)}
        for f, c in file_counts.most_common(10)
    ]

    if concentration > CLAIM_CONCENTRATION_THRESHOLD:
        status = "warn"
        details = (
            f"`{top_file}` has {top_count}/{total_with_refs} claims "
            f"({concentration:.0%}). Threshold is {CLAIM_CONCENTRATION_THRESHOLD:.0%}."
        )
    else:
        status = "pass"
        details = (
            f"Claims distributed across {len(file_counts)} files. "
            f"Top file: `{top_file}` ({concentration:.0%})."
        )

    return {
        "status": status,
        "details": details,
        "file_claim_counts": top_files,
        "total_claims": len(claims),
        "total_with_refs": total_with_refs,
    }


# ── Report rendering ─────────────────────────────────────────────────

def render_report(
    coverage: dict,
    cascades: dict,
    distribution: dict,
) -> str:
    """Render a human-readable pipeline health report."""
    lines = []
    lines.append("=" * 60)
    lines.append("  Pipeline Health Report")
    lines.append(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 60)
    lines.append("")

    # ── Coverage ──
    status_icon = {"pass": "[PASS]", "warn": "[WARN]", "fail": "[FAIL]"}

    lines.append(f"  Coverage Steering  {status_icon[coverage['status']]}")
    lines.append(f"    {coverage['details']}")
    lines.append(f"    Total .py files: {coverage.get('total_files', 0)}")
    lines.append(f"    Unreviewed: {coverage.get('unreviewed_count', 0)}")
    lines.append(f"    Reviewed: {coverage.get('reviewed_count', 0)}")

    stalest = coverage.get("stalest", [])
    if stalest:
        lines.append("    Top 10 stalest files:")
        for entry in stalest:
            ts = entry["last_reviewed"] or "never"
            lines.append(f"      {entry['path']}")
            lines.append(f"        last reviewed: {ts}")
    lines.append("")

    # ── Cascades ──
    lines.append(f"  Verification Cascades  {status_icon[cascades['status']]}")
    lines.append(f"    {cascades['details']}")
    lines.append(f"    Total verification reports: {cascades.get('total_verification_reports', 0)}")

    cascading = cascades.get("cascading_pairs", [])
    if cascading:
        lines.append(f"    Cascading pairs ({len(cascading)}):")
        for p in cascading[:5]:
            lines.append(f"      {p['claim_file']} by {p['claim_by']}: {p['count']}x")

    most_verified = cascades.get("most_verified", [])
    if most_verified:
        lines.append("    Most-verified pairs:")
        for p in most_verified:
            lines.append(f"      {p['claim_file']} by {p['claim_by']}: {p['count']}x")
    lines.append("")

    # ── Distribution ──
    lines.append(f"  Claim Distribution  {status_icon[distribution['status']]}")
    lines.append(f"    {distribution['details']}")
    lines.append(f"    Total claims: {distribution.get('total_claims', 0)}")

    file_counts = distribution.get("file_claim_counts", [])
    if file_counts:
        lines.append("    Top files by claim count:")
        for f in file_counts[:10]:
            lines.append(f"      {f['file']}: {f['count']} ({f['pct']}%)")
    lines.append("")

    # ── Summary ──
    all_statuses = [coverage["status"], cascades["status"], distribution["status"]]
    if "fail" in all_statuses:
        overall = "UNHEALTHY"
    elif "warn" in all_statuses:
        overall = "NEEDS ATTENTION"
    else:
        overall = "HEALTHY"

    lines.append("-" * 60)
    lines.append(f"  Overall: {overall}")
    lines.append("-" * 60)

    return "\n".join(lines)


# ── Attestation ──────────────────────────────────────────────────────

def write_attestation(
    coverage: dict,
    cascades: dict,
    distribution: dict,
    freshness_hours: int,
) -> Path:
    """Write the attestation file to .claude/pipeline_health.json."""
    now = datetime.now(timezone.utc)

    # Build summary one-liner
    statuses = {
        "coverage": coverage["status"],
        "cascades": cascades["status"],
        "distribution": distribution["status"],
    }
    failing = [k for k, v in statuses.items() if v == "fail"]
    warning = [k for k, v in statuses.items() if v == "warn"]

    if failing:
        summary = f"FAIL: {', '.join(failing)}"
    elif warning:
        summary = f"WARN: {', '.join(warning)}"
    else:
        summary = "All checks pass."

    attestation = {
        "timestamp": now.isoformat(),
        "attested_by": "pipeline_health.py",
        "freshness_hours": freshness_hours,
        "checks": {
            "coverage_steering": {
                "status": coverage["status"],
                "details": coverage["details"],
            },
            "verification_cascade": {
                "status": cascades["status"],
                "details": cascades["details"],
            },
            "claim_distribution": {
                "status": distribution["status"],
                "details": distribution["details"],
            },
        },
        "summary": summary,
    }

    ATTESTATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    ATTESTATION_PATH.write_text(
        json.dumps(attestation, indent=2) + "\n",
        encoding="utf-8",
    )

    return ATTESTATION_PATH


# ── CLI ──────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline health check for the Chasqui scout pipeline.",
    )
    parser.add_argument(
        "--attest",
        action="store_true",
        help="Write attestation to .claude/pipeline_health.json",
    )
    parser.add_argument(
        "--freshness-hours",
        type=int,
        default=72,
        help="Freshness window in hours (default: 72)",
    )
    args = parser.parse_args()

    # Run all checks
    print("Running coverage check...", flush=True)
    coverage = check_coverage()

    print("Running verification cascade check...", flush=True)
    cascades = check_verification_cascades()

    print("Running claim distribution check...", flush=True)
    distribution = check_claim_distribution()

    # Print report
    print()
    print(render_report(coverage, cascades, distribution))

    # Write attestation if requested
    if args.attest:
        path = write_attestation(coverage, cascades, distribution, args.freshness_hours)
        print(f"\nAttestation written to: {path}")
        print(f"Freshness window: {args.freshness_hours} hours")
    else:
        print("\nTo write attestation, run with --attest")


if __name__ == "__main__":
    main()
