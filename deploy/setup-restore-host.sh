#!/usr/bin/env bash
# Make HOST yanantin's restore host. Run on WAM-THREADRIPPER, which needs ssh to HOST
# (passwordless sudo there) and to wam-nuc, and the production image locally.
#
#   deploy/setup-restore-host.sh pundit
#
# What it sets up on HOST (all idempotent):
#   - /srv/restore, owned by the user;
#   - a read-only rrsync key to wam-nuc's backups, with wam-nuc's host key pinned
#     from wam-nuc itself, never trusted on first sight;
#   - the production ArangoDB (static binaries copied from the image that runs
#     arango-objects, so the restore uses the same server version);
#   - restore-check-objects.sh and its weekly user timer, with lingering;
#   - curl and age from the distribution.
#
# What it never does: copy the backup decryption key. That key reaches a new
# restore host by a pipe from an existing holder, or from Tony's RoboForm by hand
# (docs/credentials.md). Written 2026-11-19, from the pundit setup done by hand.
set -euo pipefail
HOST="$1"
R=192.168.111.160                       # wam-nuc
IMAGE=arangodb/enterprise:3.12.9.4      # keep in step with deploy/arango-objects-run.sh
VER=3.12.9.4
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

echo "== packages and /srv/restore on $HOST"
ssh "$HOST" "sudo -n apt-get install -y -q curl age rsync >/dev/null && sudo -n mkdir -p /srv/restore/bin && sudo -n chown -R \$USER: /srv/restore"

echo "== read-only key to wam-nuc"
ssh "$HOST" 'mkdir -p ~/.ssh && chmod 700 ~/.ssh && { [ -f ~/.ssh/restore-wam-nuc ] || ssh-keygen -q -t ed25519 -N "" -C "restore-host@$(hostname) (yanantin backups, read-only)" -f ~/.ssh/restore-wam-nuc; } && cat ~/.ssh/restore-wam-nuc.pub' > "$TMP/key.pub"
ssh wam-nuc "grep -qF '$(awk '{print $2}' "$TMP/key.pub")' ~/.ssh/authorized_keys || echo 'command=\"/usr/bin/rrsync -ro /home/tony/backups/arango-objects\",restrict $(cat "$TMP/key.pub")' >> ~/.ssh/authorized_keys"
HOSTKEY="$(ssh wam-nuc 'cat /etc/ssh/ssh_host_ed25519_key.pub' | awk -v r="$R" '{print r" "$1" "$2}')"
ssh "$HOST" "touch ~/.ssh/known_hosts; grep -qF '$HOSTKEY' ~/.ssh/known_hosts || echo '$HOSTKEY' >> ~/.ssh/known_hosts"

echo "== ArangoDB $VER (static, from $IMAGE)"
if ! ssh "$HOST" "[ -x /srv/restore/bin/arangodb-$VER/arangod ]"; then
  cid="$(docker create "$IMAGE")"
  mkdir -p "$TMP/arango"
  for p in /usr/sbin/arangod /usr/bin/arangorestore /usr/share/arangodb3; do docker cp -q "$cid:$p" "$TMP/arango/"; done
  docker rm "$cid" >/dev/null
  tar -C "$TMP/arango" -czf - . | ssh "$HOST" "mkdir -p /srv/restore/bin/arangodb-$VER && tar -C /srv/restore/bin/arangodb-$VER -xzf -"
fi

echo "== restore check and weekly timer"
scp -q "$HERE/restore-check-objects.sh" "$HOST:/srv/restore/bin/"
ssh "$HOST" 'chmod +x /srv/restore/bin/restore-check-objects.sh; mkdir -p ~/.config/systemd/user'
scp -q "$HERE"/systemd/restore-host/yanantin-restore-check{,-azure}.{service,timer} "$HOST:.config/systemd/user/"
ssh "$HOST" 'sudo -n loginctl enable-linger "$USER"; systemctl --user daemon-reload; systemctl --user enable --now yanantin-restore-check.timer yanantin-restore-check-azure.timer'

echo "== checks"
ssh "$HOST" "set -e; /srv/restore/bin/arangodb-$VER/arangod --version | head -1
rsync -e 'ssh -i ~/.ssh/restore-wam-nuc -o IdentitiesOnly=yes -o BatchMode=yes' $R:backup-log.jsonl /tmp/restore-probe.jsonl && echo 'read from wam-nuc: ok'
echo x > /tmp/restore-probe-w; ! rsync -e 'ssh -i ~/.ssh/restore-wam-nuc -o IdentitiesOnly=yes -o BatchMode=yes' /tmp/restore-probe-w $R:x 2>/dev/null && echo 'write to wam-nuc refused: ok'
systemctl --user list-timers --no-pager | grep yanantin-restore-check
[ -f ~/.config/yanantin/backup-age.key ] && echo 'backup key: present' || echo 'backup key: MISSING (pipe it from a holder, or paste from RoboForm)'"
