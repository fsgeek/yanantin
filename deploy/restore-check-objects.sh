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
stop_server() {  # SIGTERM, then wait for exit: a 31M-document server takes minutes to flush
  local pid; pid="$(cat "$WORK/arangod.pid" 2>/dev/null)" || return 0
  kill "$pid" 2>/dev/null || return 0
  for _ in $(seq 1 180); do kill -0 "$pid" 2>/dev/null || return 0; sleep 5; done
  kill -9 "$pid" 2>/dev/null || true
}
trap 'stop_server; mark restore-failed "$STAGE" "${RESULT:+\"result\":$RESULT}"; exit 1' ERR

STAGE=clean
# A server left by an earlier check: stop it and wait, before deleting its files.
pkill -u "$USER" -f "$BIN/arangod" 2>/dev/null || true
for _ in $(seq 1 180); do pgrep -u "$USER" -f "$BIN/arangod" >/dev/null || break; sleep 5; done
pkill -9 -u "$USER" -f "$BIN/arangod" 2>/dev/null || true
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
# The static binaries look for their data under /usr/share/arangodb3 unless told.
export ICU_DATA="$BIN/arangodb3" ICU_DATA_LEGACY="$BIN/arangodb3" TZ_DATA="$BIN/arangodb3/tzdata"
mkdir -p "$WORK/db" "$WORK/apps"
ARANGODB_OVERRIDE_DETECTED_TOTAL_MEMORY=8G "$BIN/arangod" --configuration none \
  --server.endpoint "tcp://127.0.0.1:$PORT" --server.authentication false \
  --database.directory "$WORK/db" --javascript.app-path "$WORK/apps" \
  --javascript.startup-directory "$BIN/arangodb3/js" --log.file "$WORK/arangod.log" \
  --pid-file "$WORK/arangod.pid" --daemon true --server.telemetrics-api false
for _ in $(seq 1 120); do
  curl -sf "http://127.0.0.1:$PORT/_api/version" >/dev/null && break
  grep -q FATAL "$WORK/arangod.log" 2>/dev/null && break   # don't wait 10 min on a dead server
  sleep 5
done
curl -sf "http://127.0.0.1:$PORT/_api/version" >/dev/null

STAGE=restore
"$BIN/arangorestore" --configuration none --server.endpoint "tcp://127.0.0.1:$PORT" --server.authentication false \
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
# Views: every view in the dump must exist after the restore (definition only;
# populating an ArangoSearch view over 31M documents takes far longer than the check).
import glob, os
views = 0
for vf in glob.glob(os.path.join(os.path.dirname(sys.argv[1]), "dump", "*", "*.view.json")):
    db, name = vf.split(os.sep)[-2], json.load(open(vf)).get("name")
    views += 1
    try: q(f"/_db/{db}/_api/view/{name}")
    except Exception as e: bad.append(f"{db}/view {name}: missing ({e})")
print(json.dumps({"collections": n, "documents": docs, "views": views, "mismatches": bad}))
EOF
)"
echo "$RESULT"
stop_server
STAGE=compare
python3 -c 'import json,sys; sys.exit(1 if json.loads(sys.argv[1])["mismatches"] else 0)' "$RESULT"
mark restore-checked done "\"result\":$RESULT"
