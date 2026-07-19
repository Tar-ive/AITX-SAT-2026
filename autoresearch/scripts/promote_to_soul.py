#!/usr/bin/env python3
"""Promotion reconciler — when an experiment is promoted, merge its winning
lessons into the agent SOUL in Supabase, with content-hash dedup so merging
memory diffs is trivial and idempotent.

Flow (your step 9→soul):
  1. a git branch's experiment is promoted (passed the boundaries gate),
  2. its champion-lessons.md is the winning policy,
  3. each lesson line gets a stable content hash; the SOUL is the UNION of
     hashed lines — merging two memory diffs is just set-union, so re-running
     never duplicates and two sources reconcile cleanly,
  4. the new SOUL version is written to public.agent_soul (versioned),
  5. the promoted git ref is recorded so the code change and the memory change
     stay linked.

Usage:
  promote_to_soul.py --agent hermes --lessons research/champion-lessons.md \\
     --experiment exp-083 --git-ref <branch-or-sha>

Env: SUPABASE_DB_PW (+ pooler host/user). Optional COORDINATOR_URL.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys


def envq(n, d=""):
    return os.environ.get(n, d).strip().strip("'").strip('"')


DSN = (f"host={envq('SUPABASE_POOLER_HOST', 'aws-0-ca-central-1.pooler.supabase.com')} "
       f"port=5432 dbname=postgres user={envq('SUPABASE_POOLER_USER', 'postgres.qzegmkzyzalmakoqxezc')} "
       f"sslmode=require")


def psql(sql, out=True):
    r = subprocess.run(["psql", DSN, "-t", "-A", "-c", sql], capture_output=True, text=True,
                       env={**os.environ, "PGPASSWORD": envq("SUPABASE_DB_PW")})
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
    return r.stdout.strip() if out else r.returncode


def lit(s):
    return "$s$" + (s or "") + "$s$"


def line_hash(line):
    # normalize a lesson line, hash its content — merging is union over hashes.
    norm = re.sub(r"\s+", " ", line.strip().lstrip("-*• ").lower())
    return hashlib.sha256(norm.encode()).hexdigest()[:12], line.strip()


def parse_lessons(text):
    """Return {hash: original_line} for every non-empty bullet/line."""
    out = {}
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        h, orig = line_hash(ln)
        out[h] = orig
    return out


def latest_soul(agent):
    body = psql(f"select soul_md from public.agent_soul where agent_name={lit(agent)} "
                f"order by version desc limit 1;")
    ver = psql(f"select coalesce(max(version),0) from public.agent_soul where agent_name={lit(agent)};")
    return int(ver or 0), body


def render(hashed):
    header = "# Agent SOUL — learned lessons (hash-merged)\n\n## Learned lessons\n"
    return header + "\n".join(f"- {v.lstrip('-*• ')}" for v in hashed.values()) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="hermes")
    ap.add_argument("--lessons", required=True)
    ap.add_argument("--experiment", required=True)
    ap.add_argument("--git-ref", default="")
    args = ap.parse_args()

    new = parse_lessons(open(args.lessons).read())
    prev_ver, prev_body = latest_soul(args.agent)
    prev = parse_lessons(prev_body) if prev_body else {}

    # hash-union merge: keep all existing, add any new hashes. idempotent.
    merged = dict(prev)
    added = 0
    for h, line in new.items():
        if h not in merged:
            merged[h] = line
            added += 1

    if added == 0:
        print(f"SOUL v{prev_ver} already contains all promoted lessons (hash-dedup); no new version")
        return

    soul_md = render(merged)
    summary = f"promoted {args.experiment}" + (f" (git {args.git_ref[:12]})" if args.git_ref else "")
    rc = psql(f"insert into public.agent_soul (agent_name, version, soul_md, diff_lines, summary) "
              f"values ({lit(args.agent)}, {prev_ver + 1}, {lit(soul_md)}, {added}, {lit(summary)});", out=False)
    print(f"SOUL v{prev_ver + 1} for {args.agent}: merged {added} new lesson(s) "
          f"({len(merged)} total, hash-deduped) from {args.experiment}")

    coord = envq("COORDINATOR_URL").rstrip("/")
    if coord and rc == 0:
        try:
            import requests
            requests.post(f"{coord}/api/radar", timeout=15, json={
                "source": "promotion", "version": f"soul-v{prev_ver + 1}",
                "memory_diff_lines": added, "experiment": args.experiment})
        except Exception:
            pass


if __name__ == "__main__":
    main()
