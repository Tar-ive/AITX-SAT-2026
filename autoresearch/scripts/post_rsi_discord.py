#!/usr/bin/env python3
"""Post the latest measured RSI candidate to Discord for human review."""

import csv
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://discord.com/api/v10"


def load_env():
    path = ROOT / ".env"
    for raw in path.read_text().splitlines() if path.exists() else []:
        if "=" in raw and not raw.lstrip().startswith("#"):
            key, value = raw.split("=", 1)
            os.environ.setdefault(key, value.strip().strip("'\""))


def request(method, url, **kwargs):
    response = requests.request(method, url, timeout=15, **kwargs)
    if response.status_code == 429:
        time.sleep(min(float(response.json().get("retry_after", 1)), 5))
        response = requests.request(method, url, timeout=15, **kwargs)
    response.raise_for_status()
    return response


def main():
    load_env()
    token = os.environ["DISCORD_BOT_TOKEN"]
    channel = os.getenv("DISCORD_RSI_CHANNEL_ID", "1527922756480401478")
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    with (ROOT / "data/rsi_runs.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    candidate, champion = rows[-1], next(row for row in reversed(rows) if row["current"] == "true")
    delta = (float(candidate["decision_quality"]) / float(champion["decision_quality"]) - 1) * 100
    recommendation = "REVIEW FOR PROMOTION" if delta > 0 else "KEEP CHAMPION"
    digest = (
        f"**Actual RSI digest — {candidate['evaluated_at'][:10]}**\n"
        f"Champion: **{champion['version']} · {float(champion['decision_quality']):.3f}**  |  "
        f"Challenger: **{candidate['version']} · {float(candidate['decision_quality']):.3f}**\n"
        f"Delta: **{delta:+.1f}%** · rollouts: **{candidate['sample_size']}**\n"
        f"Recommendation: **{recommendation}**."
    )
    request("POST", f"{API}/channels/{channel}/messages", headers=headers, json={"content": digest})
    approval = request(
        "POST",
        f"{API}/channels/{channel}/messages",
        headers=headers,
        json={"content": (
            f"**Human promotion gate**\nReview `{candidate['version']}`. "
            f"React ✅ to promote or ❌ to keep `{champion['version']}`. "
            "No promotion happens automatically."
        )},
    ).json()
    for emoji in ("%E2%9C%85", "%E2%9D%8C"):
        request(
            "PUT",
            f"{API}/channels/{channel}/messages/{approval['id']}/reactions/{emoji}/@me",
            headers={"Authorization": f"Bot {token}"},
        )
    print(f"posted Discord review request for {candidate['version']}")


if __name__ == "__main__":
    main()
