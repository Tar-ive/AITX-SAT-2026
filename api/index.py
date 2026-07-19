#!/usr/bin/env python3
"""Vercel serverless adapter for the hosted-Supabase dashboard API."""

import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dashboard_api import (  # noqa: E402
    CATEGORIES,
    IMPROVEMENT_RUNS,
    RSI_RUNS_CSV,
    autoresearch_experiments,
    build_story,
    database,
    marketplace,
    rsi_idea_memory,
    rsi_operations,
    try_supabase_rsi_runs,
)


class handler(BaseHTTPRequestHandler):
    def json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        route = parsed.path.removeprefix("/api").rstrip("/") or "/"

        if route == "/health":
            try:
                with database() as connection, connection.cursor() as cursor:
                    cursor.execute("select now()")
                    checked_at = cursor.fetchone()[0].isoformat()
                self.json({"status": "ok", "database": "hosted Supabase", "checked_at": checked_at})
            except Exception as error:
                self.json({"status": "error", "error": str(error)}, 503)
            return

        if route == "/marketplace":
            category = query.get("category", ["all"])[0].lower()
            if category not in {*CATEGORIES, "all"}:
                self.json({"error": "category must be gpu, macbook, ram, or all"}, 400)
                return
            try:
                self.json(marketplace(category))
            except Exception as error:
                self.json({"data_status": "unavailable", "error": str(error), "listings": []}, 503)
            return

        if route == "/autoresearch-experiments":
            try:
                self.json(autoresearch_experiments())
            except Exception as error:
                self.json({"error": str(error), "experiments": []}, 503)
            return

        if route == "/supabase-rsi-runs":
            self.json(try_supabase_rsi_runs())
            return

        if route == "/improvement":
            try:
                payload = build_story(RSI_RUNS_CSV) if RSI_RUNS_CSV.exists() else {
                    "evidence_status": "illustrative",
                    "source": "built-in fallback",
                    "runs": IMPROVEMENT_RUNS,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
                self.json(payload)
            except Exception as error:
                self.json({"evidence_status": "invalid", "error": str(error), "runs": []}, 422)
            return

        if route == "/rsi-operations":
            try:
                self.json(rsi_operations())
            except Exception as error:
                self.json({"status": "invalid", "error": str(error)}, 422)
            return

        if route == "/rsi-ideas":
            try:
                self.json(rsi_idea_memory())
            except Exception as error:
                self.json({"status": "unavailable", "error": str(error), "ideas": []}, 503)
            return

        self.json({"error": "not found"}, 404)
