"""macOS identity (0.3.1 step 4, docs/design-machine-identity-evidence.md): the
primary is IOPlatformUUID plus the APFS Data volume's UUID, scoped by platform so
it can never equal a Linux machine-id; every other identifier is evidence.
Command outputs below are wam-mac's real formats (2026-11-09), serial redacted."""

import pytest

from yanantin.collector.storage.local.linux.collector import default_exclude_paths
from yanantin.machine.evidence import darwin_identity_evidence, darwin_primary, valid_primary

IOREG = ('      "IOPlatformSerialNumber" = "SERIAL123"\n'
         '      "IOPlatformUUID" = "11111111-2222-4333-8444-555555555555"\n')
DISKUTIL = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
	<key>FilesystemType</key><string>apfs</string>
	<key>MountPoint</key><string>/System/Volumes/Data</string>
	<key>VolumeUUID</key><string>66666666-7777-4888-9999-aaaaaaaaaaaa</string>
</dict></plist>"""
IFCONFIG = ("lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384\n"
            "anpi0: flags=8863<UP,BROADCAST> mtu 1500\n\tether 02:00:5e:00:00:02\n"
            "en0: flags=8863<UP,BROADCAST> mtu 1500\n\tether 3c:a6:f6:01:02:03\n")
SW_VERS = "ProductName:\t\tmacOS\nProductVersion:\t\t26.4\nBuildVersion:\t\t25E246\n"
PRIMARY = "darwin:11111111-2222-4333-8444-555555555555:66666666-7777-4888-9999-aaaaaaaaaaaa"


def runner(outputs):
    def run(cmd):
        key = cmd[0]
        if key not in outputs:
            return 127, ""
        return outputs[key]
    return run


REAL = runner({"ioreg": (0, IOREG), "diskutil": (0, DISKUTIL), "ifconfig": (0, IFCONFIG), "sw_vers": (0, SW_VERS)})


def test_the_primary_joins_platform_and_data_volume():
    assert darwin_primary(run=REAL) == PRIMARY


def test_the_primary_is_valid_and_cannot_be_mistaken_for_a_linux_machine_id():
    assert valid_primary(PRIMARY)
    assert valid_primary("0a1b2c3d4e5f60718293a4b5c6d7e8f9")
    assert not valid_primary("darwin:11111111-2222-4333-8444-555555555555:")
    assert not valid_primary("darwin:00000000-0000-0000-0000-000000000000:66666666-7777-4888-9999-aaaaaaaaaaaa")


def test_without_either_half_there_is_no_primary():
    with pytest.raises(RuntimeError, match="will not guess"):
        darwin_primary(run=runner({"diskutil": (0, DISKUTIL)}))
    with pytest.raises(RuntimeError, match="will not guess"):
        darwin_primary(run=runner({"ioreg": (0, IOREG), "diskutil": (1, "")}))


def test_evidence_keeps_every_identifier_with_how_it_was_read():
    ev = {o["name"]: o for o in darwin_identity_evidence(run=REAL, hostname="Tonys-Mac-mini.local")}
    assert ev["io_platform_uuid"]["value"] == "11111111-2222-4333-8444-555555555555"
    assert ev["data_volume_uuid"]["value"] == "66666666-7777-4888-9999-aaaaaaaaaaaa"
    assert ev["platform_serial"]["value"] == "SERIAL123"
    assert ev["mac_addresses"]["value"] == "02:00:5e:00:00:02,3c:a6:f6:01:02:03"
    assert "26.4" in ev["sw_vers"]["value"]
    assert all(o["status"] == "ok" for o in ev.values())
    missing = {o["name"]: o for o in darwin_identity_evidence(run=runner({}), hostname="h")}
    assert missing["io_platform_uuid"]["status"] == "unreadable" and missing["io_platform_uuid"]["value"] is None


def test_the_mac_walk_skips_the_duplicate_and_foreign_volumes():
    mac = default_exclude_paths("darwin")
    # /System/Volumes/Data repeats /Users and the rest through firmlinks;
    # /Volumes is where other drives mount (macOS's /mnt).
    assert {"/System/Volumes", "/Volumes", "/Network"} <= mac
    assert "/Users" not in mac
    assert "/System/Volumes" not in default_exclude_paths("linux")
