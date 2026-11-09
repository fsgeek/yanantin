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
  *usually* belong to an *installation*: new on a reinstall, copied by naive cloning. Not always: systemd
  can seed machine-id from a VM or firmware UUID, so a reinstall may keep it, and a sysprepped Windows
  clone gets a new MachineGuid (Codex, finding 12). The detectors below rely on none of these as rules. macOS `IOPlatformUUID` and the
  SMBIOS system UUID belong to *hardware*, though VMs and some boards supply invented or duplicate
  values. Fingerprints (MACs, disk serials) drift with hardware changes. No one source is foolproof
  (Tony, 2026-11-04).

## Decision

1. **One primary identifier per platform. The provider ID is derived from it, as today:
   `uuid5("yanantin.collector.filesystem.{primary}")`.**
   - Linux: `/etc/machine-id`. It stays the primary, because 18.1M objects on four machines are
     keyed through it. Changing it would orphan them.
   - macOS: `IOPlatformUUID` (`ioreg -rd1 -c IOPlatformExpertDevice`). wam-mac's is
     `11111111-2222-4333-8444-555555555555`.
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
- ~~where walk-time evidence travels and is stored losslessly~~ — **specified 2026-11-09:** see
  *Evidence: what, how carried, how stored* below;
- ~~what happens to any existing hostname-derived identities (inventory first)~~ — **inventoried
  2026-11-09:** the index holds one legacy identity, `9cb28995` (35,805 objects, walked 2026-06-28).
  It is this WSL under an earlier provider derivation (none of the current formulas reproduce it),
  flagged "for later retirement" in July (commit a67485a1). Its URIs largely duplicate
  `192c0842`'s. The Mac has never landed, so no hostname-fallback identities exist. Lineage to
  record: a fact linking `9cb28995` to `192c0842` as the same machine under an earlier derivation.
  Retirement waits until that link exists, so nothing reads as two machines;
- ~~the temporal evidence the clone and reinstall facts need~~ — **specified 2026-11-09:** see *Detectors* below;
- ~~qualifying the platform lifecycle claims above~~ — done in *Why*.


## Evidence: what, how carried, how stored (specified 2026-11-09)

**What.** At walk start the walker records one observation per identifier the platform might offer:
`{name, read_from, status, value, detail}`.
- `read_from` says how it was read: a file path, a command, or an API.
- `status` is one of:
  - `ok`;
  - `absent`: the platform has the source, but nothing is there (e.g. no `/etc/machine-id`);
  - `unsupported`: this platform doesn't have it (IOPlatformUUID on Linux);
  - `unreadable`: present but refused (e.g. `/sys/class/dmi/id/product_uuid` without root);
  - `invalid`: read, but empty, all zeros, or a known placeholder.
- `value` is the raw text as read, kept for `ok` and `invalid`. `detail` holds the error, if any.

| platform | primary (provider key) | evidence |
|---|---|---|
| Linux | `/etc/machine-id` (unchanged: continuity guard) | product_uuid, MAC addresses, root/boot disk serials, hostname, os-release |
| macOS | IOPlatformUUID + the APFS Data volume's UUID (the namespace `/Users` lives on) | platform serial, hostname, MACs, sw_vers |
| Windows | the walked volume's GUID (`\\?\Volume{…}`) | MachineGuid, SMBIOS UUID, volume serial, hostname, OS build |

**How carried.** The observations go in the walk manifest under `identity_evidence`, beside the
`alias` that refresh adds (2026-11-09). The manifest already lands whole as the walk fact's
`data.walk`, so nothing new is built.

**How stored.** As that fact: append-only, raw strings, no projection. The old machine-config recorder's
string projection (Codex, finding 8) is not used for evidence.

## Detectors (specified 2026-11-09)

All of these record facts, and none rewrites an identity. Unknown never compares as changed: a value
counts only when both readings are `ok` (Codex, finding 11).

1. **Within one refresh run, two aliases yield the same provider.**
   - Hardware evidence equal (product_uuid / IOPlatformUUID / SMBIOS, whichever is `ok` on both): the
     aliases name **one machine**. Walk it once, and record the extra aliases on its fact. This is
     Tony's case: ubuntu18/20/22/24 all point at 192.168.111.150.
   - Hardware evidence differs: a **collision**. Two filesystems would overwrite each other's keys, so
     the second landing is refused (`"failed": "identity_collision"`, naming both aliases), and a fact
     is recorded.
   - Neither side `ok`: refused, as a collision. Better a missing landing than a merged one.
2. **Across runs, the same provider's hardware evidence changes** (both readings `ok`): an
   `evidence_changed` fact naming the fields and the two walks. A human or a later resolver decides
   between a clone and a hardware change. A clone shows up as values alternating across walks.
3. **The same hardware evidence (`ok`) appears under a new provider:** a `same_hardware_new_provider`
   fact linking the two. It points to a likely reinstall or a second installation, and doesn't decide
   which. The legacy `9cb28995` → `192c0842` lineage is recorded the same way, by hand, since that walk
   predates evidence.

## Build order for 0.3.1

1. Linux evidence in the walker's manifest, tested against the continuity guard.
2. Refresh detector 1, the within-run check. This is the only detector that refuses a landing.
3. Validation of the primary: empty, malformed or placeholder values refuse the walk (finding 9).
4. The macOS reader: IOPlatformUUID, the Data volume UUID, the dataless-file policy (`setiopolicy_np`
   materialize-off) and `SF_DATALESS`. Then a first Mac walk, which proves `/Users` coverage
   (finding 13).
5. Release 0.3.1 to PyPI, and pin it in refresh, so remote walks run the new reader (finding 5).
6. Detectors 2 and 3.

The Windows walker is its own design (enumeration first, no recall). See the qhaway references
*Windows walker design facts* and *Cloud placeholders, never recall*.
