#!/bin/bash
# Upgrade pending OpenTimestamps proofs (the WHEN layer, part 2).
#
# `ots stamp` returns immediately with an INCOMPLETE proof (a commitment held
# by calendar servers). A few hours later, once the commitment is anchored in
# a Bitcoin block, `ots upgrade` rewrites the .ots file with the full proof
# path to the blockchain. Run this periodically after committing.
#
# Layout: pending proofs live in timestamps/. Once a proof is complete
# (Bitcoin-anchored) it can never change again, so its triple — the bare
# <hash> target file, the .ots proof, and any .ots.bak — moves to
# timestamps/anchored/ and is never rescanned. This keeps each run
# proportional to the pending set (recent commits), not the whole history.
# The completeness signal is `ots upgrade`'s exit code: success means the
# proof is complete (calendar-not-ready is the failure case) — the same
# contract the pending: branch below has always relied on.
set -e

GIT_ROOT=$(git rev-parse --show-toplevel)
cd "$GIT_ROOT"

# Resolve ots the same way the post-commit hook does (venv first, uv fallback).
if [ -x "$GIT_ROOT/.venv/bin/ots" ]; then
    OTS=("$GIT_ROOT/.venv/bin/ots")
elif command -v uv >/dev/null 2>&1 && uv run --quiet ots --version >/dev/null 2>&1; then
    OTS=(uv run --quiet ots)
else
    echo "FATAL: ots client not found. Run: uv sync" >&2
    exit 1
fi

ANCHORED_DIR="timestamps/anchored"

upgraded=0
anchored=0

# Move a completed proof's triple into ANCHORED_DIR, staging tracked files
# via git mv and adding untracked ones (a .bak born this run) in place.
move_to_anchored() {
    local proof=$1
    local base=${proof%.ots}
    mkdir -p "$ANCHORED_DIR"
    local p dest
    for p in "$base" "$proof" "$proof.bak"; do
        [ -e "$p" ] || continue
        dest="$ANCHORED_DIR/$(basename "$p")"
        if git ls-files --error-unmatch "$p" >/dev/null 2>&1; then
            git mv "$p" "$dest"
        else
            mv "$p" "$dest"
            git add -- "$dest"
        fi
    done
    anchored=$((anchored + 1))
}

for f in timestamps/*.ots; do
    [ -f "$f" ] || continue
    original_hash=$(sha256sum "$f" | cut -d' ' -f1)
    if "${OTS[@]}" upgrade "$f" 2>/dev/null; then
        upgraded_hash=$(sha256sum "$f" | cut -d' ' -f1)
        if [ "$original_hash" != "$upgraded_hash" ]; then
            echo "upgraded: $f"
            upgraded=$((upgraded + 1))
        else
            echo "already complete: $f"
        fi
        move_to_anchored "$f"
    else
        echo "pending:  $f"
    fi
done

if [ "$anchored" -gt 0 ]; then
    # Scope the commit to the timestamps tree: the staged moves and upgraded
    # proofs land; unrelated staged work elsewhere is untouched. The ots:
    # prefix matters: the post-commit hook skips stamping ots:* commits.
    git commit --only --no-verify \
        -m "ots: upgrade $upgraded timestamp(s), $anchored anchored" \
        -- timestamps
else
    echo "No timestamps ready to upgrade yet."
fi
