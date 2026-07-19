#!/usr/bin/env python3
"""End-to-end Discord latency probe: prompt in → agent reply out.

Posts a GPU-search prompt to #gpu-desk as a control bot user, then polls the
channel until an agent replies, recording wall-clock seconds. This is the
"real" speed metric the demo wants: the full path (Discord → sandbox → model →
tools → Discord), not just a model call. Run it before and after distillation
to show the smaller agents getting FASTER because they learned where to look.

Each result is appended to data/latency_runs.json and POSTed to the coordinator
(/api/radar and /api/latency) so the leaderboard plots before/after live.

Env: DISCORD_BOT_TOKEN, DISCORD_SERVER_ID, optional COORDINATOR_URL, LABEL.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
GUILD = os.environ.get("DISCORD_SERVER_ID", "1527850934535717055")
COORD = os.environ.get("COORDINATOR_URL", "").rstrip("/")
LABEL = os.environ.get("LABEL", "probe")
REPO = Path(os.environ.get("REPO_DIR", Path(__file__).resolve().parents[1]))
OUT = REPO / "data" / "latency_runs.json"
H = {"Authorization": f"Bot {TOKEN}"}

PROMPTS = [
    "@Brain find the best price for an RTX 5090, reply with one line.",
    "@Brain cheapest in-stock RTX 5080 from a safe retailer, one line.",
    "@Brain where should I buy a factory-sealed RTX 5070 Ti today?",
]


def channel_id(name="gpu-desk"):
    chans = requests.get(f"https://discord.com/api/v10/guilds/{GUILD}/channels",
                         headers=H, timeout=15).json()
    return next((c["id"] for c in chans if c.get("name") == name), None)


def probe_once(cid, prompt, my_id, timeout=120):
    sent = requests.post(f"https://discord.com/api/v10/channels/{cid}/messages",
                         headers=H, json={"content": prompt}, timeout=15).json()
    t0 = time.time()
    after = sent["id"]
    while time.time() - t0 < timeout:
        time.sleep(2)
        msgs = requests.get(f"https://discord.com/api/v10/channels/{cid}/messages",
                            headers=H, params={"after": after, "limit": 10}, timeout=15).json()
        # a reply from a bot that is NOT the prober = an agent answering
        for m in msgs:
            if m.get("author", {}).get("bot") and m["author"]["id"] != my_id and m.get("content"):
                return round(time.time() - t0, 2)
    return None


def main():
    me = requests.get("https://discord.com/api/v10/users/@me", headers=H, timeout=15).json()
    cid = channel_id()
    if not cid:
        raise SystemExit("no #gpu-desk channel")
    lats = []
    for p in PROMPTS:
        dt = probe_once(cid, p, me["id"])
        print(f"[latency] {LABEL}: {dt}s  «{p[:40]}»", flush=True)
        if dt is not None:
            lats.append(dt)
        time.sleep(5)
    if not lats:
        raise SystemExit("no agent replies captured")
    result = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "label": LABEL, "median_latency_s": round(sorted(lats)[len(lats) // 2], 2),
              "mean_latency_s": round(sum(lats) / len(lats), 2), "samples": len(lats),
              "all_s": lats}
    hist = json.loads(OUT.read_text()) if OUT.exists() else []
    hist.append(result)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(hist, indent=1))
    print("[latency] result:", json.dumps(result), flush=True)
    if COORD:
        for path in ("/api/latency", "/api/radar"):
            try:
                requests.post(f"{COORD}{path}", timeout=15,
                              json={"source": "latency-probe", **result})
            except requests.RequestException:
                pass


if __name__ == "__main__":
    main()
