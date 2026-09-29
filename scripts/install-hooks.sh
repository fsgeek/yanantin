#!/bin/bash
# Install the projects git hooks (the WHEN layer wiring).
#
# Idempotent: safe to re-run. Ensures the opentimestamps-client dependency is
# present in the project venv, then installs a thin .git/hooks/post-commit
# shim that execs the tracked hook in scripts/hooks/. Keeping the real hook
# under version control (and the shim trivial) means the governance logic is
# itself reviewable and signed, not hidden in .git/.
set -e

GIT_ROOT=$(git rev-parse --show-toplevel)
cd "$GIT_ROOT"

echo "Syncing project environment (ensures opentimestamps-client is installed)..."
uv sync

echo "Verifying ots client is callable..."
if ! "$GIT_ROOT/.venv/bin/ots" --version >/dev/null 2>&1; then
    echo "FATAL: ots not callable after 'uv sync'. Check pyproject.toml deps." >&2
    exit 1
fi

echo "Installing post-commit hook shim..."
HOOK="$GIT_ROOT/.git/hooks/post-commit"
cat > "$HOOK" << 'EOF'
#!/bin/bash
exec "$(git rev-parse --show-toplevel)/scripts/hooks/post-commit" "$@"
EOF
chmod +x "$HOOK"

echo "Done. The post-commit hook now stamps each commit with OpenTimestamps."
echo "Run 'scripts/ots-upgrade.sh' a few hours after committing to anchor to Bitcoin."
