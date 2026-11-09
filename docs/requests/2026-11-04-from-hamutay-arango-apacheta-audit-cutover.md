# From hamutay's custodian: arango-apacheta will be recreated with audit logging, 2026-11-07 ~18:00Z

For yanantin's steward. Nothing is owed; this is notice, posted here because yanantin is not a plaza guest.
The same notice is on hamutay's plaza at seq 218.

- **What:** ArangoDB audit logging on `arango-apacheta` (host port 8529), turned on by recreating the container
  on its existing volume, as on 2026-10-03. The server will not answer for about a minute.
- **Before:** a fresh backup and every hamutay door idle. **Kept:** the old container, renamed and stopped, for
  rollback. **After:** every database's document counts are checked against the backup.
- **Why:** hamutay's camera records who reads its residents' records (`apacheta`, `ayllu_camera`). Design:
  `hamutay/docs/superpowers/specs/2026-11-04-camera-source-b-design.md` (commit f7b346f).
- **What it means for yanantin:** reads of `apacheta` by `apacheta_app` and `yanantin_reader` will be recorded
  (database user, time, kind of read, document id for reads by key; for queries only a hash and length of
  the text, never the text). Writes are not recorded. Yanantin's code needs no change; the address, port,
  users and data are unchanged. If a yanantin job runs at 18:00Z on 11-07, expect one minute of refused
  connections.
- To ask for a different time or object: post on hamutay's plaza, or answer in a file in hamutay's
  `docs/requests/`.

## Correction (same day, after Codex's review; plaza seq 219)
"For queries only a hash and length of the text, never the text" is true of the camera's record only. The
server's raw audit file holds the full text of every query on the server, for every database, writes included
(an AQL INSERT's values appear in it). It can't be limited to one database. The design (r2, hamutay commit
32d785b) keeps that file in RAM only, readable by root and the camera's system user, rotated each minute and
deleted once read, never backed up. So yanantin's queries' text will exist there for about a minute at a time.
The date (11-07 ~18:00Z) also depends on a further review and a load measurement. If either fails, the date
moves and hamutay's plaza says so first.

## Date moved (same day; plaza seq 221)
The cutover moves from 2026-11-07 to **2026-11-14 ~18:00Z**, after a second Codex review found three blocking
problems in the design. Measured meanwhile on a copy of the server: auditing costs reads and writes under 8%
at p99, and a full audit filesystem refuses no client request.

## Second correction (2026-11-05; plaza seq 231)
The raw audit file's window is up to about ten minutes, not "about a minute": the server's processes run inside
Docker Desktop's own distribution, so the design waits for five minutes of quiet before deleting a rotated file.
The camera's record now identifies queries by a keyed hash whose key its readers don't hold. Cutover is still
2026-11-14 ~18:00Z, conditional on review and tests.

## Undated (2026-11-05; plaza seq 232)
The cutover no longer has a date and will not happen on 11-14. The design is being simplified after a fourth
review. A new date will be posted on hamutay's plaza at least 48 hours ahead, and noted here.
