#!/usr/bin/env python3
"""Post a human-digestible evaluation digest to Discord #eval (step 10).

Reads the latest harness experiments from Supabase + the radar snapshots, and
posts a compact card with the FIVE eval metrics (decision quality,
seconds/answer, prompt-injection risk, episodic-memory diff lines, knowledge
regression), before→after, the winning action, and rollback status. Separate
from the noisy #daily so humans have one clean place to monitor RSI.

Env: DISCORD_BOT_TOKEN, DISCORD_SERVER_ID, SUPABASE_DB_PW (+ pooler host/user),
optional REPO_DIR.
"""
import json
import os
import subprocess
from pathlib import Path

import requests

TOKEN = os.environ["DISCORD_BOT_TOKEN"].strip().strip("'").strip('"')
GUILD = os.environ.get("DISCORD_SERVER_ID", "1527850934535717055")
REPO = Path(os.environ.get("REPO_DIR", Path(__file__).resolve().parents[1]))
H = {"Authorization": f"Bot {TOKEN}"}


def envq(name, default=""):
    return os.environ.get(name, default).strip().strip("'").strip('"')


def psql(sql):
    dsn = (f"host={envq('SUPABASE_POOLER_HOST', 'aws-0-ca-central-1.pooler.supabase.com')} "
           f"port=5432 dbname=postgres user={envq('SUPABASE_POOLER_USER', 'postgres.qzegmkzyzalmakoqxezc')} "
           f"sslmode=require")
    r = subprocess.run(["psql", dsn, "-t", "-A", "-F", "\x1f", "-c", sql],
                       capture_output=True, text=True,
                       env={**os.environ, "PGPASSWORD": envq("SUPABASE_DB_PW")})
    return r.stdout.strip()


def channel(name):
    chans = requests.get(f"https://discord.com/api/v10/guilds/{GUILD}/channels",
                         headers=H, timeout=15).json()
    c = next((c for c in chans if c.get("name") == name), None)
    return (c["id"], c["type"]) if c else (None, None)


def deliver(cid, ctype, title, content):
    """Forum channels (type 15) need a thread with a title; text channels
    (type 0) take a plain message."""
    if ctype == 15:
        return requests.post(f"https://discord.com/api/v10/channels/{cid}/threads",
                             headers=H, timeout=15,
                             json={"name": title[:90], "message": {"content": content[:1900]}})
    return requests.post(f"https://discord.com/api/v10/channels/{cid}/messages",
                         headers=H, timeout=15, json={"content": content[:1900]})


def main():
    # Latest accepted (champion) and most recent experiment from the registry.
    latest = psql(
        "select action, decision_quality, seconds_per_answer, prompt_injection_risk, "
        "memory_diff_lines, knowledge_regression, accepted, rolled_back "
        "from public.harness_experiments "
        "where coalesce(metadata->>'hidden_from_evals','false') <> 'true' "
        "order by created_at desc limit 1;")
    champ = psql(
        "select decision_quality, seconds_per_answer, prompt_injection_risk, "
        "memory_diff_lines, knowledge_regression from public.harness_experiments "
        "where accepted and coalesce(metadata->>'hidden_from_evals','false') <> 'true' "
        "order by created_at desc limit 1;")

    def arrow(cur, base, lower_better=False):
        try:
            d = float(cur) - float(base)
        except (TypeError, ValueError):
            return ""
        good = (d < 0) if lower_better else (d > 0)
        return f" {'▲' if d > 0 else '▼' if d < 0 else '–'}{abs(d):.3g}" if not good else \
               f" ✅{'▲' if d > 0 else '▼'}{abs(d):.3g}"

    cid, ctype = channel("eval")
    if not cid:
        cid, ctype = channel("gpu-desk")
    if not cid:
        print("no #eval or #gpu-desk channel")
        return

    from datetime import datetime, timezone
    title = f"RSI eval — {datetime.now(timezone.utc):%Y-%m-%d %H:%MZ}"
    if not latest:
        lines = ["📊 **RSI Eval Digest** — no harness experiments recorded yet.",
                 "The autoresearch loops write here as they run experiments."]
    else:
        f = latest.split("\x1f")
        c = champ.split("\x1f") if champ else [""] * 5
        lines = [
            "📊 **RSI Eval Digest** — the five metrics that matter",
            f"Latest action: `{f[0]}` · {'🏆 PROMOTED' if f[6] == 't' else '↩️ ROLLED BACK' if f[7] == 't' else 'candidate (held)'}",
            "",
            f"• **Decision quality**: {f[1]}{arrow(f[1], c[0])}",
            f"• **Seconds per answer**: {f[2]}{arrow(f[2], c[1], lower_better=True)}",
            f"• **Prompt injection risk**: {f[3] or 'not measured'}{arrow(f[3], c[2], lower_better=True)}",
            f"• **Hermes episodic memory diff lines**: {f[4]}  _(how much the agent learned)_",
            f"• **Agent knowledge regression**: {f[5]}  _(≥0 = no regression)_",
            "",
            "Promotion is automatic on a defensible, regression-free gain; "
            "rollback is automatic on a >2pt drop. Humans monitor here.",
        ]
    r = deliver(cid, ctype, title, "\n".join(lines))
    print(f"posted eval digest ({'forum thread' if ctype == 15 else 'message'}): HTTP {r.status_code}")


if __name__ == "__main__":
    main()
