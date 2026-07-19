---
name: database-first-research
description: Research policy for Hermes: query shared Supabase data first, then use a tightly limited Tavily fallback.
---

# Database-first research

For every request that needs facts, listings, prices, market data, historical
context, or prior project findings, follow this order.

1. Query the shared Supabase marketplace data first with the
   `supabase-readonly` skill. Use one focused, read-only `SELECT` with a
   relevant filter and `LIMIT`; never access credentials or write data.
2. Use those rows if they answer the request. State that the answer is based
   on the shared database and identify any freshness limitation.
3. Only if the database has no relevant rows, or the rows are clearly stale or
   incomplete for the request, use the `tavily-search` skill as the fallback.
4. Run at most one Tavily search per request, with at most five results. Do
   not open, extract, or cite more than five distinct external websites. Prefer
   primary or authoritative sources among those results.
5. In the answer, clearly distinguish database findings from web findings and
   say when neither source produced enough evidence.

Do not use generic web-search or web-extract tools before the database check.
