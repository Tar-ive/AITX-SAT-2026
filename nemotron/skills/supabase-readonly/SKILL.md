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

Do not query `public.watchlists`, which can contain user-specific information.
Keep queries focused, use filters and `LIMIT`, and never attempt INSERT, UPDATE,
DELETE, DDL, or transaction-control commands. The helper and database role both
enforce read-only behavior.
