#!/usr/bin/env bash
# Wire the Scout and Inspector Discord bots to their OpenClaw agents. Tokens
# travel via stdin, never argv or logs. Re-run after a Brain sandbox rebuild.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
set -a; . "$REPO/.env"; set +a
: "${DISCORD_BOT_TOKEN_SCOUT:?missing in .env}"
: "${DISCORD_BOT_TOKEN_INSPECTOR:?missing in .env}"

C="${1:-$(docker ps --format '{{.Names}}' | grep -E '^openshell-(my-assistant|openclaw)-' | head -1)}"
[ -n "$C" ] || { echo "No Brain/OpenClaw sandbox container is running"; exit 1; }

python3 -c 'import json, os; print(json.dumps({name: os.environ[f"DISCORD_BOT_TOKEN_{name.upper()}"] for name in ("scout", "inspector")}))' \
| docker exec -i "$C" node -e '
let raw=""; process.stdin.on("data", d => raw += d).on("end", () => {
  const tokens = JSON.parse(raw);
  const fs = require("fs");
  const configPath = "/sandbox/.openclaw/openclaw.json";
  const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
  config.channels ??= {};
  config.channels.discord ??= {};
  config.channels.discord.accounts ??= {};
  for (const id of Object.keys(tokens)) {
    config.channels.discord.accounts[id] = {
      token: tokens[id], enabled: true, healthMonitor: { enabled: false },
    };
  }
  const ids = Object.keys(tokens);
  config.bindings = (config.bindings || []).filter(binding =>
    !ids.includes(binding.agentId) && !ids.includes(binding.match?.accountId)
  );
  config.bindings.push(...ids.map(id => ({
    agentId: id, match: { channel: "discord", accountId: id },
  })));
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  console.log("patched Scout and Inspector bindings");
});'

# Bindings load at gateway boot. Restart only the agent process; the sandbox
# and its workspace remain intact.
GW_PID=$(docker exec "$C" sh -c "ps -eo pid,comm | grep openclaw | awk '{print \$1}' | head -1")
if [ -n "$GW_PID" ]; then
  docker exec "$C" kill "$GW_PID"
  echo "Gateway process restarted; bots reconnect over the next minute."
else
  echo "WARNING: gateway process not found; restart the Brain gateway to load bindings."
fi
