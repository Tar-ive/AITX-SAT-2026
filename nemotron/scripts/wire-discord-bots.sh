#!/usr/bin/env bash
# Wire the Scout/Inspector/Concierge Discord bots to their agents by patching
# the sandbox's live openclaw.json (multi-account + bindings). The gateway
# hot-reloads the change — no restart needed (a restart would regenerate the
# file, so RE-RUN THIS after every sandbox start/rebuild).
# Tokens come from the repo .env (DISCORD_BOT_TOKEN_{SCOUT,INSPECTOR,CONCIERGE})
# and travel via stdin — never argv, never logs.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
set -a; . "$REPO/.env"; set +a
: "${DISCORD_BOT_TOKEN_SCOUT:?missing in .env}"
: "${DISCORD_BOT_TOKEN_INSPECTOR:?missing in .env}"
: "${DISCORD_BOT_TOKEN_CONCIERGE:?missing in .env}"

C="${1:-$(docker ps --format '{{.Names}}' | grep openshell-openclaw | head -1)}"
[ -n "$C" ] || { echo "No openclaw sandbox container running"; exit 1; }

printf '{"scout":"%s","inspector":"%s","concierge":"%s"}' \
  "$DISCORD_BOT_TOKEN_SCOUT" "$DISCORD_BOT_TOKEN_INSPECTOR" "$DISCORD_BOT_TOKEN_CONCIERGE" \
| docker exec -i "$C" node -e '
let raw="";process.stdin.on("data",d=>raw+=d).on("end",()=>{
  const toks=JSON.parse(raw);
  const fs=require("fs");
  const p="/sandbox/.openclaw/openclaw.json";
  const cfg=JSON.parse(fs.readFileSync(p,"utf8"));
  for(const id of ["scout","inspector","concierge"]){
    cfg.channels.discord.accounts[id]={token:toks[id],enabled:true,healthMonitor:{enabled:false}};
  }
  cfg.bindings=[
    {agentId:"scout",match:{channel:"discord",accountId:"scout"}},
    {agentId:"inspector",match:{channel:"discord",accountId:"inspector"}},
    {agentId:"concierge",match:{channel:"discord",accountId:"concierge"}}
  ];
  fs.writeFileSync(p,JSON.stringify(cfg,null,2));
  console.log("patched: accounts="+Object.keys(cfg.channels.discord.accounts).join(",")+
    " bindings="+cfg.bindings.map(b=>b.agentId).join(","));
});'
# Accounts hot-reload, but bindings only load at gateway boot — so restart the
# gateway PROCESS in-place (the supervisor respawns it; the container and the
# patched config survive, unlike a container restart which regenerates config).
GW_PID=$(docker exec "$C" sh -c "ps -eo pid,comm | grep openclaw | awk '{print \$1}' | head -1")
if [ -n "$GW_PID" ]; then
  docker exec "$C" kill "$GW_PID"
  echo "Gateway process restarted (pid $GW_PID) — bots reconnect staggered over ~40s."
else
  echo "WARNING: gateway process not found; bindings may not load until next gateway start."
fi
