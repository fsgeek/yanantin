#!/usr/bin/env bash
# Launch the pichay proxy for live context monitoring.
#
# Usage:
#   bash tools/phase1/launch_proxy.sh [--observe | --compact | --full]
#
# Modes:
#   --observe   Log only, no interventions (default)
#   --compact   Evict stale tool results (context paging)
#   --full      Compact + trim (tool stubs, skill dedup, paging)
#
# After this starts, in another terminal:
#   ANTHROPIC_BASE_URL=http://localhost:<PORT> claude
#
# And optionally in a third terminal:
#   python tools/phase1/wss_monitor.py tmp/proxy-logs/proxy_*.jsonl

set -euo pipefail

PICHAY_DIR="$HOME/projects/pichay"
PICHAY_VENV="$PICHAY_DIR/.venv/bin/python"
LOG_DIR="$HOME/projects/yanantin/tmp/proxy-logs"

if [ ! -f "$PICHAY_VENV" ]; then
    echo "Error: pichay venv not found at $PICHAY_VENV" >&2
    echo "Run: cd $PICHAY_DIR && uv sync" >&2
    exit 1
fi

mkdir -p "$LOG_DIR"

# Defaults
MODE="observe"
TOKEN_CAP=200000
PROXY_ARGS=()

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --observe)
            MODE="observe"
            shift
            ;;
        --compact)
            MODE="compact"
            PROXY_ARGS+=(--compact)
            shift
            ;;
        --full)
            MODE="compact+trim"
            PROXY_ARGS+=(--compact --trim)
            shift
            ;;
        --no-cap)
            TOKEN_CAP=0
            shift
            ;;
        --token-cap)
            TOKEN_CAP="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [--observe|--compact|--full] [--token-cap N|--no-cap]" >&2
            exit 1
            ;;
    esac
done

CAP_DISPLAY="none"
if [ "$TOKEN_CAP" -gt 0 ] 2>/dev/null; then
    PROXY_ARGS+=(--token-cap "$TOKEN_CAP")
    CAP_DISPLAY="$TOKEN_CAP (warning at $(( TOKEN_CAP * 80 / 100 )))"
fi

echo "═══════════════════════════════════════════════════════════════"
echo " Pichay Proxy — mode: $MODE"
echo " Token cap: $CAP_DISPLAY"
echo " Logs: $LOG_DIR"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "After the proxy starts, copy the port from below and run:"
echo ""
echo "  ANTHROPIC_BASE_URL=http://localhost:PORT claude              # new session"
echo "  ANTHROPIC_BASE_URL=http://localhost:PORT claude --continue   # resume last"
echo ""
echo "To monitor working set size (optional, separate terminal):"
echo ""
echo "  python tools/phase1/wss_monitor.py $LOG_DIR/proxy_*.jsonl"
echo ""
echo "───────────────────────────────────────────────────────────────"

exec "$PICHAY_VENV" -m pichay.proxy \
    --port 0 \
    --log-dir "$LOG_DIR" \
    ${PROXY_ARGS[@]+"${PROXY_ARGS[@]}"}
