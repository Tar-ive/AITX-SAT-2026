---
name: supabase-readonly
description: Query the project's shared Supabase marketplace data without write access.
---

# Supabase read-only access

Use this skill only for retrieving data. Queries are sent to the local
read-only proxy; never request, print, or handle a database credential.

Run a single `SELECT` query with:

```bash
/opt/hermes/.venv/bin/python -c "import json, urllib.request; sql='SELECT ...'; request=urllib.request.Request('http://host.openshell.internal:8001/query', data=json.dumps({'sql': sql}).encode(), headers={'Content-Type':'application/json'}, method='POST'); print(urllib.request.urlopen(request, timeout=15).read().decode())"
```

Only query these shared marketplace tables:

- `public.sources`
- `public.products`
- `public.product_identifiers`
- `public.listings`
- `public.price_observations`
- `public.sync_runs`
- `public.reviews_feedback` — aggregated Discord reactions, feedback-button
  votes, and human replies/threads. Use it to learn current preferences; do
  not expose author IDs or raw feedback text in user-facing answers.
- `public.agent_shared_memory` — sanitised canonical user inputs shared by
  NemoHermes and NemoClaw. One Discord message is stored once using its message
  ID as the deduplication key; use this for internal context only.
- `public.agent_shared_memory` — one sanitised canonical user-input record per
  Discord message, shared by NemoHermes and NemoClaw. Use it as short-lived
  context, never expose raw records, and respect `#no-memory` opt-out.

Do not query `public.watchlists`, which can contain user-specific information.
Keep queries focused, use filters and `LIMIT`, and never attempt INSERT, UPDATE,
DELETE, DDL, or transaction-control commands. The helper and database role both
enforce read-only behavior.
