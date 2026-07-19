#!/usr/bin/env python3
"""Run bounded, read-only queries against the shared Supabase marketplace data."""

import argparse
import json
import os
from pathlib import Path
import re
import sys

import psycopg


ALLOWED_TABLES = {
    "sources",
    "products",
    "product_identifiers",
    "listings",
    "price_observations",
    "sync_runs",
}
MAX_ROWS = 100
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|create|alter|drop|truncate|grant|revoke|copy|"
    r"call|do|execute|set|reset|begin|commit|rollback|vacuum|analyze)\b",
    re.IGNORECASE,
)


def validate(sql: str) -> str:
    statement = sql.strip().rstrip(";").strip()
    if not statement.lower().startswith(("select ", "with ")):
        raise ValueError("Only SELECT queries are allowed.")
    if ";" in statement or FORBIDDEN.search(statement):
        raise ValueError("The query contains a non-read-only operation.")
    referenced = set(re.findall(r"\b(?:public\.)?([a-z_]+)\b", statement.lower()))
    blocked = {name for name in referenced if name == "watchlists"}
    if blocked:
        raise ValueError("Queries to user-specific watchlists are not allowed.")
    return statement


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sql", required=True, help="One SELECT query")
    args = parser.parse_args()
    try:
        sql = validate(args.sql)
        connection_string = os.environ.get("SUPABASE_AGENT_READONLY_CONNECTION_STRING", "")
        if connection_string.startswith("openshell:resolve:") or not connection_string:
            secret_files = sorted(Path("/sandbox").glob(".*/supabase_readonly.env"))
            if not secret_files:
                raise KeyError("SUPABASE_AGENT_READONLY_CONNECTION_STRING")
            connection_string = secret_files[0].read_text(encoding="utf-8").strip()
        with psycopg.connect(connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout = '10s'")
                cursor.execute(sql)
                columns = [column.name for column in cursor.description]
                rows = cursor.fetchmany(MAX_ROWS)
        print(json.dumps([dict(zip(columns, row)) for row in rows], default=str))
        return 0
    except (KeyError, ValueError, psycopg.Error) as error:
        print(f"Read-only Supabase query failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
