#!/usr/bin/env bash
# Workspace entrypoint: install NemoClaw, onboard the agent team, inject the
# repo identity layer, then follow logs. Idempotent across container restarts.
set -euo pipefail

echo "[startup] installing prerequisites"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq curl git ca-certificates docker.io binutils jq >/dev/null

export PATH="$HOME/.local/bin:$PATH"

if ! command -v nemoclaw >/dev/null 2>&1; then
  echo "[startup] installing NemoClaw"
  curl -fsSL https://www.nvidia.com/nemoclaw.sh -o /tmp/nemoclaw-installer.sh
  bash /tmp/nemoclaw-installer.sh --non-interactive --yes-i-accept-third-party-software
fi

# Fix #9 (see retail-assistant example): the gateway launches the sandbox via
# the HOST docker daemon, mounting openshell binaries from NEMOCLAW_BIN_PATH —
# an identical host/container path. The installer drops them in /usr/local/bin,
# so copy them into the shared path or the sandbox container cannot start
# ("openshell-sandbox: is a directory").
mkdir -p "$NEMOCLAW_BIN_PATH"
for b in openshell openshell-gateway openshell-sandbox; do
  rm -rf "${NEMOCLAW_BIN_PATH:?}/$b"   # purge dirs Docker may have auto-created
  cp -f "/usr/local/bin/$b" "$NEMOCLAW_BIN_PATH/$b" 2>/dev/null || true
done
ls -la "$NEMOCLAW_BIN_PATH"

# Official knobs (per retail-assistant example): tell NemoClaw where the
# host-visible binaries live so gateway + sandbox mounts resolve on the host.
export NEMOCLAW_OPENSHELL_GATEWAY_BIN="$NEMOCLAW_BIN_PATH/openshell-gateway"
export NEMOCLAW_OPENSHELL_SANDBOX_BIN="$NEMOCLAW_BIN_PATH/openshell-sandbox"

sandbox_running() {
  docker ps --format '{{.Names}}' | grep -q "openshell-${NEMOCLAW_SANDBOX_NAME}"
}

echo "[startup] onboarding sandbox '$NEMOCLAW_SANDBOX_NAME' with agent team (attempt 1)"
timeout 20m nemoclaw onboard --agents /deploy/config/agents.yaml || true

if ! sandbox_running; then
  echo "[startup] attempt 1 incomplete — killing stale gateway and retrying (example's Fix #9 flow)"
  pkill -f openshell-gateway 2>/dev/null || true
  docker rm -f "openshell-${NEMOCLAW_SANDBOX_NAME}" 2>/dev/null || true
  sleep 3
  timeout 20m nemoclaw onboard --resume || timeout 20m nemoclaw onboard --fresh --agents /deploy/config/agents.yaml || true
fi

if ! sandbox_running; then
  echo "[startup] onboarding still incomplete; keeping container alive for inspection"
  sleep infinity
fi

echo "[startup] injecting identity layer"
C=$(docker ps --format '{{.Names}}' | grep "openshell-${NEMOCLAW_SANDBOX_NAME}" | head -1)
if [ -n "$C" ]; then
  WS=/sandbox/.openclaw/workspace
  docker exec "$C" sh -c "[ -f $WS/AGENTS.md.stock ] || cp $WS/AGENTS.md $WS/AGENTS.md.stock"
  docker cp /deploy/identity/AGENTS.team.md "$C:/tmp/AGENTS.team.md"
  docker exec "$C" sh -c "
    awk '/<!-- BEGIN AITX-TEAM-PROTOCOL/{skip=1} !skip{print} /<!-- END AITX-TEAM-PROTOCOL/{skip=0}' \
      $WS/AGENTS.md > /tmp/AGENTS.base.md
    cat /tmp/AGENTS.base.md /tmp/AGENTS.team.md > $WS/AGENTS.md
    rm /tmp/AGENTS.base.md /tmp/AGENTS.team.md"
  echo "[startup] identity injected into $C"

  if [ -n "${DISCORD_BOT_TOKEN_SCOUT:-}" ]; then
    echo "[startup] wiring per-agent Discord bots (multi-account hot reload)"
    printf '{"scout":"%s","inspector":"%s","concierge":"%s"}' \
      "$DISCORD_BOT_TOKEN_SCOUT" "$DISCORD_BOT_TOKEN_INSPECTOR" "$DISCORD_BOT_TOKEN_CONCIERGE" \
    | docker exec -i "$C" node -e '
      let raw="";process.stdin.on("data",d=>raw+=d).on("end",()=>{
        const toks=JSON.parse(raw);const fs=require("fs");
        const p="/sandbox/.openclaw/openclaw.json";
        const cfg=JSON.parse(fs.readFileSync(p,"utf8"));
        for(const id of ["scout","inspector","concierge"])
          cfg.channels.discord.accounts[id]={token:toks[id],enabled:true,healthMonitor:{enabled:false}};
        cfg.bindings=["scout","inspector","concierge"].map(id=>({agentId:id,match:{channel:"discord",accountId:id}}));
        fs.writeFileSync(p,JSON.stringify(cfg,null,2));
        console.log("[startup] discord accounts wired");});'
  fi
else
  echo "[startup] WARNING: sandbox container not found; identity not injected"
fi

echo "[startup] ready — following sandbox logs"
exec nemoclaw "$NEMOCLAW_SANDBOX_NAME" logs --follow
