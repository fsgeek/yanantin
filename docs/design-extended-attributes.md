# Extended attributes and alternate data streams: capture what the OS already recorded

**Status:** design, 2026-11-20, yanantin's steward. **Why:** Tony asked for "take a document and say 'where did
this come from' and it led back to the email from whence it originated" (register:
`tony-where-did-this-come-from`). Both operating systems already record part of that answer, and the walkers
drop it. Every walk keeps every `stat` field (raw_stat), but no extended attributes. That breaks the rule to
capture what the source offers (qhaway: "Capture what's been offered").

## What the OS offers (the provenance-bearing ones; capture is of *all* names)
- **macOS** `com.apple.metadata:kMDItemWhereFroms`: a binary plist of where a file came from (download URL and
  referrer; for attachments saved from Mail, the message's sender and subject, to be confirmed on real files).
  Also `com.apple.quarantine`: the agent that downloaded it, and when.
- **Windows (NTFS)** `Zone.Identifier` alternate data stream: `ZoneId`, and where present `HostUrl` and
  `ReferrerUrl`. It belongs to the Windows walker, not yet built; the same design applies.
- **Linux**: `user.*` xattrs are rare, but some browsers write `user.xdg.origin.url` and
  `user.xdg.referrer.url` on downloads.

## Decisions
1. **Every attribute name is captured**, with its size. Silence would read as "none".
2. **Values ≤ 64 KiB are kept** (base64 for binary; also decoded when the format is known: binary plist for
   WhereFroms, `key=value` text for quarantine and Zone.Identifier). **Larger values** (resource forks,
   Finder data) are kept as size + sha256 only. That's a declared loss, recorded on the record: `value_omitted:
   "over 64 KiB"`.
3. **Remote walks stay on the pinned package.** `scripts/walk_corpus.py` reads attributes per entry and writes a
   side file, `walk-…-xattrs.jsonl.gz` (path, attributes), next to the walk. It never reads file contents, and on
   macOS it reads attributes without materializing dataless files (the same iopolicy already set).
4. **Landing folds the side file in** on WAM-THREADRIPPER, with current code. Each StorageObject's raw record
   gains `xattrs`, and the decoded WhereFroms/quarantine/origin fields become first-class provenance fields that
   find can query.
5. **Incremental walks**: changing an attribute changes ctime, so the existing modified-or-changed filter already
   catches it.

## Tests (written first, from this document)
- A file with no attributes gets `xattrs: {}`, not a missing field.
- A 1 MiB attribute is kept as size + sha256 with `value_omitted`; a 100-byte one is kept whole.
- A real WhereFroms plist decodes to its URL list; a malformed one keeps its raw bytes and records the error.
- Walking a dataless iCloud file reads its attributes and does not download it (checked on wam-mac).
- Landing joins side-file rows to their records by path within the walk; an orphan side row is reported.

## Evidence (2026-11-20, wam-mac `~/Downloads`)
All 7 files carry xattrs: `com.apple.quarantine` (6), `com.apple.metadata:kMDItemWhereFroms` (3; e.g. the Docker
installer's download URLs), `com.apple.metadata:kMDItemDownloadedDate` (3), `com.apple.macl` (3),
`com.apple.provenance` (1), `com.apple.FinderInfo` (1). None of these files came from Mail, so the Mail case
is still unconfirmed.

## Open
- Whether Mail-saved attachments carry the message's sender/subject in WhereFroms (check on real files on
  wam-mac before relying on it).
- Graph-side join: an attachment's hash ↔ a file's hash (same-file links) is the stronger trail; it needs the
  mail collector.
