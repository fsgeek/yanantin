# yanantin's systemd user units

Installed on the WSL that hosts arango-apacheta (WAM-THREADRIPPER), in
`~/.config/systemd/user/`. These are copies; the installed files are the live ones.

- `yanantin-refresh.timer` → `yanantin-refresh.service`: nightly at 04:30 local, after
  hamutay's ~03:15 arango backup. It runs `scripts/refresh_machines.py`, an incremental walk
  of ubuntu24, wam-nuc, wam-mac (skipped when unreachable) and this machine, landed into
  `apacheta.Objects` with the memory guard.

Install or update:

    cp deploy/systemd/yanantin-refresh.* ~/.config/systemd/user/
    systemctl --user daemon-reload && systemctl --user enable --now yanantin-refresh.timer

Results: `journalctl --user -u yanantin-refresh.service`.
