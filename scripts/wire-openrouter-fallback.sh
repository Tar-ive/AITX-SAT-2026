#!/usr/bin/env bash
# Wire OpenRouter as the inference fallback for every agent in the sandbox.
# Same models, OpenRouter naming (nano gains an -a3b suffix):
#   nvidia/nemotron-3-super-120b-a12b  -> openrouter: same id
#   nvidia/nemotron-3-nano-30b         -> openrouter: nvidia/nemotron-3-nano-30b-a3b
# OpenClaw fails over across model fallbacks on provider errors (incl. 429s).
# Run ON THE EC2 HOST after any sandbox rebuild (same lifecycle as
# wire-discord-bots.sh). Requires OPENROUTER_API_KEY in the deploy .env.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
set -a; . "$REPO/deploy/docker-compose/.env" 2>/dev/null || . "$REPO/.env"; set +a
: "${OPENROUTER_API_KEY:?missing in env}"

C="${1:-$(docker ps --format '{{.Names}}' | grep openshell- | head -1)}"
[ -n "$C" ] || { echo "no sandbox container"; exit 1; }
W="$(docker ps --format '{{.Names}}' | grep workspace | head -1)"

# 1. Egress policy so the sandbox may reach openrouter.ai at all
if [ -n "$W" ]; then
  docker exec "$W" sh -c 'export PATH=/root/.local/bin:$PATH; nemoclaw openclaw policy-add --from-file /deploy/config/policies/openrouter.yaml --yes 2>&1 | tail -2' || echo "policy-add reported an issue (may already exist)"
fi

# 2. Provider + per-agent fallbacks in openclaw.json (token via stdin)
printf '%s' "$OPENROUTER_API_KEY" | docker exec -i "$C" node -e '
let key="";process.stdin.on("data",d=>key+=d).on("end",()=>{
  const fs=require("fs"), p="/sandbox/.openclaw/openclaw.json";
  const c=JSON.parse(fs.readFileSync(p,"utf8"));
  const model=(id)=>({id,name:"openrouter/"+id,reasoning:false,input:["text"],
    cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:131072,maxTokens:4096});
  c.models.providers.openrouter={
    baseUrl:"https://openrouter.ai/api/v1", apiKey:key.trim(), api:"openai-completions",
    models:[model("nvidia/nemotron-3-super-120b-a12b"), model("nvidia/nemotron-3-nano-30b-a3b")]};
  const FB={"inference/nvidia/nemotron-3-super-120b-a12b":"openrouter/nvidia/nemotron-3-super-120b-a12b",
            "inference/nvidia/nemotron-3-nano-30b":"openrouter/nvidia/nemotron-3-nano-30b-a3b"};
  const d=c.agents.defaults.model;
  const dp=typeof d==="string"?d:d.primary;
  c.agents.defaults.model={primary:dp,fallbacks:[FB[dp]||FB["inference/nvidia/nemotron-3-super-120b-a12b"]]};
  for(const a of c.agents.list||[]){
    if(!a.model) continue;
    const prim=typeof a.model==="string"?a.model:a.model.primary;
    a.model={primary:prim,fallbacks:[FB[prim]||FB["inference/nvidia/nemotron-3-super-120b-a12b"]]};
  }
  fs.writeFileSync(p,JSON.stringify(c,null,2));
  console.log("providers:",Object.keys(c.models.providers).join(","),
    "| defaults:",JSON.stringify(c.agents.defaults.model));
});'

# 3. Restart the gateway process so model config loads at boot
GW_PID=$(docker exec "$C" sh -c "ps -eo pid,comm | grep openclaw | awk '{print \$1}' | head -1")
[ -n "$GW_PID" ] && docker exec "$C" kill "$GW_PID" && echo "gateway restarted (pid $GW_PID); bots reconnect over ~40s"
echo "OpenRouter fallback wired."
