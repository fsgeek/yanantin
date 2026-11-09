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


# ---- macOS ---------------------------------------------------------------
# The primary is IOPlatformUUID (hardware) plus the APFS Data volume's UUID (the
# namespace /Users lives on), so a second installation on the same Mac is a
# different provider (Codex finding 2). The "darwin:" scope keeps it from ever
# equalling a Linux machine-id (finding 4).

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_DARWIN_PRIMARY = re.compile(rf"^darwin:({_UUID}):({_UUID})$")


def valid_primary(text: str) -> bool:
    """A Linux machine-id, or a macOS darwin:<platform>:<data volume> primary
    with neither half a placeholder."""
    if valid_machine_id(text):
        return True
    match = _DARWIN_PRIMARY.match(text)
    return bool(match) and all(_valid_uuid(part) for part in match.groups())


def _run(cmd: list[str]) -> tuple[int, str]:
    import subprocess

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)
    return proc.returncode, proc.stdout


def _ioreg(run) -> tuple[dict, str | None]:
    code, out = run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"])
    if code != 0:
        return {}, f"ioreg exited {code}"
    return dict(re.findall(r'"(IOPlatform\w+)" = "([^"]*)"', out)), None


def _data_volume_uuid(run) -> tuple[str | None, str | None]:
    import plistlib

    code, out = run(["diskutil", "info", "-plist", "/System/Volumes/Data"])
    if code != 0:
        return None, f"diskutil exited {code}"
    try:
        return plistlib.loads(out.encode()).get("VolumeUUID"), None
    except Exception as e:  # noqa: BLE001 - a malformed plist is recorded, not raised
        return None, f"unparseable plist: {e}"


def darwin_primary(*, run=_run) -> str:
    """darwin:<IOPlatformUUID>:<Data volume UUID>, lowercased, or refuse."""
    platform, detail = _ioreg(run)
    volume, vdetail = _data_volume_uuid(run)
    uuid = platform.get("IOPlatformUUID")
    if not uuid or not volume:
        raise RuntimeError(
            f"no macOS primary (IOPlatformUUID: {uuid or detail}, Data volume UUID: {volume or vdetail}); "
            "yanantin will not guess an identity")
    primary = f"darwin:{uuid.lower()}:{volume.lower()}"
    if not valid_primary(primary):
        raise RuntimeError(f"invalid macOS primary {primary!r}")
    return primary


def darwin_identity_evidence(*, run=_run, hostname: str | None = None) -> list[dict]:
    """Every macOS identifier yanantin reads, as observations."""
    import socket

    platform, detail = _ioreg(run)
    out = []
    for key, name in (("IOPlatformUUID", "io_platform_uuid"), ("IOPlatformSerialNumber", "platform_serial")):
        value = platform.get(key)
        status = "unreadable" if detail else ("ok" if value else "absent")
        if value and key == "IOPlatformUUID" and not _valid_uuid(value.lower()):
            status = "invalid"
        out.append(_observation(name, "ioreg -rd1 -c IOPlatformExpertDevice", status, value, detail))
    volume, vdetail = _data_volume_uuid(run)
    out.append(_observation("data_volume_uuid", "diskutil info -plist /System/Volumes/Data",
                            "unreadable" if vdetail else ("ok" if volume else "absent"), volume, vdetail))
    code, ifconfig = run(["ifconfig"])
    macs = sorted(set(re.findall(r"^\s+ether ([0-9a-f:]{17})", ifconfig, re.M))) if code == 0 else []
    out.append(_observation("mac_addresses", "ifconfig", "ok" if macs else ("absent" if code == 0 else "unreadable"),
                            ",".join(macs) or None, None if code == 0 else f"ifconfig exited {code}"))
    name = hostname if hostname is not None else socket.gethostname()
    out.append(_observation("hostname", "socket.gethostname()", "ok" if name else "absent", name or None))
    code, sw = run(["sw_vers"])
    out.append(_observation("sw_vers", "sw_vers", "ok" if code == 0 and sw.strip() else "unreadable",
                            sw.strip() or None, None if code == 0 else f"sw_vers exited {code}"))
    return out
