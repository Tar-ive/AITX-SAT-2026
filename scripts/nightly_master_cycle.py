#!/usr/bin/env python3
"""Nightly master cycle — the strategy tournament.

Runs at 05:30 UTC (after the gateway's 05:00 episodic distillation):

  1. PULL the day's digest: fresh MEMORY.md lessons + episodes.jsonl
  2. BUILD candidate policies, one per strategy:
       control      yesterday's champion (regression guard)
       episodic     tonight's synthesized MEMORY.md lessons
       exemplar-sft lessons distilled from good episodes (SFT-style route)
       autoresearch the mutation loop's current champion
  3. EVALUATE all candidates on the four criteria
       accuracy UP · retrieval LOW · deal safety (price regression) ·
       stability (model regression vs champion)
  4. SELECT the day's strategy (Pareto gate, prefer simpler on ties)
  5. PROMOTE daily: winner's lessons are written into the LIVE sandbox
     MEMORY.md — the Discord agents train on it all day
  6. WEEKLY (Sundays): a synthesis report goes to Discord for human
     approval/feedback; replies flow back through episodic distillation.

State: data/strategy_log.json, data/radar_snapshots.json, Supabase (via the
shell wrapper), coordinator API. Stdlib + requests only.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from auto_research_loop import evaluate, chat, OPENCODE_KEY, NVIDIA_KEY  # noqa: E402

REPO = Path(os.environ.get("REPO_DIR", Path(__file__).resolve().parents[1]))
STRATEGY_LOG = REPO / "data" / "strategy_log.json"
SNAPSHOTS = REPO / "data" / "radar_snapshots.json"
CHAMPION = REPO / "research" / "daily-champion-lessons.md"
COORD = os.environ.get("COORDINATOR_URL", "").rstrip("/")
GUILD = os.environ.get("DISCORD_SERVER_ID", "1527850934535717055")


def sandbox():
    out = subprocess.run(["docker", "ps", "--format", "{{.Names}}"],
                         capture_output=True, text=True).stdout
    for name in out.split():
        if name.startswith("openshell-"):
            return name
    return None


def pull(container, path):
    r = subprocess.run(["docker", "exec", container, "cat", path],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def exemplar_sft_lessons(episodes_text):
    """SFT-style route: distill rules from the good episodes (the teacher-
    dataset signal) via the researcher model."""
    good = []
    for line in episodes_text.splitlines():
        try:
            e = json.loads(line)
            if e.get("quality") == "good":
                good.append({"request": e.get("request"), "outcome": e.get("outcome"),
                             "lesson": e.get("lesson")})
        except json.JSONDecodeError:
            continue
    if not good:
        return ""
    prompt = ("Distill these successful interactions into <=15 generalized bullet "
              "rules for a GPU purchase-decision judge. No specifics that only "
              "apply to one case. Output only markdown bullets.\n\n"
              + json.dumps(good[-30:], indent=1))
    try:
        text, _ = chat("https://opencode.ai/zen/v1", OPENCODE_KEY,
                       "nemotron-3-ultra-free",
                       "Output only the requested bullets.", prompt, timeout=240)
    except Exception:
        text, _ = chat("https://integrate.api.nvidia.com/v1", NVIDIA_KEY,
                       "nvidia/nemotron-3-super-120b-a12b",
                       "Output only the requested bullets.", prompt, timeout=240)
    import re
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def select(results, champ_acc):
    """Pareto gate on the four criteria; prefer simpler strategy on ties."""
    order = ["control", "episodic", "exemplar-sft", "autoresearch"]
    viable = []
    for name, m in results.items():
        if m["n"] < 15:  # degraded eval
            continue
        if m["accuracy"] < champ_acc - 0.02:  # model regression
            continue
        if m["deal_safety"] < results["control"]["deal_safety"] - 2:  # price regression
            continue
        if m["retrieval_s"] > results["control"]["retrieval_s"] * 1.4:
            continue
        viable.append(name)
    if not viable:
        return "control"
    return max(viable, key=lambda n: (round(results[n]["accuracy"], 3), -order.index(n)))


def discord_post(token, content):
    import requests
    chans = requests.get(f"https://discord.com/api/v10/guilds/{GUILD}/channels",
                         headers={"Authorization": f"Bot {token}"}, timeout=15).json()
    target = next((c["id"] for c in chans if c.get("name") == "daily"),
                  next((c["id"] for c in chans if c.get("name") == "gpu-desk"), None))
    if target:
        requests.post(f"https://discord.com/api/v10/channels/{target}/messages",
                      headers={"Authorization": f"Bot {token}"},
                      json={"content": content[:1900]}, timeout=15)


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    box = sandbox()
    if not box:
        sys.exit("no sandbox running")

    episodic = pull(box, "/sandbox/.openclaw/workspace/MEMORY.md")
    episodes = pull(box, "/sandbox/.openclaw/workspace/memory/episodes.jsonl")
    autoresearch = (REPO / "research" / "champion-lessons.md")
    candidates = {
        "control": CHAMPION.read_text() if CHAMPION.exists() else "",
        "episodic": episodic,
        "exemplar-sft": exemplar_sft_lessons(episodes),
        "autoresearch": autoresearch.read_text() if autoresearch.exists() else "",
    }
    candidates = {k: v for k, v in candidates.items() if v or k == "control"}

    results = {}
    for name, lessons in candidates.items():
        print(f"[master] evaluating strategy: {name}", flush=True)
        results[name], _ = evaluate(lessons)
        print(f"[master] {name}: {json.dumps(results[name])}", flush=True)

    champ_acc = results["control"]["accuracy"]
    winner = select(results, champ_acc)
    print(f"[master] strategy of the day: {winner}", flush=True)

    # PROMOTE: winner's lessons become the live agents' memory + new champion
    CHAMPION.parent.mkdir(exist_ok=True)
    CHAMPION.write_text(candidates[winner])
    if winner != "control":
        tmp = "/tmp/promoted-lessons.md"
        Path(tmp).write_text(candidates[winner])
        subprocess.run(["docker", "cp", tmp, f"{box}:/sandbox/.openclaw/workspace/MEMORY.md"])
        print("[master] promoted into live sandbox MEMORY.md", flush=True)

    entry = {"date": today, "winner": winner,
             "results": {k: v for k, v in results.items()}}
    log = json.loads(STRATEGY_LOG.read_text()) if STRATEGY_LOG.exists() else []
    log.append(entry)
    STRATEGY_LOG.write_text(json.dumps(log, indent=1))

    snaps = json.loads(SNAPSHOTS.read_text()) if SNAPSHOTS.exists() else []
    snaps.append({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "version": f"daily-{today}-{winner}", "role": "champion",
                  "accepted": True, "stability": round(results[winner]["accuracy"] - champ_acc, 4),
                  **results[winner]})
    SNAPSHOTS.write_text(json.dumps(snaps, indent=1))

    if COORD:
        try:
            import requests
            requests.post(f"{COORD}/api/evaluations", timeout=15,
                          json={"version": f"daily-{today}", "source": "strategy-tournament",
                                "winner": winner, **results[winner]})
        except Exception:
            pass

    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if token:
        lines = [f"🌙 **Nightly strategy tournament — {today}**"]
        for n, m in results.items():
            mark = "🏆" if n == winner else "·"
            lines.append(f"{mark} `{n}`: acc {m['accuracy']} · {m['retrieval_s']}s · safety {m['deal_safety']}%")
        lines.append(f"Promoted **{winner}** — the agents train on it today.")
        discord_post(token, "\n".join(lines))

    # WEEKLY human review (Sundays)
    if datetime.now(timezone.utc).weekday() == 6 and token:
        week = log[-7:]
        prompt = ("Summarize this week of strategy tournaments for a human reviewer in "
                  "<=180 words: trend, best strategy, risks. End by asking for approval "
                  "or feedback.\n\n" + json.dumps(week, indent=1))
        try:
            text, _ = chat("https://opencode.ai/zen/v1", OPENCODE_KEY,
                           "nemotron-3-ultra-free", "Be concise and concrete.", prompt, timeout=240)
            discord_post(token, "📋 **Weekly RSI synthesis — human review requested**\n" + text
                         + "\n\nReply here with feedback; it becomes tomorrow night's lessons.")
        except Exception as e:
            print(f"[master] weekly synthesis failed: {e}", flush=True)


if __name__ == "__main__":
    main()
