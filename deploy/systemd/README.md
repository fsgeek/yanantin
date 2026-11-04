# yanantin's systemd user units

Installed on the WSL that hosts arango-apacheta (WAM-THREADRIPPER), in
`~/.config/systemd/user/`. These are copies; the installed files are the live ones.

- `yanantin-refresh.timer` → `yanantin-refresh.service`: nightly at 04:30 local, after
  hamutay's ~03:15 arango backup. It runs `scripts/refresh_machines.py`, an incremental walk
  of ubuntu24, wam-nuc, gazelle, wam-mac (skipped when unreachable) and this machine, landed into
  `Objects` on arango-objects (port 8532, since 2026-10-28) with the memory guard.
- `yanantin-backup-objects.timer` → `yanantin-backup-objects.service`: nightly at 06:15, after the
  refresh. It runs `deploy/backup-objects.sh`: arangodump of arango-objects, sha256 manifest, rsync to
  wam-nuc:backups/arango-objects, remote verify, keep 2 here and 7 there. hamutay's backup covers
  only the 8529 server, so without this the file index has no backup.

Install or update:

    cp deploy/systemd/yanantin-*.service deploy/systemd/yanantin-*.timer ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now yanantin-refresh.timer yanantin-backup-objects.timer

Results: `journalctl --user -u yanantin-refresh.service` (and `-u yanantin-backup-objects.service`;
the backup also writes one status line per run to `~/backups/arango-objects/backup-log.jsonl`).
