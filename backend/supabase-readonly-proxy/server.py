import json
import os
import re
import threading
import http.client
from urllib.request import Request, urlopen
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import discord
import psycopg

MAX_ROWS = 100
FORBIDDEN = re.compile(r"\b(insert|update|delete|merge|create|alter|drop|truncate|grant|revoke|copy|call|do|execute|set|reset|begin|commit|rollback|vacuum|analyze|watchlists)\b", re.I)


def read_query(sql):
    statement = sql.strip().rstrip(";").strip()
    if not statement.lower().startswith(("select ", "with ")) or ";" in statement or FORBIDDEN.search(statement):
        raise ValueError("Only SELECT queries to shared marketplace tables are allowed.")
    with psycopg.connect(os.environ["SUPABASE_AGENT_READONLY_CONNECTION_STRING"]) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '10s'")
            cursor.execute(statement)
            columns = [column.name for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchmany(MAX_ROWS)]


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path not in {"/query", "/publish"}:
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size))
            if self.path == "/query":
                result = read_query(payload["sql"])
                response = {"rows": result}
            else:
                content = str(payload.get("content", "")).strip()
                if not content:
                    raise ValueError("A cron-output message is required.")
                content = content[:1900]
                channel_id = os.environ["DISCORD_DAILY_CHANNEL_ID"]
                bot_token = os.environ["DISCORD_SAGE_BOT_TOKEN"]
                discord_connection = http.client.HTTPSConnection("discord.com", timeout=15)
                discord_connection.request(
                    "POST",
                    f"/api/v10/channels/{channel_id}/messages",
                    body=json.dumps({"content": f"[Sage daily update]\n{content}"}),
                    headers={"Authorization": f"Bot {bot_token}", "Content-Type": "application/json"},
                )
                discord_response = discord_connection.getresponse()
                if not 200 <= discord_response.status < 300:
                    raise RuntimeError(f"Discord rejected the post ({discord_response.status})")
                discord_response.read()
                discord_connection.close()
                response = {"published": True}
            body = json.dumps(response, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as error:
            body = json.dumps({"error": str(error)}).encode()
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *_):
        pass


class SageClient(discord.Client):
    async def on_ready(self):
        print(f"Sage connected as {self.user}; guild_count={len(self.guilds)}", flush=True)
        channel_id = int(os.environ["DISCORD_DAILY_CHANNEL_ID"])
        for guild in self.guilds:
            member = guild.me
            channel = guild.get_channel(channel_id)
            if member is None:
                print(f"Sage diagnostics: guild={guild.id}; member cache unavailable", flush=True)
            elif channel is None:
                print(f"Sage diagnostics: guild={guild.id}; daily channel not visible to Sage", flush=True)
            else:
                permissions = channel.permissions_for(member)
                print(
                    f"Sage diagnostics: daily_view={permissions.view_channel}; "
                    f"daily_send={permissions.send_messages}; roles={[role.name for role in member.roles]}",
                    flush=True,
                )


def run_sage_gateway():
    SageClient(intents=discord.Intents.none()).run(
        os.environ["DISCORD_SAGE_BOT_TOKEN"], log_handler=None
    )


threading.Thread(target=run_sage_gateway, daemon=True).start()
ThreadingHTTPServer(("0.0.0.0", 8001), Handler).serve_forever()
