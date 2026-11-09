"""Linux identity evidence: every identifier offered, each with how it was read
and a status, never a silent fallback (docs/design-machine-identity-evidence.md,
"Evidence: what, how carried, how stored")."""

from yanantin.machine.evidence import linux_identity_evidence

STATUSES = {"ok", "absent", "unsupported", "unreadable", "invalid"}


def _by_name(observations):
    assert all(set(o) == {"name", "read_from", "status", "value", "detail"} for o in observations)
    assert all(o["status"] in STATUSES for o in observations)
    return {o["name"]: o for o in observations}


def _root(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    return tmp_path


def test_a_normal_machine(tmp_path):
    root = _root(tmp_path, {
        "etc/machine-id": "0a1b2c3d4e5f60718293a4b5c6d7e8f9\n",
        "sys/class/dmi/id/product_uuid": "4c4c4544-0042-3510-8051-b4c04f4e4a32\n",
        "sys/class/net/eth0/address": "00:15:5d:aa:bb:cc\n",
        "sys/class/net/lo/address": "00:00:00:00:00:00\n",
        "etc/os-release": 'PRETTY_NAME="Ubuntu 24.04.5 LTS"\n',
    })
    ev = _by_name(linux_identity_evidence(root=root, hostname="wam-desktop"))
    assert ev["machine_id"]["status"] == "ok" and ev["machine_id"]["value"] == "0a1b2c3d4e5f60718293a4b5c6d7e8f9"
    assert ev["machine_id"]["read_from"] == "/etc/machine-id"
    assert ev["product_uuid"]["status"] == "ok"
    assert ev["mac_addresses"]["value"] == "00:15:5d:aa:bb:cc"  # loopback's zeros are not a MAC
    assert ev["hostname"]["value"] == "wam-desktop"
    assert "Ubuntu 24.04.5" in ev["os_release"]["value"]


def test_missing_and_refused_are_different(tmp_path):
    root = _root(tmp_path, {"sys/class/dmi/id/product_uuid": "x"})
    (root / "sys/class/dmi/id/product_uuid").chmod(0)
    ev = _by_name(linux_identity_evidence(root=root, hostname="h"))
    assert ev["machine_id"]["status"] == "absent"
    assert ev["product_uuid"]["status"] in ("unreadable", "ok")  # root can read anything
    if ev["product_uuid"]["status"] == "unreadable":
        assert ev["product_uuid"]["value"] is None and ev["product_uuid"]["detail"]


def test_empty_zero_and_placeholder_values_are_invalid_but_kept(tmp_path):
    root = _root(tmp_path, {
        "etc/machine-id": "\n",
        "sys/class/dmi/id/product_uuid": "03000200-0400-0500-0006-000700080009\n",
    })
    ev = _by_name(linux_identity_evidence(root=root, hostname="h"))
    assert ev["machine_id"]["status"] == "invalid" and ev["machine_id"]["value"] == ""
    assert ev["product_uuid"]["status"] == "invalid"
    assert ev["product_uuid"]["value"] == "03000200-0400-0500-0006-000700080009"
    root2 = _root(tmp_path / "z", {"etc/machine-id": "0" * 32})
    assert _by_name(linux_identity_evidence(root=root2, hostname="h"))["machine_id"]["status"] == "invalid"


def test_non_hex_machine_id_is_invalid(tmp_path):
    root = _root(tmp_path, {"etc/machine-id": "not-a-machine-id"})
    assert _by_name(linux_identity_evidence(root=root, hostname="h"))["machine_id"]["status"] == "invalid"
