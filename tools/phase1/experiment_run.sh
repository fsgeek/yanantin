#!/usr/bin/env bash
#
# Experiment runner for context paging evaluation.
#
# Orchestrates a single experimental run:
#   1. Reset target project to known state
#   2. Start proxy with treatment config
#   3. Launch Claude Code pointed at proxy
#   4. After completion: capture all artifacts
#   5. Tag and archive
#
# Usage:
#   ./tools/phase1/experiment_run.sh \
#       --treatment baseline \
#       --run 1 \
#       --project /path/to/target/project \
#       --branch experiment-start \
#       --prompt "Build feature X with tests" \
#       [--compact] [--age-threshold 4] [--min-size 500] \
#       [--strip-skills] [--trim-memory] \
#       [--temperature 0]
#
# Artifacts captured in: tmp/experiments/{treatment}_{run}/
#   - proxy.jsonl         (all API traffic)
#   - pages.jsonl         (eviction/fault log)
#   - session/            (copy of ~/.claude/projects/<project>/)
#   - git_log.txt         (final git log)
#   - git_diff.txt        (diff from start point)
#   - test_results.txt    (if tests ran)
#   - config.json         (treatment parameters)
#   - timing.json         (start/end timestamps)

set -euo pipefail

# Defaults
TREATMENT="baseline"
RUN_NUM=1
PROJECT_DIR=""
START_BRANCH="main"
PROMPT=""
COMPACT=""
AGE_THRESHOLD=4
MIN_SIZE=500
STRIP_SKILLS=""
TRIM_MEMORY=""
TEMPERATURE=""
PROXY_PORT=8080
EXPERIMENT_DIR=""

usage() {
    echo "Usage: $0 --treatment NAME --run N --project DIR --prompt TEXT [options]"
    echo ""
    echo "Required:"
    echo "  --treatment NAME    Treatment label (baseline, t1_compact, t2_trimmed, ...)"
    echo "  --run N             Run number (1, 2, 3, ...)"
    echo "  --project DIR       Target project directory"
    echo "  --prompt TEXT       Starting prompt for Claude Code"
    echo ""
    echo "Optional:"
    echo "  --branch BRANCH     Git branch to reset to (default: main)"
    echo "  --compact           Enable dead tool result eviction"
    echo "  --age-threshold N   Eviction age threshold (default: 4)"
    echo "  --min-size N        Min tool result size for eviction (default: 500)"
    echo "  --strip-skills      Strip skill definitions from system prompt"
    echo "  --trim-memory       Reduce MEMORY.md after first turn"
    echo "  --temperature N     Set temperature (e.g., 0 for deterministic)"
    echo "  --port N            Proxy port (default: 8080)"
    exit 1
}

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --treatment) TREATMENT="$2"; shift 2 ;;
        --run) RUN_NUM="$2"; shift 2 ;;
        --project) PROJECT_DIR="$2"; shift 2 ;;
        --branch) START_BRANCH="$2"; shift 2 ;;
        --prompt) PROMPT="$2"; shift 2 ;;
        --compact) COMPACT="--compact"; shift ;;
        --age-threshold) AGE_THRESHOLD="$2"; shift 2 ;;
        --min-size) MIN_SIZE="$2"; shift 2 ;;
        --strip-skills) STRIP_SKILLS="yes"; shift ;;
        --trim-memory) TRIM_MEMORY="yes"; shift ;;
        --temperature) TEMPERATURE="$2"; shift 2 ;;
        --port) PROXY_PORT="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; usage ;;
    esac
done

# Validate required args
if [[ -z "$PROJECT_DIR" || -z "$PROMPT" ]]; then
    echo "Error: --project and --prompt are required"
    usage
fi

# Setup experiment directory
YANANTIN_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
EXPERIMENT_DIR="${YANANTIN_DIR}/tmp/experiments/${TREATMENT}_run${RUN_NUM}"
mkdir -p "$EXPERIMENT_DIR"

echo "=========================================="
echo "Experiment Run"
echo "  Treatment:  $TREATMENT"
echo "  Run:        $RUN_NUM"
echo "  Project:    $PROJECT_DIR"
echo "  Branch:     $START_BRANCH"
echo "  Output:     $EXPERIMENT_DIR"
echo "  Compact:    ${COMPACT:-no}"
echo "  Strip skills: ${STRIP_SKILLS:-no}"
echo "  Trim memory:  ${TRIM_MEMORY:-no}"
echo "  Temperature:  ${TEMPERATURE:-default}"
echo "=========================================="

# Save config
cat > "$EXPERIMENT_DIR/config.json" << CONFIGEOF
{
    "treatment": "$TREATMENT",
    "run": $RUN_NUM,
    "project_dir": "$PROJECT_DIR",
    "start_branch": "$START_BRANCH",
    "compact": $([ -n "$COMPACT" ] && echo true || echo false),
    "age_threshold": $AGE_THRESHOLD,
    "min_size": $MIN_SIZE,
    "strip_skills": $([ -n "$STRIP_SKILLS" ] && echo true || echo false),
    "trim_memory": $([ -n "$TRIM_MEMORY" ] && echo true || echo false),
    "temperature": ${TEMPERATURE:-null},
    "proxy_port": $PROXY_PORT
}
CONFIGEOF

