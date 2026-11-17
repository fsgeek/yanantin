#!/usr/bin/env bash
# Restore check for arango-objects backups. Runs on the RESTORE HOST (ubuntu26-test),
# never on WAM-THREADRIPPER: the point is to prove that a snapshot comes back from
# wam-nuc alone (tupay's verified-backup contract, T10/T11; yanantin's binding is in
# progress).
#
# Why (2026-11-17): the only earlier "restore test" (2026-11-04) restored two
# collections on the same machine. A backup nobody has restored is a hope.
#
# Steps: clear what an earlier crashed check left -> fetch the newest ok snapshot
# from wam-nuc (read-only rrsync key) -> sha256 against its manifest -> restore all
# databases into a throwaway arangod (the production version, static binaries under
# /srv/restore/bin) -> compare every collection's count with the counts taken at
# backup time -> one JSON line in /srv/restore/restore-log.jsonl.
#
# Usage: restore-check-objects.sh [SNAPSHOT]   (default: newest ok in wam-nuc's log)
set -euo pipefail

ROOT=/srv/restore
BIN="$ROOT/bin/arangodb-3.12.9.4"
WORK="$ROOT/check"
LOG="$ROOT/restore-log.jsonl"
R="192.168.111.160"   # wam-nuc
RSYNC_SSH="ssh -i $HOME/.ssh/restore-wam-nuc -o IdentitiesOnly=yes -o BatchMode=yes"
PORT=18529
STAGE=start
SNAP="${1:-}"
STARTED="$(date -u +%FT%TZ)"

mark() {  # mark <restore-checked|restore-failed> <stage> [extra-json]
  local line="{\"snapshot\":\"$SNAP\",\"mark\":\"$1\",\"stage\":\"$2\",\"started\":\"$STARTED\",\"finished\":\"$(date -u +%FT%TZ)\",\"host\":\"$(hostname)\"${3:+,$3}}"
  echo "$line" >> "$LOG"; echo "$line"
}
stop_server() { [ -f "$WORK/arangod.pid" ] && kill "$(cat "$WORK/arangod.pid")" 2>/dev/null && sleep 10 || true; }
trap 'stop_server; mark restore-failed "$STAGE" "${RESULT:+\"result\":$RESULT}"; exit 1' ERR

STAGE=clean
pkill -u "$USER" -f "$BIN/arangod" 2>/dev/null || true   # a crashed earlier check
rm -rf "$WORK"; mkdir -p "$WORK"

STAGE=select
rsync -e "$RSYNC_SSH" -q "$R:backup-log.jsonl" "$WORK/r-backup-log.jsonl"
[ -n "$SNAP" ] || SNAP="$(python3 -c '
import json,sys
ok=[json.loads(l)["run"] for l in open(sys.argv[1]) if json.loads(l).get("status")=="ok"]
print(ok[-1])' "$WORK/r-backup-log.jsonl")"

STAGE=fetch
rsync -e "$RSYNC_SSH" -a "$R:$SNAP/" "$WORK/snap/"

STAGE=manifest
( cd "$WORK/snap" && sha256sum --quiet -c MANIFEST.sha256 )

STAGE=server
mkdir -p "$WORK/db" "$WORK/apps"
ARANGODB_OVERRIDE_DETECTED_TOTAL_MEMORY=8G ICU_DATA="$BIN/arangodb3" "$BIN/arangod" \
  --server.endpoint "tcp://127.0.0.1:$PORT" --server.authentication false \
  --database.directory "$WORK/db" --javascript.app-path "$WORK/apps" \
  --javascript.startup-directory "$BIN/arangodb3/js" --log.file "$WORK/arangod.log" \
  --pid-file "$WORK/arangod.pid" --daemon true --server.telemetrics-api false
for _ in $(seq 1 120); do
  curl -sf "http://127.0.0.1:$PORT/_api/version" >/dev/null && break; sleep 5
done
curl -sf "http://127.0.0.1:$PORT/_api/version" >/dev/null

STAGE=restore
"$BIN/arangorestore" --server.endpoint "tcp://127.0.0.1:$PORT" --server.authentication false \
  --server.password "" --input-directory "$WORK/snap/dump" --all-databases true \
  --create-database true --threads 4 > "$WORK/arangorestore.log" 2>&1

STAGE=counts
RESULT="$(python3 - "$WORK/snap/live-counts.json" "$PORT" <<'EOF'
import json, sys, urllib.request
want = json.load(open(sys.argv[1]))
def q(p): return json.load(urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[2]}" + p, timeout=600))
bad, n, docs = [], 0, 0
for db, cols in want.items():
    for col, expected in cols.items():
        try: got = q(f"/_db/{db}/_api/collection/{col}/count")["count"]
        except Exception as e: got = f"missing ({e})"
        n += 1; docs += expected if isinstance(expected, int) else 0
        if got != expected: bad.append(f"{db}/{col}: {expected} -> {got}")
print(json.dumps({"collections": n, "documents": docs, "mismatches": bad}))
EOF
)"
echo "$RESULT"
stop_server
STAGE=compare
python3 -c 'import json,sys; sys.exit(1 if json.loads(sys.argv[1])["mismatches"] else 0)' "$RESULT"
mark restore-checked done "\"result\":$RESULT"
