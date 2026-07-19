#!/usr/bin/env python3
"""Search-cache micro-service — runs on the EC2 HOST, reachable from the
sandbox over its egress bridge (10.200.0.1). Keeps agents credential-free:
the host holds the DB connection string; the agent just calls HTTP.

  GET  /search-cache?q=RTX+5090   -> most recent cache row (or {"hit":false})
  POST /search-cache  {json}       -> insert a search record

Uses psql (already on the host) via the SUPABASE pooler. Stdlib only.
Env: SUPABASE_DB_PW, SUPABASE_POOLER_HOST, SUPABASE_POOLER_USER, PORT (8787).
"""
import json
import os
import re
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

def env(name, default=""):
    # docker --env-file keeps surrounding quotes literally; strip them.
    return os.environ.get(name, default).strip().strip("'").strip('"')

DSN = (f"host={env('SUPABASE_POOLER_HOST','aws-0-ca-central-1.pooler.supabase.com')} "
       f"port=5432 dbname=postgres user={env('SUPABASE_POOLER_USER','postgres.qzegmkzyzalmakoqxezc')} "
       f"sslmode=require")
PW = env("SUPABASE_DB_PW")


def slug(s):
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", (s or "").lower()))[:60]


def psql(sql):
    r = subprocess.run(["psql", DSN, "-t", "-A", "-F", "\x1f", "-c", sql],
                       capture_output=True, text=True, env={**os.environ, "PGPASSWORD": PW})
    return r.stdout.strip(), r.returncode


def lit(v):
    if v is None:
        return "null"
    return "'" + str(v).replace("'", "''") + "'"


def arr(xs):
    return "'{" + ",".join('"' + str(x).replace('"', '') + '"' for x in (xs or [])) + "}'"


REPO_DIR = os.environ.get("REPO_DIR", "/repo")


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def _file(self, path, ctype):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            return self._send(404, {"error": "not found"})
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        # Reliable, always-fresh leaderboard served straight from the host —
        # no Railway ephemeral wipes, no deploy lag. Read-only; exposes only
        # the leaderboard page and its data file (never the repo/secrets).
        if u.path in ("/leaderboard", "/", "/autoresearch"):
            return self._file(os.path.join(REPO_DIR, "frontend", "autoresearch.html"), "text/html; charset=utf-8")
        if u.path == "/radar":
            return self._file(os.path.join(REPO_DIR, "autoresearch", "data", "radar_snapshots.json"), "application/json")
        if u.path != "/search-cache":
            return self._send(404, {"error": "not found"})
        q = (parse_qs(u.query).get("q") or [""])[0]
        out, rc = psql(
            "select sites_with_results, best_price, best_source, best_url, available, "
            "round(extract(epoch from now()-searched_at)/3600,1) "
            f"from public.search_cache where product_slug={lit(slug(q))} "
            "order by searched_at desc limit 1;")
        if rc != 0 or not out:
            return self._send(200, {"hit": False})
        f = out.split("\x1f")
        self._send(200, {"hit": True, "sites_with_results": f[0].strip("{}").split(",") if f[0] else [],
                         "best_price": f[1], "best_source": f[2], "best_url": f[3],
                         "available": f[4] == "t", "age_hours": float(f[5])})

    def do_POST(self):
        if urlparse(self.path).path != "/search-cache":
            return self._send(404, {"error": "not found"})
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            p = json.loads(self.rfile.read(n))
        except json.JSONDecodeError:
            return self._send(400, {"error": "bad json"})
        _, rc = psql(
            "insert into public.search_cache (product_query, product_slug, sites_checked, "
            "sites_with_results, best_price, best_source, best_url, available, searched_by) values ("
            f"{lit(p.get('product_query'))}, {lit(slug(p.get('product_query','')))}, "
            f"{arr(p.get('sites_checked'))}, {arr(p.get('sites_with_results'))}, "
            f"{p.get('best_price') if p.get('best_price') is not None else 'null'}, "
            f"{lit(p.get('best_source'))}, {lit(p.get('best_url'))}, "
            f"{'true' if p.get('available', True) else 'false'}, {lit(p.get('searched_by','agent'))});")
        self._send(200, {"saved": rc == 0})


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8787))), H).serve_forever()
