#!/usr/bin/env bash
# Chasqui heartbeat — dispatches scouts on a cron schedule.
#
# Install:
#   crontab -e
#   # Every 6 hours, dispatch a scout:
#   0 */6 * * * /home/tony/projects/yanantin/.claude/hooks/chasqui_heartbeat.sh scout
#   # Daily at 3am, verify 3 claims:
#   0 3 * * * /home/tony/projects/yanantin/.claude/hooks/chasqui_heartbeat.sh verify
#   # Weekly on Sunday at noon, score the cairn:
#   0 12 * * 0 /home/tony/projects/yanantin/.claude/hooks/chasqui_heartbeat.sh score
#
# Modes: scout (default), verify, respond, score

set -euo pipefail

PROJECT_DIR="/home/tony/projects/yanantin"
LOG_DIR="${PROJECT_DIR}/logs"
LOG_FILE="${LOG_DIR}/chasqui.log"

# Source the API key from the environment file if it exists
ENV_FILE="${PROJECT_DIR}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Timestamp for log entries
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
MODE="${1:-scout}"

log() {
    echo "[$TS] $*" >> "$LOG_FILE"
}

log "Chasqui heartbeat: mode=$MODE"

cd "$PROJECT_DIR"

case "$MODE" in
    scout)
        uv run python -m yanantin.chasqui --json >> "$LOG_FILE" 2>&1
        ;;
    verify)
        uv run python -m yanantin.chasqui --verify 3 --json >> "$LOG_FILE" 2>&1
        ;;
    respond)
        # Find the most recent scout report and respond to it
        LATEST=$(ls -t docs/cairn/scout_*.md 2>/dev/null | head -1)
        if [ -n "$LATEST" ]; then
            uv run python -m yanantin.chasqui --respond "$LATEST" --json >> "$LOG_FILE" 2>&1
        else
            log "No scout reports found to respond to"
        fi
        ;;
    score)
        uv run python -m yanantin.chasqui --score --json >> "$LOG_FILE" 2>&1
        ;;
    *)
        log "Unknown mode: $MODE"
        exit 1
        ;;
esac

EXIT_CODE=$?
log "Chasqui heartbeat complete: exit=$EXIT_CODE"
