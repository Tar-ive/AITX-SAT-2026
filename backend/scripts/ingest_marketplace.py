#!/usr/bin/env python3
"""Fetch a few marketplace listings and write them to hosted Supabase."""

import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import quote_plus

import psycopg2
import requests
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[1]
EBAY_SCOPE = "https://api.ebay.com/oauth/api_scope"
ALLOWED_CATEGORIES = {
    "macbook": re.compile(r"\bmacbook\b", re.I),
    "gpu": re.compile(r"\b(gpu|graphics card|video card|geforce|rtx|gtx|radeon)\b", re.I),
    "ram": re.compile(
        r"\b(memory module|ram (?:kit|module|stick)|(?:kit|module|stick) of ram|"
        r"ddr[345](?:[- ]?\d+)?|sodimm|so-dimm|dimm)\b",
        re.I,
    ),
}
ALLOWED_QUERY = re.compile(
    r"\b(macbook|gpu|graphics card|video card|geforce|rtx|gtx|radeon|"
    r"ram|memory|ddr[345]|sodimm|so-dimm|dimm)\b",
    re.I,
)


def load_env():
    for raw in (ROOT / ".env").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


def env(*names, default=None):
    return next((os.environ[name] for name in names if os.environ.get(name)), default)


def money(value, default=0):
    if isinstance(value, dict):
        value = value.get("value", default)
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value or default))
    return float(match.group().replace(",", "")) if match else float(default)


def category(text):
    return next((name for name, pattern in ALLOWED_CATEGORIES.items() if pattern.search(text)), None)


def database():
    pooler = (ROOT / "supabase/.temp/pooler-url").read_text().strip()
    endpoint = pooler.rsplit("@", 1)[-1].split("/", 1)[0]
    host, port = endpoint.rsplit(":", 1)
    project_ref = (ROOT / "supabase/.temp/project-ref").read_text().strip()
    return psycopg2.connect(
        host=host,
        port=int(port),
        user=f"postgres.{project_ref}",
        password=env("SUPABASE_DB_PW", "SUPABASE_DB_PASSWORD"),
        dbname="postgres",
        sslmode="require",
    )


def ebay_token(api_host):
    client, secret = env("EBAY_CLIENT_ID"), env("EBAY_CLIENT_SECRET")
    if not (client and secret):
        token = env("EBAY_OAUTH_APPLICATION_TOKEN")
        if not token:
            raise RuntimeError("missing eBay token or client credentials")
        return token

    basic = base64.b64encode(f"{client}:{secret}".encode()).decode()
    response = requests.post(
        f"https://{api_host}/identity/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials", "scope": EBAY_SCOPE},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def fetch_ebay(query, limit):
    environment = env("EBAY_ENV", default="sandbox").lower()
    api_host = "api.ebay.com" if environment == "production" else "api.sandbox.ebay.com"
    response = requests.get(
        f"https://{api_host}/buy/browse/v1/item_summary/search",
        params={"q": query, "limit": limit},
        headers={
            "Authorization": f"Bearer {ebay_token(api_host)}",
            "X-EBAY-C-MARKETPLACE-ID": env("EBAY_MARKETPLACE_ID", default="EBAY_US"),
        },
        timeout=30,
    )
    response.raise_for_status()

    rows = []
    for item in response.json().get("itemSummaries", []):
        shipping = (item.get("shippingOptions") or [{}])[0].get("shippingCost", {})
        seller = item.get("seller") or {}
        rows.append(
            {
                "external_id": item["itemId"],
                "title": item["title"],
                "condition": item.get("condition"),
                "seller_name": seller.get("username"),
                "seller_rating": money(seller.get("feedbackPercentage")),
                "currency": (item.get("price") or {}).get("currency", "USD"),
                "item_price": money(item.get("price")),
                "shipping_price": money(shipping),
                "listing_url": item.get("itemWebUrl"),
                "image_url": (item.get("image") or {}).get("imageUrl"),
                "availability": "available",
                "collection_method": "api",
                "collector": f"ebay-browse:{environment}",
                "raw_payload": {
                    "collection_method": "api",
                    "collector": "ebay-browse",
                    "environment": environment,
                    "query": query,
                    "record": item,
                },
            }
        )
    return rows


