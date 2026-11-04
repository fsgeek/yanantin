# Machine identity as evidence: one primary per platform, every identifier recorded (2026-11-04)

*Status: REVISING after an independent Codex review (2026-11-04). The review's findings and the
decisions taken in response are in the last section; they override the draft where the two disagree.*

*Original status: draft for review. Builds on the settled spec
`docs/superpowers/specs/2026-06-14-machine-identity-and-filesystem-collector-wiring.md`: identity
(a stable `EntityResolution`) is not config (a per-run snapshot). Nothing here changes that.*

## Why

- macOS has no `/etc/machine-id`. The nightly refresh skips wam-mac (logged, wrongly, as
  "unreachable"). Locally, `machine/base.py:_get_machine_id()` silently falls back to
  `uuid5(hostname.os.arch)`. That is a fingerprint, and renaming the Mac would make it a new machine.
- Indaleko's Mac identity was `uuid4()` per generator run
  (`platforms/mac/MacHardwareInfoGenerator.py:209`), stored in the config JSON as `MachineGuid`
  (line 111) and in the file name. Each re-run produced a new machine.
- The platforms disagree on what "machine" means. Linux `/etc/machine-id` and Windows `MachineGuid`
  belong to an *installation*: new on reinstall, copied by cloning. macOS `IOPlatformUUID` and the
  SMBIOS system UUID belong to *hardware*, though VMs and some boards supply invented or duplicate
  values. Fingerprints (MACs, disk serials) drift with hardware changes. No one source is foolproof
  (Tony, 2026-11-04).

## Decision

1. **One primary identifier per platform. The provider ID is derived from it, as today:
   `uuid5("yanantin.collector.filesystem.{primary}")`.**
   - Linux: `/etc/machine-id`. It stays the primary, because 18.1M objects on four machines are
     keyed through it. Changing it would orphan them.
   - macOS: `IOPlatformUUID` (`ioreg -rd1 -c IOPlatformExpertDevice`). wam-mac's is
     `99E7341C-E143-533C-9C7E-455BCCBCE27D`.
   - Windows: `HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid` (when a Windows collector exists).
   - `identity_type` names the source: `machine.linux`, `machine.darwin`, `machine.windows`.
2. **No silent fallback.** If the primary cannot be read, the collector refuses to run and says why.
   The hostname-based fallback in `_get_machine_id()` is removed. A wrong identity is worse than none,
   because objects written under it are attributed to a machine that doesn't exist.
3. **Every identifier the machine offers is recorded in each config snapshot, as evidence:**
   - machine-id, hardware/SMBIOS UUID (where readable; it is root-only on Linux by default),
     IOPlatformUUID, platform serial (macOS), MachineGuid;
   - hostname, MAC addresses, root/boot disk serials, OS name and version.

   Each value is recorded with how it was read, or why it could not be. This follows Tony's rule to
   capture what's offered.
4. **Disagreement is reported, not resolved.** At walk time, compare the snapshot with the previous
   snapshot for the same primary:
   - same primary, different hardware UUID or different hostname at overlapping times → **possible
     clone**: warn, and record a fact;
   - same hardware UUID, new primary (seen across primaries) → **likely reinstall**: record a fact
     linking the two;
   - same primary, changed disk serials or MACs → **hardware change**: record a fact.

   None of these rewrites an identity. A person (or a later resolver) decides. Old objects stay as
   "existed at some point" under the identity that saw them.

## Remote walks

`scripts/refresh_machines.py` reads the remote primary with `cat /etc/machine-id` and skips the host
when that fails. The remote side should run the same platform-aware reader as the local collector,
so local and remote derive identical provider IDs for the same machine. A failed read is reported as
`"skipped": "no primary identifier"`, not as `"unreachable"`.

## Tests (to write first)

- Linux: the provider ID is unchanged for an existing machine-id (continuity red bar).
- macOS reader: parses the `ioreg` output; with `ioreg` unavailable it refuses rather than falling back.
- No hostname fallback remains anywhere (a red bar over `machine/`).
- Clone detection: two snapshots with one primary and different hardware UUIDs produce a warning fact.
- Remote and local readers agree on this machine.

## Open questions

- Which evidence fields are stable enough to compare, and at what cadence? Comparing every walk
  costs little, but MACs change on laptops (docks, Wi-Fi randomization).
- On Linux, should the walker try `product_uuid` with sudo, or leave it as "unreadable without root"?

## Review (Codex, 2026-11-04) and what changes

Codex reviewed this draft independently. It received the doc and code paths, not conclusions, and
returned 15 findings, several reproduced with read-only probes. The steward re-checked findings 1, 5
and 15 against the source; all three hold. Full review:
`scratchpad/codex-review-identity.txt` (not committed).

**The question changes (findings 1, 2).** A filesystem provider should not identify a *machine*.
Object keys are `uuid5(source:uri)` and landing writes them in `replace` mode
(`core/registration.py:300`). So any two filesystems that share a provider and a path overwrite
each other's records. Clones under one machine-id do this, and so would two installations on one
Mac if the provider were hardware-derived. A warning fact can't undo an overwrite. **Decision:** the
filesystem provider identifies the *storage namespace that was walked*: an installation and its
volume. The machine is evidence attached to it, not its key. On Linux, the existing machine-id
derivation stays as the namespace key for continuity. For a new platform, the key includes a volume
identifier. On macOS that is the APFS Data volume's UUID, the volume `/Users` actually lives on
(finding 13). Collision policy: before landing, if the namespace key's evidence disagrees with the
previous walk (e.g. a different hardware UUID or hostname), the landing refuses and records a fact.
It does not overwrite.

**Decisions taken now:**
- *Continuity is the exact hash input* (finding 3): the raw machine-id string with `NAMESPACE_DNS`,
  for both the `filesystem` and the `machine_config` prefixes. No normalization through `UUID()`.
  A red bar pins today's four provider IDs.
- *Validate the primary* (finding 9): reject empty, malformed and all-zero values, both when read
  locally and when passed in.
- *Bind identity to the walk* (finding 6, an existing bug): refresh rejects a manifest whose
  provider differs from the preflight provider whose cutoff it used. This is fixed before anything
  else.
- *Failure categories* (finding 14): transport failure, no primary identifier, and timeout are
  reported separately. A per-host timeout no longer aborts the remaining hosts.
- *Rollout* (finding 5): remote walks run the PyPI release. The reader, walker and verifier ship
  together as 0.3.1, and refresh pins that version.
- *Typed identities* (finding 4): new platforms' entity keys are scoped by `identity_type`. The
  recorder checks the type when it reuses an entity.

**Still to specify before building** (findings 7, 8, 10, 11, 12):
- where walk-time evidence travels and is stored losslessly, with statuses for absent, unsupported,
  unreadable and invalid observations;
- what happens to any existing hostname-derived identities (inventory first);
- the temporal evidence the clone and reinstall facts need;
- qualifying the platform lifecycle claims above. Systemd can seed machine-id from VM or firmware
  UUIDs, and a sysprepped Windows clone gets a new MachineGuid.
