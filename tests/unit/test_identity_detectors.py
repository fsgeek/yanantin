"""Cross-run identity detectors (0.3.1 build step 6; docs/design-machine-identity-
evidence.md, detectors 2 and 3). They report, never rewrite: a fact for a person
or a later resolver. Unknown never compares as changed (Codex finding 11)."""

from yanantin.machine.detectors import identity_findings


def obs(name, value, status="ok"):
    return {"name": name, "read_from": "x", "status": status, "value": value, "detail": None}


LINUX_A = [obs("machine_id", "0a1b2c3d4e5f60718293a4b5c6d7e8f9"), obs("product_uuid", "4c4c4544-0000-1111-2222-333333333333"),
           obs("hostname", "box"), obs("mac_addresses", "00:15:5d:aa:bb:cc")]


def test_no_history_no_findings():
    assert identity_findings("p1", LINUX_A, {}) == []


def test_unchanged_evidence_is_quiet():
    assert identity_findings("p1", LINUX_A, {"p1": LINUX_A}) == []


def test_a_hardware_change_under_one_provider_is_reported_with_its_fields():
    moved = [o if o["name"] != "product_uuid" else obs("product_uuid", "4c4c4544-9999-1111-2222-333333333333")
             for o in LINUX_A]
    [f] = identity_findings("p1", moved, {"p1": LINUX_A})
    assert f["kind"] == "evidence_changed" and f["provider"] == "p1"
    assert f["hardware"] is True and f["fields"] == ["product_uuid"]
    assert f["before"]["product_uuid"] != f["after"]["product_uuid"]


def test_soft_changes_are_reported_but_not_as_hardware():
    renamed = [o if o["name"] != "hostname" else obs("hostname", "box2") for o in LINUX_A]
    [f] = identity_findings("p1", renamed, {"p1": LINUX_A})
    assert f["hardware"] is False and f["fields"] == ["hostname"]


def test_unknown_never_compares_as_changed():
    unreadable = [o if o["name"] != "product_uuid" else obs("product_uuid", None, "unreadable") for o in LINUX_A]
    assert identity_findings("p1", unreadable, {"p1": LINUX_A}) == []
    assert identity_findings("p1", LINUX_A, {"p1": unreadable}) == []


def test_the_same_hardware_under_a_new_provider_is_linked():
    reinstalled = [o if o["name"] != "machine_id" else obs("machine_id", "1b2c3d4e5f60718293a4b5c6d7e8f90a")
                   for o in LINUX_A]
    [f] = identity_findings("p2", reinstalled, {"p1": LINUX_A})
    assert f["kind"] == "same_hardware_new_provider"
    assert f["provider"] == "p2" and f["other_provider"] == "p1" and f["fields"] == ["product_uuid"]


def test_macs_alone_do_not_link_providers():
    # MACs move with docks and USB adapters; only firmware identifiers link machines.
    other = [obs("machine_id", "1b2c3d4e5f60718293a4b5c6d7e8f90a"), obs("mac_addresses", "00:15:5d:aa:bb:cc")]
    assert identity_findings("p2", other, {"p1": LINUX_A}) == []
