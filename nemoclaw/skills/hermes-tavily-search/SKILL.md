---
name: tavily-search
description: Search the public web with Tavily. Use when a Discord user asks for current information, sources, news, facts that may have changed, or asks to search the web.
---

# Tavily Search

Use this only after the `database-first-research` policy determines that the
shared Supabase data has no relevant or sufficiently current answer. Run no
more than one search for a user request; the command is capped at five results
(five websites maximum):

```bash
/opt/hermes/.venv/bin/python /sandbox/.hermes/skills/tavily-search/tavily_search.py "<query>"
```

Use the returned titles, URLs, and content snippets to answer. State when the answer is based on web results and include the source URLs. Do not claim that a search succeeded if the command reports an error.

For product, deal, or retailer research, preserve the direct URLs returned by
the search. Give every online option a direct, clickable product or listing URL
that the evidence supports. Clearly label every result as online or in-person /
pickup, and do not imply that an in-person option can be purchased online.

The command uses a protected OpenShell credential placeholder. Never ask Discord users for an API key and never print credentials.
