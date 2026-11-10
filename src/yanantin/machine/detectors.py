"""Cross-run identity detectors (docs/design-machine-identity-evidence.md,
detectors 2 and 3). They compare a walk's identity evidence with earlier walks
and return findings to record as facts. Nothing here changes an identity: a
person or a later resolver decides what a finding means. A value counts only
when both readings are "ok"; unknown never compares as changed.
"""

from __future__ import annotations

from uuid import NAMESPACE_DNS, uuid5

# Findings are recorded as facts under this provider.
IDENTITY_PROVIDER_ID = uuid5(NAMESPACE_DNS, "yanantin.identity")

# The fields that define a provider; they can't change while the provider stays the same.
_PRIMARY_FIELDS = {"machine_id", "io_platform_uuid", "data_volume_uuid"}
# Firmware identifiers: the only evidence strong enough to link two providers to
# one machine. MACs follow docks and adapters; hostnames are names.
HARDWARE_FIELDS = {"product_uuid", "io_platform_uuid", "platform_serial"}


def _ok(evidence: list[dict]) -> dict[str, str]:
    return {o["name"]: o["value"] for o in evidence if o.get("status") == "ok" and o.get("value") is not None}


def identity_findings(provider: str, evidence: list[dict], previous: dict[str, list[dict]]) -> list[dict]:
    """Findings for this walk. previous maps each provider to the evidence of its
    latest earlier walk.

    - evidence_changed: this provider's evidence differs from its last walk
      (hardware=True when a firmware identifier changed: a clone or a hardware
      change; otherwise a rename or a soft change).
    - same_hardware_new_provider: on a provider's first walk, a firmware
      identifier it shares with another provider (a reinstall or a second
      installation on the same machine).
    """
    now = _ok(evidence)
    findings = []
    if provider in previous:
        before = _ok(previous[provider])
        fields = sorted(name for name in now.keys() & before.keys()
                        if name not in _PRIMARY_FIELDS and now[name] != before[name])
        if fields:
            findings.append({
                "kind": "evidence_changed", "provider": provider, "fields": fields,
                "hardware": any(name in HARDWARE_FIELDS for name in fields),
                "before": {name: before[name] for name in fields},
                "after": {name: now[name] for name in fields},
            })
    else:
        for other, other_evidence in sorted(previous.items()):
            theirs = _ok(other_evidence)
            shared = sorted(name for name in HARDWARE_FIELDS & now.keys() & theirs.keys()
                            if now[name] == theirs[name])
            if shared:
                findings.append({"kind": "same_hardware_new_provider", "provider": provider,
                                 "other_provider": other, "fields": shared})
    return findings