def fetch_bestbuy(query, limit):
    token = env("APIFY_API_KEY", "APIFY_API_KEy")
    if not token:
        raise RuntimeError("missing APIFY_API_KEY")

    actor = env("APIFY_BESTBUY_ACTOR", default="axlymxp/bestbuy-scraper")
    response = requests.post(
        f"https://api.apify.com/v2/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items",
        params={"token": token},
        json={
            "searchQuery": query,
            "maxResults": limit,
            "fetchProductDetails": True,
            "zipCode": "60601",
        },
        timeout=240,
    )
    response.raise_for_status()

    rows = []
    for item in response.json():
        title = item.get("title") or item.get("productName") or item.get("name")
        url = item.get("url") or item.get("productUrl") or item.get("link")
        external_id = (
            item.get("sku")
            or item.get("skuId")
            or item.get("productId")
            or hashlib.sha256(f"{title}|{url}".encode()).hexdigest()[:24]
        )
        price = item.get("currentPrice", item.get("salePrice", item.get("price")))
        if not title or price is None:
            continue
        rows.append(
            {
                "external_id": str(external_id),
                "title": title,
                "condition": item.get("condition", "New"),
                "seller_name": "Best Buy",
                "seller_rating": None,
                "currency": item.get("currency", "USD"),
                "item_price": money(price),
                "shipping_price": money(item.get("shippingPrice")),
                "listing_url": url
                or f"https://www.bestbuy.com/site/searchpage.jsp?st={quote_plus(query)}",
                "image_url": item.get("imageUrl") or item.get("image"),
                "availability": str(item.get("availability", item.get("inStock", "unknown"))),
                "collection_method": "scraped",
                "collector": f"apify:{actor}",
                "raw_payload": {
                    "collection_method": "scraped",
                    "collector": f"apify:{actor}",
                    "merchant": "Best Buy",
                    "query": query,
                    "record": item,
                },
            }
        )
    return rows


def save_rows(connection, source, query, rows):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into public.sync_runs (source_id, status, metadata)
            select id, 'running', %s from public.sources where slug = %s
            returning id, source_id
            """,
            (Json({"query": query}), source),
        )
        sync_id, source_id = cursor.fetchone()

        for row in rows:
            cursor.execute(
                """
                insert into public.listings (
                  source_id, external_id, title, condition, seller_name, seller_rating,
                  currency, item_price, shipping_price, listing_url, image_url,
                  availability, collection_method, collector, raw_payload
                ) values (
                  %(source_id)s, %(external_id)s, %(title)s, %(condition)s,
                  %(seller_name)s, %(seller_rating)s, %(currency)s, %(item_price)s,
                  %(shipping_price)s, %(listing_url)s, %(image_url)s, %(availability)s,
                  %(collection_method)s, %(collector)s, %(raw_payload)s
                )
                on conflict (source_id, external_id) do update set
                  title = excluded.title,
                  condition = excluded.condition,
                  seller_name = excluded.seller_name,
                  seller_rating = excluded.seller_rating,
                  currency = excluded.currency,
                  item_price = excluded.item_price,
                  shipping_price = excluded.shipping_price,
                  listing_url = excluded.listing_url,
                  image_url = excluded.image_url,
                  availability = excluded.availability,
                  collection_method = excluded.collection_method,
                  collector = excluded.collector,
                  raw_payload = excluded.raw_payload,
                  last_seen_at = now()
                returning id
                """,
                {**row, "source_id": source_id, "raw_payload": Json(row["raw_payload"])},
            )
            listing_id = cursor.fetchone()[0]
            cursor.execute(
                """
                insert into public.price_observations
                  (listing_id, item_price, shipping_price, currency)
                values (%s, %s, %s, %s)
                """,
                (listing_id, row["item_price"], row["shipping_price"], row["currency"]),
            )

        cursor.execute(
            """
            update public.sync_runs
            set status = 'succeeded', records_seen = %s, finished_at = now()
            where id = %s
            """,
            (len(rows), sync_id),
        )
        cursor.execute("update public.sources set enabled = true where id = %s", (source_id,))
    connection.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?", default="RTX 5090")
    parser.add_argument("--source", choices=("all", "ebay", "bestbuy"), default="all")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    if not ALLOWED_QUERY.search(args.query):
        parser.error("query must target a GPU, MacBook, or RAM")

    load_env()
    fetchers = {"ebay": fetch_ebay, "bestbuy": fetch_bestbuy}
    selected = fetchers if args.source == "all" else {args.source: fetchers[args.source]}
    connection, loaded = database(), 0
    try:
        for source, fetch in selected.items():
            try:
                rows = fetch(args.query, args.limit)
                rows = [row for row in rows if category(row["title"])]
                if not rows:
                    raise RuntimeError("source returned no allowed GPU, MacBook, or RAM listings")
                save_rows(connection, source, args.query, rows)
                loaded += len(rows)
                print(f"{source}: stored {len(rows)} current listings")
            except Exception as error:
                connection.rollback()
                print(f"{source}: failed ({error})")
    finally:
        connection.close()
    if not loaded:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
