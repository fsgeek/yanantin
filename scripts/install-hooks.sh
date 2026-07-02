#!/bin/bash
# Install yanantin git hooks. Idempotent.
#
# Activation is a single portable action: point git at the tracked .githooks/
# directory via core.hooksPath. That directory is the single source of truth for
# ALL hooks (post-commit OTS stamping, pre-commit + pre-push signing guards), so
# a fresh clone is fully protected after one run of this script.
#
# Why hooksPath instead of copying files into .git/hooks/:
#   - .git/hooks/ is untracked and per-clone — copies drift from the repo.
#   - core.hooksPath makes the tracked .githooks/ files authoritative directly.
#   - It was previously set only as local config on one machine, so the signing
#     guard silently did NOT run on any other clone. This makes it replicable.
set -e

GIT_ROOT=$(git rev-parse --show-toplevel)
cd "$GIT_ROOT"

git config core.hooksPath .githooks

# Ensure the tracked hooks are executable (a fresh clone preserves the mode bit,
# but be defensive in case they were touched).
chmod +x .githooks/post-commit .githooks/pre-commit .githooks/pre-push

echo "Installed: core.hooksPath -> .githooks (post-commit, pre-commit, pre-push)"
echo
echo "Active hooks:"
echo "  post-commit  OpenTimestamps stamp of each commit (docs/ots/<short>.ots)"
echo "  pre-commit   signing INTENT guard (signed + author==committer + key UID)"
echo "  pre-push     signing OUTCOME guard over the outgoing range"
echo
echo "Each new commit is stamped via OpenTimestamps. Run scripts/ots-upgrade.sh"
echo "periodically (e.g., daily) to anchor pending proofs to Bitcoin."
