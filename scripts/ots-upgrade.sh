#!/bin/bash
# Upgrade pending OpenTimestamps proofs to Bitcoin-anchored proofs.
#
# Calendar aggregation into a Bitcoin block typically takes a few
# hours. Run this periodically (manually or via cron) to convert
# pending PendingAttestations into BitcoinBlockHeaderAttestations.
#
# If any proofs are upgraded, commits them as "ots: upgrade N timestamp(s)".
set -e

GIT_ROOT=$(git rev-parse --show-toplevel)
cd "$GIT_ROOT"

UV="${UV:-$HOME/.local/bin/uv}"
if [ ! -x "$UV" ]; then
    echo "ots: uv not found at $UV" >&2
    exit 1
fi

UPGRADED=$("$UV" run python -c "
from pathlib import Path
from yanantin.provenance.timestamp import upgrade_pending_proofs
print(len(upgrade_pending_proofs(Path('docs/ots'))))
")

if [ "$UPGRADED" -gt 0 ]; then
    git add docs/ots/
    git commit --no-verify -m "ots: upgrade $UPGRADED timestamp(s)"
    echo "Upgraded $UPGRADED OTS proof(s)."
else
    echo "No proofs ready to upgrade."
fi
