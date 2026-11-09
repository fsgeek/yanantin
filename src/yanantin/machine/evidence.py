"""Identity evidence: every identifier a machine offers, each with how it was
read and a status (docs/design-machine-identity-evidence.md).

No single identifier is foolproof (Tony, 2026-11-04), so none is trusted alone:
the walker records them all in its manifest, and disagreement between walks is
what reveals a clone, a reinstall or a hardware change. Nothing here falls
back to a guess: a value that can't be read is recorded as such.
"""

from __future__ import annotations

import re
from pathlib import Path

# Values firmware and hypervisors ship when they have no real identifier.
_PLACEHOLDER_UUIDS = {
    "00000000-0000-0000-0000-000000000000",
    "ffffffff-ffff-ffff-ffff-ffffffffffff",
    "03000200-0400-0500-0006-000700080009",
}
_MACHINE_ID = re.compile(r"^[0-9a-f]{32}$")
_ZERO_MAC = "00:00:00:00:00:00"


def _observation(name: str, read_from: str, status: str, value: str | None = None,
                 detail: str | None = None) -> dict:
    return {"name": name, "read_from": read_from, "status": status, "value": value, "detail": detail}


def _read(root: Path, path: str, name: str, valid) -> dict:
    try:
        text = (root / path.lstrip("/")).read_text().strip()
    except FileNotFoundError:
        return _observation(name, path, "absent")
    except OSError as e:
        return _observation(name, path, "unreadable", detail=f"{type(e).__name__}: {e.strerror or e}")
    return _observation(name, path, "ok" if valid(text) else "invalid", text)


def valid_machine_id(text: str) -> bool:
    """32 lowercase hex digits, not all zeros: what systemd writes."""
    return bool(_MACHINE_ID.match(text)) and set(text) != {"0"}


def _valid_uuid(text: str) -> bool:
    return bool(text) and text.lower() not in _PLACEHOLDER_UUIDS


def linux_identity_evidence(*, root: Path = Path("/"), hostname: str | None = None) -> list[dict]:
    """Every Linux identifier yanantin reads, as observations. root and hostname
    are parameters so tests need no particular machine."""
    import socket

    out = [
        _read(root, "/etc/machine-id", "machine_id", valid_machine_id),
        _read(root, "/sys/class/dmi/id/product_uuid", "product_uuid", _valid_uuid),
    ]
    net = root / "sys/class/net"
    macs = []
    for iface in sorted(net.iterdir()) if net.is_dir() else []:
        try:
            mac = (iface / "address").read_text().strip()
        except OSError:
            continue
        if mac and mac != _ZERO_MAC:
            macs.append(mac)
    out.append(_observation("mac_addresses", "/sys/class/net/*/address",
                            "ok" if macs else "absent", ",".join(macs) or None))
    name = hostname if hostname is not None else socket.gethostname()
    out.append(_observation("hostname", "socket.gethostname()", "ok" if name else "absent", name or None))
    out.append(_read(root, "/etc/os-release", "os_release", bool))
    return out
