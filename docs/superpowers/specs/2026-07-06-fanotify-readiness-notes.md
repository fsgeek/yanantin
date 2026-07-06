# Scouting: fanotify real-time collector readiness

**Status:** scouting notes, not a design. Forward-looking; NOT part of the
2026-07-05 activity-observation-reduction pour.
**Author:** Yanantin AI, 2026-07-06
**Why this exists:** "does fanotify even work on my dev box" is an hour-losing
environment question. This records the empirical answer so a successor does not
re-derive it, and separates the *real* blockers from the ones I assumed and the
probe disproved.

---

## The question

The reduction spec (`2026-07-05-activity-observation-reduction-design.md`, §8)
says the banding aggregator's design truly earns its keep on a **real-time**
source (fanotify/fs_usage), not on mtime-scan — mtime-scan is batch and can't see
intra-scan churn or provide rename-coherent handles. So: what blocks building the
fanotify real-time monitor?

## What was probed (2026-07-06, this WSL2 box, kernel 6.18)

Direct `ctypes` probe of `fanotify_init`, run as the normal unprivileged user
(`uid=1000`, `CapEff=0`):

```
basic notif class (FAN_CLASS_NOTIF)        FAIL  EPERM
FAN_REPORT_FID        (Linux 5.1+)         OK
FAN_REPORT_DFID_NAME  (Linux 5.9+)         OK
```

**This inverts the naive expectation.** The *classic* fd-returning mode needs
`CAP_SYS_ADMIN` and fails EPERM here. The *modern FID-reporting* modes were
deliberately opened to unprivileged users since 5.1 (reporting an opaque file
handle instead of an openable fd leaks nothing), and they **initialize fine on
this box, unprivileged, today**. My prior belief "WSL2 fanotify is partial / needs
root" was stale — reasoning from old fanotify. The probe corrected it.

## Blockers, tiered by whether they are real

### Tier 1 — NOT blockers (the probe cleared them)

- **API access.** Rich-mode `fanotify_init` succeeds unprivileged. No
  `CAP_SYS_ADMIN` for the FID/NAME path.
- **Kernel / WSL2.** 6.18 supports `FAN_REPORT_DFID_NAME`; it initializes. WSL2 is
  not the wall.
- **Event delivery — VERIFIED, not assumed (2026-07-06).** The earlier draft of
  this note hypothesized WSL2's 9p mount might init+mark fine but deliver an empty
  stream (the classic false-green). **Probed and disproven for this box.** The
  repo is on **ext4** (`/dev/sdd`, per `df -T`; `stat -f` mislabels it ext2/3 —
  trust `df`), not 9p. A second probe (`fanotify_mark` a temp dir under the repo,
  then create/modify/delete a file) **delivered 156 bytes of real event data**.
  init+mark+delivery all work here. NOTE the caveat still holds for `/mnt/c`-style
  9p mounts — those were not tested and 9p historically does not propagate events.
  The repo's own ext4 filesystem is not affected.
- **Rename coherence.** `FAN_MOVED_FROM`/`FAN_MOVED_TO` + `FAN_REPORT_FID` give a
  stable file handle across a move — exactly the "key on the stable handle,
  survives rename" property §4 of the reduction spec wants and mtime-scan cannot
  provide. fanotify is where that claim becomes testable.

### Tier 2 — Real engineering, but bounded

- **No Python fanotify binding.** stdlib has none. Path is `ctypes` against libc
  (as the probe did). The actual work is **parsing the variable-length
  `fanotify_event_metadata` + `fanotify_event_info_fid` byte structs** off the fd:
  nested TLV-ish records, opaque `file_handle` blobs. Fiddly but contained — this
  is the bulk of the collector body.
- **`open_by_handle_at` privilege split.** You get the FID unprivileged, but
  *resolving* it to a path needs `CAP_DAC_READ_SEARCH`. **For the witness this may
  not matter:** the spec says `location` is an opaque collector-minted token the
  witness never resolves. So the fanotify collector can mint
  `fanotify-fid:<handle>` URIs and never resolve them — staying unprivileged — and
  hand resolution to the anchor layer. The spec's opacity principle pays off: the
  privileged step is the one already deferred.

### Tier 3 — The REAL blocker, and it is this repo, not fanotify

- **There is no long-lived collector abstraction in the pipeline.** Verified
  (2026-07-06): `FactRecorderBase.record_facts(envelope) -> int` is stateless
  batch; every existing collector is scan-and-exit (returns an `FsEventBatch`,
  exits). fanotify is the opposite shape — a **long-lived fd you `read()` in a
  loop, forever**. Nothing in the current collector/wrangler/recorder contract is
  a daemon. fanotify cannot be bolted onto a batch pipeline; it forces a
  **long-running collector stage the architecture does not model.**

## Consequence for sequencing

This confirms the reduction spec's ordering as more than "easy source first":

- **mtime-scan first** fits the pipeline that *exists* (batch), and lets the
  banding aggregator be built and falsified **without** also inventing the
  long-running-collector abstraction in the same pour.
- **fanotify is a later pour that pays two costs at once**: the ctypes
  struct-parser (Tier 2) *and* the daemon-collector stage (Tier 3). Sequence it
  **after** the aggregator is green on batch, not tangled into it.

The fanotify *API and event delivery* are not the blocker (both proven working,
unprivileged, on this box's ext4 repo — 2026-07-06). **No VM move is needed;** the
environmental worry was disproven by probe. The **one** remaining blocker is the
long-running-collector abstraction. That is an architecture gap to design
deliberately, not discover mid-pour — and no change of machine fixes it.

## Probe reproduction

The probe was a ~20-line `ctypes` script calling `fanotify_init(flags, O_RDONLY)`
for the three flag sets above and reporting OK / errno. Re-run it on any target
box before assuming fanotify availability — the answer is kernel- and
privilege-dependent and the FID-mode-unprivileged result is not obvious.
```
