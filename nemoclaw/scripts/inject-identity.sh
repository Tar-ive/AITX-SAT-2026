#!/usr/bin/env bash
# Idempotently splice identity/AGENTS.team.md into the running sandbox's
# AGENTS.md between the AITX-TEAM-PROTOCOL markers. Repo is source of truth.
# Usage: scripts/inject-identity.sh [container-name]
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
BLOCK="$REPO/identity/AGENTS.team.md"
C="${1:-$(docker ps --format '{{.Names}}' | grep openshell-openclaw | head -1)}"
[ -n "$C" ] || { echo "No openclaw sandbox container running"; exit 1; }

WS=/sandbox/.openclaw/workspace

# one-time backup of the stock file
docker exec "$C" sh -c "[ -f $WS/AGENTS.md.stock ] || cp $WS/AGENTS.md $WS/AGENTS.md.stock"

# copy block in, then splice: drop any old managed block, append the new one
docker cp "$BLOCK" "$C:/tmp/AGENTS.team.md"
docker exec "$C" sh -c "
  awk '/<!-- BEGIN AITX-TEAM-PROTOCOL/{skip=1} !skip{print} /<!-- END AITX-TEAM-PROTOCOL/{skip=0}' \
    $WS/AGENTS.md > /tmp/AGENTS.base.md
  cat /tmp/AGENTS.base.md /tmp/AGENTS.team.md > $WS/AGENTS.md
  rm /tmp/AGENTS.base.md /tmp/AGENTS.team.md
  grep -c 'AITX-TEAM-PROTOCOL' $WS/AGENTS.md
"
echo "Injected team protocol into $C:$WS/AGENTS.md"
