# Objects: an index of what existed, kept fresh incrementally (2026-10-26)

*From yanantin's steward, revised the same day with Tony's guidance. It resolves the tension
between #31 (append-only versioning with `supersedes` edges, chosen in June) and the July
batch landing (one object per machine and path, replaced in place).*

## The contract

**Objects is an index, not storage** (Tony: "One advantage Yanantin and Indaleko had is
they're indices, not storage"). The service promises **"this thing existed at some point"**,
not "this thing exists now".

- A **stale pointer** (an object whose file has since gone or changed) is not a lie. It is
  detected when someone follows it: stat the path on the named machine when resolving. It is
  handled there, by marking it or refreshing it.
- So **deletions are not on the critical path of a re-walk.** Nothing has to notice a missing
  file at walk time for find to be correct under this contract.

## Keeping it fresh: incremental walks, then periodic full scans

1. **Incremental walk** (built in `scripts/walk_corpus.py`): given the previous walk's start,
   keep only entries **modified or changed** (mtime or ctime) after `since − overlap`.
   - mtime alone misses files that arrive with old mtimes: `cp -p`, `tar x`, `rsync -t` and
     moves keep their mtime but get a new ctime.
   - The whole tree is still statted, but only the changes are landed. On wam-nuc, an hour's
     cutoff kept 41,744 of 1,846,329 entries.
   - Parents of new entries are always in the stream (adding, removing or renaming an entry
     changes its directory), so containment edges still resolve.
2. **Each walk is recorded** in its landing fact: root, policy, incremental or full, cutoff,
   start. The next walk takes its cutoff from there. An incremental walk's shape is never
   read as the whole machine's.
3. **Periodic full-scan validation:** a full walk under the same policy is compared with the
   index for that machine, so stale pointers can be found in bulk. Only a complete walk under
   the same policy may judge absence. The 2026-10-26 policy mix (July `--all-names`, then a
   default walk) is the case that rule is for.

## History (what #31 wanted)

Replacing in place overwrites the previous size, mtime and inode. Under "existed at some
point", that history is worth keeping but not urgent. The plan is to write a **change fact**
to the activity stream when a landing changes an object: the old values, the new values, and
the (device, inode) turnover of #31's atomic-rename case. `supersedes` then relates successive
change facts for the same (machine, path). This also makes the walk-and-diff the storage
activity stream Tony described ("scan everything, look for changes"). eBPF, the USN journal or
FSEvents can later feed the same facts faster.

## Eventually: "were there any other copies of it?"

Hand back an object and ask where else it exists, on this machine or another, in any cloud.
That needs a **content identity** (a hash), which a stat walk doesn't have. Size plus name is a
cheap candidate filter. A hash transducer, run on demand over the candidates, confirms a match.
This is the query-driven enrichment pattern (`docs/hypotheses/query-driven-enrichment-small-group-find.md`):
compute the expensive attribute only where a query needs it.

## Declared limits

- Size and mtime miss a content change that preserves both (declared in June).
- **Linux birth time:** ext4, xfs and btrfs keep one (`statx`, `stx_btime`), but Python 3.14's
  `os.stat` doesn't expose it on Linux. That's why `created` is null for every Linux object.
  A `ctypes` call to glibc's `statx` would fill it; its cost per entry is to be measured.
- **atime** is relatime on these mounts: updated at most daily, or when older than mtime/ctime.
  It means "read since the last change, or within a day", not "last read". NTFS behaviour is
  to be checked on the Windows machines before the Windows collector relies on it.
