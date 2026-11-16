#!/usr/bin/env bash
# Run before the refresh and the backup (ExecStartPre): if arango-objects isn't
# running, start it and wait until it answers.
#
# Why: after the 2026-11-14 reboot it stayed down for 18h, the refresh and backup
# both failed, and the whole repair was one `docker start`. Tony worries any alert
# channel would drown in noise, so the timers repair what they can themselves, and
# the MCP server's health notice reports what they can't.
set -euo pipefail
CONTAINER="${CONTAINER:-arango-objects}"
PORT="${HOST_PORT:-8532}"
WAIT="${WAIT_SECONDS:-600}"

if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" != "true" ]; then
  echo "$CONTAINER was not running ($(docker inspect -f '{{.State.Status}} exit={{.State.ExitCode}} finished={{.State.FinishedAt}}' "$CONTAINER")); starting it"
  docker start "$CONTAINER" >/dev/null
fi
# 401 (no credentials) or 200 means it is serving; 503 means still starting.
for _ in $(seq 1 $((WAIT / 5))); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/_api/version" || true)"
  case "$code" in 200|401) exit 0;; esac
  sleep 5
done
echo "$CONTAINER did not answer on $PORT within ${WAIT}s" >&2
exit 1
