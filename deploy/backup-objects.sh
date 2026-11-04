#!/usr/bin/env bash
# Nightly dump of arango-objects (yanantin's file index, port 8532), copied to
# wam-nuc. Same pattern as hamutay/deploy/backup-arango.sh, which covers only the
# 8529 server.
#
# Why: the file index moved to its own server on 2026-10-28 and nothing backed it
# up. On 2026-11-04 it held 18.6M objects, including ~454k that are the only
# record of files since deleted (copied over from apacheta before that copy was
# dropped).
#
# Each run: live counts -> arangodump inside the container -> copy out -> sha256
# manifest -> rsync to wam-nuc -> verify the remote manifest -> prune -> one JSON
# status line in backup-log.jsonl (here and on wam-nuc). Any failure exits non-zero.
set -euo pipefail

CONTAINER="${CONTAINER:-arango-objects}"
HOST_PORT="${HOST_PORT:-8532}"
LOCAL_ROOT="${LOCAL_ROOT:-/home/tony/backups/arango-objects}"
REMOTE="${REMOTE:-wam-nuc}"
REMOTE_ROOT="${REMOTE_ROOT:-backups/arango-objects}"
KEEP_LOCAL="${KEEP_LOCAL:-2}"    # this disk is 89% full (2026-11-04)
KEEP_REMOTE="${KEEP_REMOTE:-7}"
ROOT_PW_FILE="${ROOT_PW_FILE:-/home/tony/.yanantin/config/secrets/arango-objects-root}"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$LOCAL_ROOT/$TS"
LOG="$LOCAL_ROOT/backup-log.jsonl"
STAGE="start"
mkdir -p "$LOCAL_ROOT"

status() {  # status <ok|failed> <stage> [extra-json-fields]
  local line
  line="{\"run\":\"$TS\",\"status\":\"$1\",\"stage\":\"$2\",\"finished\":\"$(date -u +%FT%TZ)\"${3:+,$3}}"
  echo "$line" >> "$LOG"
  echo "$line"
}
trap 'status failed "$STAGE"; exit 1' ERR

# Credentials: the root password file. Never printed, never on a command line.
STAGE="credentials"
CONF="$(mktemp)"; chmod 600 "$CONF"
trap 'rm -f "$CONF"' EXIT
python3 - "$ROOT_PW_FILE" "$CONF" <<'EOF'
import sys
pw = open(sys.argv[1]).read().strip()
# Inside the container the server listens on 8529; the host maps it to 8532.
open(sys.argv[2], "w").write(f"[server]\nendpoint = tcp://127.0.0.1:8529\nusername = root\npassword = {pw}\n")
EOF

STAGE="counts"
mkdir -p "$OUT"
python3 - "$ROOT_PW_FILE" "$HOST_PORT" "$OUT/live-counts.json" <<'EOF'
import base64, json, sys, urllib.request
pw = open(sys.argv[1]).read().strip()
auth = "Basic " + base64.b64encode(f"root:{pw}".encode()).decode()
def q(p):
    r = urllib.request.Request(f"http://127.0.0.1:{sys.argv[2]}" + p); r.add_header("Authorization", auth)
    return json.load(urllib.request.urlopen(r, timeout=60))
counts = {}
for db in q("/_api/database")["result"]:
    counts[db] = {col["name"]: q(f"/_db/{db}/_api/collection/{col['name']}/count")["count"]
                  for col in q(f"/_db/{db}/_api/collection?excludeSystem=true")["result"]}
json.dump(counts, open(sys.argv[3], "w"), indent=1, sort_keys=True)
EOF

STAGE="dump"
docker cp "$CONF" "$CONTAINER:/tmp/backup-arango.conf"
docker exec "$CONTAINER" sh -c "rm -rf /tmp/backup-dump && arangodump --configuration /tmp/backup-arango.conf \
  --all-databases true --output-directory /tmp/backup-dump --compress-output true --threads 4 \
  --overwrite true > /tmp/backup-dump.log 2>&1; rc=\$?; rm -f /tmp/backup-arango.conf; exit \$rc"
docker cp "$CONTAINER:/tmp/backup-dump/." "$OUT/dump/"
docker cp "$CONTAINER:/tmp/backup-dump.log" "$OUT/arangodump.log"
docker exec "$CONTAINER" rm -rf /tmp/backup-dump /tmp/backup-dump.log

STAGE="manifest"
( cd "$OUT" && find dump -type f -print0 | sort -z | xargs -0 sha256sum > MANIFEST.sha256 )
SIZE="$(du -sb "$OUT" | cut -f1)"
FILES="$(wc -l < "$OUT/MANIFEST.sha256")"

STAGE="copy"
ssh -o BatchMode=yes "$REMOTE" "mkdir -p $REMOTE_ROOT"
rsync -a "$OUT" "$REMOTE:$REMOTE_ROOT/"

STAGE="verify-remote"
ssh -o BatchMode=yes "$REMOTE" "cd $REMOTE_ROOT/$TS && sha256sum --quiet -c MANIFEST.sha256"

STAGE="prune"
ls -1d "$LOCAL_ROOT"/20*Z 2>/dev/null | sort | head -n -"$KEEP_LOCAL" | xargs -r rm -rf
ssh -o BatchMode=yes "$REMOTE" "ls -1d $REMOTE_ROOT/20*Z 2>/dev/null | sort | head -n -$KEEP_REMOTE | xargs -r rm -rf"

STAGE="done"
status ok done "\"bytes\":$SIZE,\"files\":$FILES,\"remote\":\"$REMOTE:$REMOTE_ROOT/$TS\""
scp -q "$LOG" "$REMOTE:$REMOTE_ROOT/backup-log.jsonl"
