#!/usr/bin/env python3
"""Reproducible daily deal workflow with optional production adapters."""
from __future__ import annotations
import argparse, json, os, re, time, uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

try: from .cron_regex import parse as parse_schedule
except ImportError: from cron_regex import parse as parse_schedule

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = Path(__file__).resolve().parent
RUNS = WORKFLOW / "runs"
def now(): return datetime.now(timezone.utc).isoformat()
def step(ledger, name, fn):
    started = time.perf_counter(); stamp = now()
    try: result, status, error = fn(), "succeeded", None
    except Exception as exc: result, status, error = None, "failed", str(exc); raise
    finally: ledger.append({"name":name,"status":status,"started_at":stamp,"duration_ms":round((time.perf_counter()-started)*1000,1),"error":error})
    return result
def parse_command(text):
    match = re.fullmatch(r"!deals\s+(.+)", " ".join(text.strip().split()), flags=re.I)
    if not match: raise ValueError("Use: !deals daily at 9am")
    return parse_schedule(match.group(1))
def load_preferences(path):
    if not path.exists(): raise FileNotFoundError(f"Missing preference file: {path}")
    return path.read_text(encoding="utf-8")
def research(mode):
    if mode == "demo": return json.loads((WORKFLOW / "fixtures" / "listings.json").read_text())
    command = os.environ.get("OPEN_SHELL_RESEARCH_COMMAND")
    if not command: raise RuntimeError("Set OPEN_SHELL_RESEARCH_COMMAND for a live research run")
    import subprocess
    return json.loads(subprocess.run(command, shell=True, check=True, capture_output=True, text=True, timeout=110).stdout)
def categorize(listings):
    categories = {"online": [], "offline": []}
    for item in listings:
        bucket = "offline" if item.get("fulfillment") == "offline" else "online"
        categories[bucket].append({**item,"total":round(float(item["price"])+float(item.get("shipping",0)),2)})
    return categories
def recommend(categories, preferences):
    budget = re.search(r"Budget:\s*\$?([\d,]+)", preferences, re.I); maximum = float(budget.group(1).replace(",","")) if budget else float("inf")
    minimum = re.search(r"Minimum saving to alert:\s*(\d+)%", preferences, re.I); floor = float(minimum.group(1)) if minimum else 0
    candidates=[]
    for channel, entries in categories.items():
        for item in entries:
            saving=round(100*(float(item.get("baseline_price",item["total"]))-item["total"])/float(item.get("baseline_price",item["total"])),1)
            if item["total"] <= maximum and saving >= floor and item.get("condition") in {"new","manufacturer-refurbished"}: candidates.append({**item,"channel":channel,"saving_percent":saving})
    return sorted(candidates,key=lambda x:(x["total"]+(15 if x["channel"]=="offline" else 0),-x["saving_percent"]))[:3]
def discord_message(recommendations, run_id=None):
    """Render the user-facing Sage digest without internal execution metadata."""
    lines = ["**Daily deals**"]
    for deal in recommendations:
        if deal["channel"] == "online":
            lines.append(
                f"- **Online**: [{deal['title']}]({deal['url']}) - **${deal['total']:.2f}** "
                f"at {deal['store']} ({deal['saving_percent']}% below baseline)"
            )
        else:
            stock_url = deal.get("stock_check_url") or deal["url"]
            location = deal.get("location") or "check your selected store"
            lines.append(
                f"- **In-store / pickup**: [{deal['title']}]({deal['url']}) - **${deal['total']:.2f}** "
                f"at {deal['store']} ({deal['saving_percent']}% below baseline); "
                f"location: {location}; [check local stock]({stock_url})"
            )
    return "\n".join(lines) if recommendations else "No verified matches met your preferences today."
def post_discord(content, mode):
    if mode == "demo": return {"destination":"#daily","mode":"dry-run","content":content}
    webhook=os.environ.get("DISCORD_DAILY_WEBHOOK_URL")
    if not webhook: raise RuntimeError("Set DISCORD_DAILY_WEBHOOK_URL for a live publish")
    request=Request(webhook,json.dumps({"content":content}).encode(),{"Content-Type":"application/json"},method="POST")
    with urlopen(request,timeout=15) as response: return {"destination":"#daily","status":response.status}
def mirror_supabase(payload):
    url,key=os.environ.get("SUPABASE_URL"),os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and key): return "local-ledger (Supabase credentials not configured)"
    request=Request(f"{url.rstrip('/')}/rest/v1/deal_workflow_runs",json.dumps(payload).encode(),{"Content-Type":"application/json","apikey":key,"Authorization":f"Bearer {key}","Prefer":"return=minimal"},method="POST")
    with urlopen(request,timeout=20): return "Supabase"
def run(mode, preferences):
    run_id,ledger=str(uuid.uuid4()),[]
    prefs=step(ledger,"load_user_preferences",lambda:load_preferences(preferences)); raw=step(ledger,"openshell_hiddenlayer_research",lambda:research(mode)); groups=step(ledger,"categorize_online_offline",lambda:categorize(raw)); picks=step(ledger,"hermes_recommend",lambda:recommend(groups,prefs)); content=discord_message(picks,run_id); delivery=step(ledger,"publish_daily",lambda:post_discord(content,mode))
    payload={"id":run_id,"mode":mode,"started_at":ledger[0]["started_at"],"finished_at":now(),"preferences_path":str(preferences),"raw_listings":raw,"categorized":groups,"recommendations":picks,"discord_delivery":delivery,"steps":ledger}
    RUNS.mkdir(exist_ok=True); (RUNS/f"{run_id}.json").write_text(json.dumps(payload,indent=2),encoding="utf-8"); payload["persistence"]=mirror_supabase(payload); return payload
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("command",nargs="?"); parser.add_argument("--run",action="store_true"); parser.add_argument("--mode",choices=["demo","live"],default="demo"); parser.add_argument("--user",type=Path,default=WORKFLOW/"user.md"); args=parser.parse_args()
    if args.command: print(json.dumps(parse_command(args.command),indent=2))
    if args.run: print(json.dumps(run(args.mode,args.user),indent=2))
if __name__ == "__main__": main()
