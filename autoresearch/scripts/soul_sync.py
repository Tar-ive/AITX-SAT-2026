#!/usr/bin/env python3
"""Sync a Hermes SOUL.md into Supabase — the bridge between Hermes's
preference-learning and the RSI loop.

Hermes learns user preferences and writes SOUL.md inside its sandbox. This
script versions each change into public.agent_soul so it is:
  - persistent (survives sandbox rebuilds / box self-stop)
  - web-accessible (public.agent_soul_latest view + coordinator can serve it)
  - shareable (other agents read the latest SOUL for the same user)
  - measurable — the diff-line count IS the RSI loop's 5th metric
    (episodic-memory / soul churn = how much the agent learned this cycle).

Usage:
  soul_sync.py push --agent hermes --file /path/to/SOUL.md
  soul_sync.py push --agent hermes --container <docker-name>   # pull from sandbox
  soul_sync.py pull --agent hermes                             # print latest SOUL
  soul_sync.py diff-lines --agent hermes                       # latest churn (5th metric)

Env: SUPABASE_DB_PW (+ pooler host/user). Optional COORDINATOR_URL to also
POST the churn as an eval signal.
"""
import argparse
import difflib
import os
import subprocess
import sys


def envq(name, default=""):
    return os.environ.get(name, default).strip().strip("'").strip('"')


DSN = (f"host={envq('SUPABASE_POOLER_HOST', 'aws-0-ca-central-1.pooler.supabase.com')} "
       f"port=5432 dbname=postgres user={envq('SUPABASE_POOLER_USER', 'postgres.qzegmkzyzalmakoqxezc')} "
       f"sslmode=require")


def psql(sql, want_out=True):
    r = subprocess.run(["psql", DSN, "-t", "-A", "-c", sql],
                       capture_output=True, text=True,
                       env={**os.environ, "PGPASSWORD": envq("SUPABASE_DB_PW")})
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
    return r.stdout.strip() if want_out else r.returncode


def lit(s):
    return "$soul$" + (s or "") + "$soul$"


def latest(agent):
    out = psql(f"select version, soul_md from public.agent_soul "
               f"where agent_name = {lit(agent)} order by version desc limit 1;")
    if not out:
        return 0, ""
    ver, _, body = out.partition("|")
    return int(ver), body


def read_soul(args):
    if args.container:
        r = subprocess.run(["docker", "exec", args.container, "cat",
                            args.soul_in_container], capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else ""
    if args.file:
        try:
            return open(args.file).read()
        except OSError:
            return ""
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["push", "pull", "diff-lines"])
    ap.add_argument("--agent", default="hermes")
    ap.add_argument("--file")
    ap.add_argument("--container")
    ap.add_argument("--soul-in-container", dest="soul_in_container",
                    default="/sandbox/.hermes/workspace/SOUL.md")
    ap.add_argument("--summary", default="SOUL update (user preferences learned)")
    args = ap.parse_args()

    if args.cmd == "pull":
        _, body = latest(args.agent)
        print(body)
        return

    if args.cmd == "diff-lines":
        out = psql(f"select coalesce(diff_lines,0) from public.agent_soul "
                   f"where agent_name = {lit(args.agent)} order by version desc limit 1;")
        print(out or "0")
        return

    # push
    new = read_soul(args)
    if not new.strip():
        print("no SOUL content found; nothing to push")
        return
    prev_ver, prev = latest(args.agent)
    if new.strip() == prev.strip():
        print(f"SOUL unchanged (v{prev_ver}); no new version")
        return
    diff = list(difflib.unified_diff(prev.splitlines(), new.splitlines(), lineterm=""))
    churn = sum(1 for d in diff if d and d[0] in "+-" and not d.startswith(("+++", "---")))
    rc = psql(f"insert into public.agent_soul (agent_name, version, soul_md, diff_lines, summary) "
              f"values ({lit(args.agent)}, {prev_ver + 1}, {lit(new)}, {churn}, {lit(args.summary)});",
              want_out=False)
    print(f"pushed SOUL v{prev_ver + 1} for {args.agent}: {churn} diff lines (the 5th metric)")

    coord = envq("COORDINATOR_URL").rstrip("/")
    if coord and rc == 0:
        try:
            import requests
            requests.post(f"{coord}/api/radar", timeout=15, json={
                "source": "hermes-soul", "version": f"soul-v{prev_ver + 1}",
                "memory_diff_lines": churn, "agent": args.agent})
        except Exception:
            pass


if __name__ == "__main__":
    main()