# Record start time
START_TIME=$(date -u +%Y-%m-%dT%H:%M:%S%z)
echo "{\"start\": \"$START_TIME\"}" > "$EXPERIMENT_DIR/timing.json"

# Step 1: Reset target project
echo ""
echo "[1/5] Resetting project to $START_BRANCH..."
cd "$PROJECT_DIR"
git checkout "$START_BRANCH" 2>&1 | tail -3
git clean -fd 2>&1 | tail -3 || true

# Clear Claude session data for this project
PROJECT_CLAUDE_DIR=$(echo "$PROJECT_DIR" | tr '/' '-' | sed 's/^-//')
CLAUDE_PROJECT_PATH="$HOME/.claude/projects/$PROJECT_CLAUDE_DIR"
if [[ -d "$CLAUDE_PROJECT_PATH" ]]; then
    echo "  Clearing previous session data: $CLAUDE_PROJECT_PATH"
    # Save and clear JSONL files (keep CLAUDE.md etc)
    find "$CLAUDE_PROJECT_PATH" -name "*.jsonl" -delete 2>/dev/null || true
fi

# Step 2: Start proxy
echo ""
echo "[2/5] Starting proxy on port $PROXY_PORT..."
PROXY_LOG_DIR="$EXPERIMENT_DIR"
PROXY_CMD="uv run python ${YANANTIN_DIR}/tools/phase1/proxy.py"
PROXY_CMD+=" --port $PROXY_PORT"
PROXY_CMD+=" --log-dir $PROXY_LOG_DIR"
if [[ -n "$COMPACT" ]]; then
    PROXY_CMD+=" --compact --age-threshold $AGE_THRESHOLD --min-size $MIN_SIZE"
fi

cd "$YANANTIN_DIR"
$PROXY_CMD &
PROXY_PID=$!
sleep 2

if ! kill -0 $PROXY_PID 2>/dev/null; then
    echo "Error: Proxy failed to start"
    exit 1
fi
echo "  Proxy PID: $PROXY_PID"

# Step 3: Run Claude Code
echo ""
echo "[3/5] Launching Claude Code..."
echo "  Prompt: ${PROMPT:0:80}..."
echo ""
echo "  >>> Claude Code will start in the target project directory."
echo "  >>> When the task is complete, exit Claude Code normally."
echo "  >>> The experiment will capture artifacts after exit."
echo ""

cd "$PROJECT_DIR"

# Build claude command
CLAUDE_CMD="ANTHROPIC_BASE_URL=http://localhost:$PROXY_PORT"
if [[ -n "$TEMPERATURE" ]]; then
    # Temperature is handled by proxy modification, not CLI flag
    echo "  Note: temperature=$TEMPERATURE will be injected by proxy"
fi

# Run Claude Code interactively
# The user will interact and exit when done
ANTHROPIC_BASE_URL="http://localhost:$PROXY_PORT" claude --prompt "$PROMPT" || true

# Step 4: Stop proxy and capture
echo ""
echo "[4/5] Capturing artifacts..."

kill $PROXY_PID 2>/dev/null || true
wait $PROXY_PID 2>/dev/null || true

# Copy session data
if [[ -d "$CLAUDE_PROJECT_PATH" ]]; then
    cp -r "$CLAUDE_PROJECT_PATH" "$EXPERIMENT_DIR/session/" 2>/dev/null || true
fi

# Git state
cd "$PROJECT_DIR"
git log --oneline -20 > "$EXPERIMENT_DIR/git_log.txt" 2>/dev/null || true
git diff "$START_BRANCH"..HEAD > "$EXPERIMENT_DIR/git_diff.txt" 2>/dev/null || true
git diff --stat "$START_BRANCH"..HEAD > "$EXPERIMENT_DIR/git_diff_stat.txt" 2>/dev/null || true

# Test results (if there's a standard test command)
if [[ -f "pyproject.toml" ]]; then
    uv run pytest tests/ -v --tb=short > "$EXPERIMENT_DIR/test_results.txt" 2>&1 || true
fi

# Record end time
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%S%z)
python3 -c "
import json
timing = json.load(open('$EXPERIMENT_DIR/timing.json'))
timing['end'] = '$END_TIME'
json.dump(timing, open('$EXPERIMENT_DIR/timing.json', 'w'), indent=2)
"

# Step 5: Summary
echo ""
echo "[5/5] Run complete."
echo ""

# Find the proxy log
PROXY_LOG=$(ls "$EXPERIMENT_DIR"/proxy_*.jsonl 2>/dev/null | head -1)
if [[ -n "$PROXY_LOG" ]]; then
    cd "$YANANTIN_DIR"
    uv run python tools/phase1/experiment_eval.py --run "$PROXY_LOG"
fi

echo ""
echo "Artifacts saved to: $EXPERIMENT_DIR"
echo "  config.json       - treatment parameters"
echo "  timing.json       - start/end timestamps"
echo "  proxy_*.jsonl     - all API traffic"
echo "  pages_*.jsonl     - eviction/fault log (if compact)"
echo "  session/          - Claude session data"
echo "  git_log.txt       - final commit history"
echo "  git_diff.txt      - changes from start point"
echo "  test_results.txt  - test output (if applicable)"
