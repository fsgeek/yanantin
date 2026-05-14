#!/bin/bash
# Install yanantin git hooks. Idempotent.
#
# Installs:
#   .git/hooks/post-commit  → wraps scripts/hooks/post-commit
#
# The pre-commit hook (pipeline attestation freshness) is managed
# separately; see .claude/hooks/pipeline_attestation.py.
set -e

GIT_ROOT=$(git rev-parse --show-toplevel)
cd "$GIT_ROOT"

HOOK_DIR=".git/hooks"
mkdir -p "$HOOK_DIR"

cat > "$HOOK_DIR/post-commit" << 'EOF'
#!/bin/bash
exec "$(git rev-parse --show-toplevel)/scripts/hooks/post-commit" "$@"
EOF
chmod +x "$HOOK_DIR/post-commit"

echo "Installed: $HOOK_DIR/post-commit -> scripts/hooks/post-commit"
echo
echo "Each new commit will be stamped via OpenTimestamps and produce"
echo "a follow-up 'ots: stamp <short>' commit. Run scripts/ots-upgrade.sh"
echo "periodically (e.g., daily) to anchor pending proofs to Bitcoin."
