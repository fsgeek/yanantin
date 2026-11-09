#!/usr/bin/env bash
# How arango-objects (yanantin's file index, host port 8532) is created. The data
# lives in the named volume yanantin-objects-data, so recreating the container
# keeps it. Stop the refresh and check for running queries first.
#
# ARANGODB_OVERRIDE_DETECTED_TOTAL_MEMORY must sit well below the 12 GiB cap and
# below the landing's 9 GiB memory guard (scripts/land_full_corpus.py). ArangoDB
# sizes its caches from this number. At 12G it settled at 9.5-11 GiB, the guard
# held every landing for its full hour, and the 2026-11-07 and 2026-11-09 refreshes
# failed. At 8G (recreated 2026-11-09) a full refresh peaked at 5.25 GiB.
set -euo pipefail

docker run -d --name arango-objects --restart always \
  --memory 12g --memory-swap 24g \
  -p 8532:8529 \
  -v yanantin-objects-data:/var/lib/arangodb3 \
  -v "$HOME/.yanantin/config/secrets/arango-objects-root:/run/secrets/arango-root:ro" \
  -e ARANGO_ROOT_PASSWORD_FILE=/run/secrets/arango-root \
  -e ARANGODB_OVERRIDE_DETECTED_TOTAL_MEMORY=8G \
  arangodb/enterprise:3.12.9.4
