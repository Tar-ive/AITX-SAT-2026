---
name: tavily-search
description: Search the public web with Tavily. Use when a Discord user asks for current information, sources, news, facts that may have changed, or asks to search the web.
---

# Tavily Search

Run the dedicated search command for current web information:

```bash
/opt/hermes/.venv/bin/python /sandbox/.hermes/skills/tavily-search/tavily_search.py "<query>"
```

Use the returned titles, URLs, and content snippets to answer. State when the answer is based on web results and include the source URLs. Do not claim that a search succeeded if the command reports an error.

The command uses a protected OpenShell credential placeholder. Never ask Discord users for an API key and never print credentials.
